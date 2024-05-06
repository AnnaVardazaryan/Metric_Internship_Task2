# Venture Capital Assistant

This repository contains essential tools for managing and analyzing venture capital data. It includes:

- **Weaviate Vector Database Initialization Notebook**: 
  - A Jupyter notebook that sets up the Weaviate vector database.
  - Populates it with initial data for analysis.

- **FastAPI Application**: 
  - A web application that extracts venture capital data from given website URLs.
  - Stores it in the Weaviate database.
  - Provides search capabilities to find similar firms based on the stored data.


## Requirements

Before getting started, make sure you have created a `.env` file with the following information:
- `OPENAI_API_KEY`: Your OpenAI API key for accessing Generative AI services.
- `WCS_DEMO_URL`: Cluster URL for the Weaviate vector database.
- `WCS_DEMO_RO_KEY`: API key for accessing the Weaviate vector database.
- `USER_AGENT`: User agent string for HTTP requests.


## Docker Setup

The included `Dockerfile` is configured to set up your Python environment, install dependencies, and run the FastAPI application. Here’s how to use it:

### Building the Docker Image

To build the Docker image from the `Dockerfile`, run the following command in your terminal:

```bash
docker build -t app .
```

After building the image, you can run the application in a Docker container using:

```bash
docker run -p 8000:8000 app
```



