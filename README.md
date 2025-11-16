# Exceeded Tokens API

A FastAPI application for handling exceeded tokens scenarios.

## Requirements

- Python 3.13+ (compatible with Python 3.13)

## Setup

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

> **Note:** This project uses pydantic 2.9+ which is compatible with Python 3.13. Earlier versions of pydantic may have compatibility issues with Python 3.13.

## Running the Application

Start the development server:

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, you can access:

- Interactive API docs (Swagger UI): `http://localhost:8000/docs`
- Alternative API docs (ReDoc): `http://localhost:8000/redoc`

## Available Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check endpoint
- `GET /api/v1/hello/{name}` - Sample greeting endpoint

## Project Structure

```
.
├── main.py              # Main FastAPI application
├── requirements.txt     # Python dependencies
└── README.md           # This file
```
