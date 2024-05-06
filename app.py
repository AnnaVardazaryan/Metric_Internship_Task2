from fastapi import FastAPI, HTTPException
from openai import OpenAI
import uvicorn
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import weaviate
import json
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from weaviate.util import generate_uuid5
from weaviate.classes.query import MetadataQuery

# Initialize FastAPI instance
app = FastAPI()

# Load environment variables from .env file
load_dotenv()

# Initialize your OpenAI client with your API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

weaviate_client = weaviate.connect_to_wcs(
    cluster_url=os.getenv("WCS_DEMO_URL"),
    auth_credentials=weaviate.auth.AuthApiKey(os.getenv("WCS_DEMO_RO_KEY")),
    headers={
        "X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"]
    }
)

# Model for incoming data
class URLData(BaseModel):
    url: str

headers = { 'user-agent': os.getenv("USER_AGENT")}

def scrape_texts_and_links(url):
    """
    Scrapes text content and links from the provided URL.

    Args:
        url (str): The URL of the webpage to scrape.

    Returns:
        tuple: A tuple containing two elements:
            - texts (str): All text content extracted from the webpage.
            - links (str): All links extracted from the webpage, along with their corresponding text.
    """
    try:
        # Send an HTTP GET request to the URL
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Ensure successful response

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract all text from paragraphs and other text holders
        texts = soup.get_text(separator=' ', strip=True)

        # Extract all links and their text
        links = ' '.join(f"{urljoin(url, link['href'])} ({link.get_text(strip=True)})" for link in soup.find_all('a', href=True))

        return texts, links

    except requests.RequestException as e:
        return None

def extract_vc_information(text):
    """
        Extracts Venture Capital (VC) information from the provided text using OpenAI's Generative AI.

        Args:
            text (str): The text containing information about a VC firm.

        Returns:
            dict or None: A dictionary containing the extracted VC information structured as follows:
                {
                    "vc_name": str,
                    "contacts": list or str,
                    "industries": list or str,
                    "investment_rounds": list or str
                }
                Returns None if there is an error during processing.
        """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": """Extract the following information from the provided text and structure
                your response in a JSON format with the specified keys. Ensure that you do not make assumptions or
                include incorrect information. If a specific type of information is completely missing from the text,
                please return only one 'no info' for that field.

        - **VC Name**: Look for the name of the Venture Capital firm.
        - **Contacts**: Search for any type of contact details available such as email addresses or phone numbers.
        Also, ensure to include URLs that link directly to social media profiles or pages from 'http://linkedin.com',
        'http://facebook.com', 'http://instagram.com', 'http://twitter.com'.  List all found info, separating them by commas.
         Also focus on including URLs that provide direct communication channels (e.g., 'contact us', 'connect with us'),
          but avoid links related to job opportunities, personal profiles, or relationships.])
        - **Industries**: Identify and list the industries that the Venture Capital firm invests in. If not directly
         mentioned, infer based on the context of the text.
        - **Investment Rounds**: Extract only the types of investment rounds the firm participates in or leads,
        such as Seed, Series A, Series B, etc. Do not include the names of companies involved in these rounds.
        You can fill the contacts session with links(including words such as contact us, connect us, reach us),
        which will move to pages from where we can take additional information. Do not include links which will contain
        info about jobs, people or relationships.

        Use the following JSON keys for the response:
        {
          "vc_name": "***",
          "contacts": "***",
          "industries": "***",
          "investment_rounds": "***"
        }

        Please format your response as a JSON object with these keys, filling in the appropriate information or 'no info' as required.
        """},
                {"role": "user", "content": text}
            ]
        )
        response_json = json.loads(response.json())["choices"][0]["message"]["content"]
        vc_name = json.loads(response_json)["vc_name"]
        contacts = json.loads(response_json)["contacts"]
        industries = json.loads(response_json)["industries"]
        investment_rounds = json.loads(response_json)["investment_rounds"]

        extracted_info = {
            "vc_name": vc_name,
            "contacts": [contacts] if isinstance(contacts, str) else contacts,
            "industries": [industries] if isinstance(industries, str) else industries,
            "investment_rounds": [investment_rounds] if isinstance(investment_rounds, str) else investment_rounds
        }
        return extracted_info
    except Exception as e:
        print(f"Error processing information with OpenAI: {e}")
        return None


def format_information(extracted_info, url):
    """
        Formats the extracted VC information into a human-readable format.

        Args:
            extracted_info (dict): A dictionary containing the extracted VC information.
                Keys represent different categories of information, and values represent the corresponding data.
            url (str): The URL of the website from which the information was extracted.

        Returns:
            str: A formatted string presenting the extracted VC information.

        """
    prompt = "The information from the URL is the following: \n"
    for key, value in extracted_info.items():
        if value == ['no info']:
            prompt += f"- There is not much information available about {key.capitalize()}. You can check it manually by visiting the website: {url}\n"
        else:
            prompt += f"- {key.capitalize()}: {value}\n"

    return prompt


@app.post("/process-url/")
async def process_vc_url(data: URLData):
    """
        Processes a VC website URL to extract information and find similar VCs.

        Args:
            data (URLData): An object containing the URL of the VC website.

        Returns:
            dict: A dictionary containing a message with extracted VC information and similar VC names.
        """
    # Scrapping Home page of the website
    texts, links = scrape_texts_and_links(data.url)
    text = texts + links
    if text is None:
        raise HTTPException(status_code=400, detail="Failed to scrape the website.")
    extracted_info = extract_vc_information(text)
    if not extracted_info:
        raise HTTPException(status_code=500, detail="Failed to extract information.")

    collection = weaviate_client.collections.get("VentureCapital")
    response = collection.query.fetch_objects(
        return_properties=["vc_name"],
    )
    # Checking if the firm information already exists in our DB
    if extracted_info['vc_name'] not in [o.properties['vc_name'] for o in response.objects]:
        uuid = generate_uuid5(extracted_info)  # Generate a UUID for the new entry

        # Insert data into Weaviate
        collection.data.insert(
            properties=extracted_info,
            uuid=uuid
        )
    user_friendly_text = format_information(extracted_info, data.url)

    # Getting 3 most similar VCs.
    response = collection.query.near_text(
        query=f"{extracted_info}",
        limit=3,
        return_metadata=MetadataQuery(distance=True)
    )

    return {f"Message: {user_friendly_text} \n Similar companies: {[o.properties['vc_name'] for o in response.objects]}"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
