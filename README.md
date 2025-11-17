# Exceeded Tokens API

A FastAPI application for processing PDF documents, generating embeddings using OpenAI, and storing them in Qdrant vector database.

## Requirements

- Python 3.13+ (compatible with Python 3.13)
- OpenAI API Key
- Qdrant API Key and URL

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

3. Set up environment variables:

Create a `.env` file in the root directory with the following variables:

```env
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Qdrant Configuration
QDRANT_API_KEY=your_qdrant_api_key_here
QDRANT_URL=https://your-qdrant-instance.cloud.qdrant.io:6333

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_DEFAULT_COLLECTION=collection_to_query_by_default
```

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
- `POST /api/v1/{collection}/upload` - Upload PDF file and generate embeddings
- `POST /api/v1/{collection}/query` - Query a collection using RAG (Retrieval Augmented Generation)
- `POST /webhooks/telegram` - Telegram webhook for document queries

### PDF Upload Endpoint

The `/api/v1/{collection}/upload` endpoint accepts a PDF file, extracts text from each page, generates embeddings using OpenAI's `text-embedding-3-small` model, and stores them in the specified Qdrant collection.

**Request:**

- Method: `POST`
- Path parameter: `collection` - Name of the Qdrant collection to store embeddings
- Body: `multipart/form-data` with a PDF file

**Example using curl:**

```bash
curl -X POST "http://localhost:8000/api/v1/my_collection/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/document.pdf"
```

**Response:**

```json
{
  "message": "PDF processed and uploaded successfully",
  "filename": "document.pdf",
  "pages_processed": 10,
  "embeddings_generated": 10,
  "collection": "my_collection"
}
```

**Features:**

- Extracts text from each page of the PDF
- Generates vector embeddings using OpenAI's `text-embedding-3-small` model (1536 dimensions)
- Automatically creates Qdrant collection if it doesn't exist
- Stores each page as a separate vector with metadata:
  - `filename`: Original PDF filename
  - `page_number`: Page number (1-indexed)
  - `text`: Extracted text content
  - `total_pages`: Total number of pages in the PDF

### RAG Query Endpoint

The `/api/v1/{collection}/query` endpoint allows you to perform semantic search on a collection using natural language queries. This is the core RAG (Retrieval Augmented Generation) functionality that enables LLMs to query your documents.

**Request:**

- Method: `POST`
- Path parameter: `collection` - Name of the Qdrant collection to query
- Body: `application/json`

```json
{
  "query": "What is the main topic of this document?",
  "limit": 5,
  "score_threshold": 0.7
}
```

**Request Parameters:**

- `query` (required): The search query in natural language
- `limit` (optional, default: 5): Maximum number of results to return (1-50)
- `score_threshold` (optional): Minimum similarity score threshold (0-1). Only results with scores above this threshold will be returned

**Example using curl:**

```bash
curl -X POST "http://localhost:8000/api/v1/my_collection/query" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the key features of the product?",
    "limit": 3,
    "score_threshold": 0.5
  }'
```

**Example using Python:**

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/my_collection/query",
    json={
        "query": "What are the key features of the product?",
        "limit": 3,
        "score_threshold": 0.5
    }
)

data = response.json()
print(f"Found {data['total_results']} results:")
for result in data['results']:
    print(f"\nScore: {result['score']:.4f}")
    print(f"Source: {result['filename']}, Page {result['page_number']}")
    print(f"Text: {result['text'][:200]}...")
```

**Response:**

```json
{
  "query": "What are the key features of the product?",
  "collection": "my_collection",
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "score": 0.8756,
      "filename": "document.pdf",
      "page_number": 3,
      "text": "Our product features include...",
      "total_pages": 10
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "score": 0.8234,
      "filename": "document.pdf",
      "page_number": 5,
      "text": "Additional capabilities are...",
      "total_pages": 10
    }
  ],
  "total_results": 2
}
```

**Response Fields:**

- `query`: The original search query
- `collection`: The collection that was searched
- `results`: Array of search results, sorted by relevance (highest score first)
  - `id`: Unique identifier of the vector
  - `score`: Similarity score (0-1, higher is more relevant)
  - `filename`: Source PDF filename
  - `page_number`: Page number in the source document
  - `text`: The text content from that page
  - `total_pages`: Total pages in the source document
- `total_results`: Number of results returned

**Use Cases:**

- **LLM Context Retrieval**: Fetch relevant context for LLM prompts
- **Document Q&A**: Answer questions based on document content
- **Semantic Search**: Find relevant information using natural language
- **Content Discovery**: Explore documents without reading them entirely

**Integration with LLMs:**

This endpoint is designed to work seamlessly with LLMs. Here's a typical workflow:

1. User asks a question
2. Call this endpoint to retrieve relevant context from your documents
3. Combine the retrieved context with the user's question
4. Send to an LLM (like GPT-4) for a comprehensive answer

Example:

```python
import openai

# Step 1: Get relevant context
response = requests.post(
    "http://localhost:8000/api/v1/my_collection/query",
    json={"query": "What is the company's return policy?", "limit": 3}
)
contexts = [r['text'] for r in response.json()['results']]

# Step 2: Create prompt with context
prompt = f"""Based on the following context, answer the question.

Context:
{chr(10).join(contexts)}

Question: What is the company's return policy?

Answer:"""

# Step 3: Get answer from LLM
completion = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}]
)
print(completion.choices[0].message.content)
```

## Project Structure

```
.
├── main.py                      # Main FastAPI application
├── config.py                    # Configuration and client initialization
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables (create this)
├── routers/                     # API route handlers
│   ├── health.py               # Health check endpoints
│   ├── upload.py               # PDF upload and processing endpoints
│   ├── query.py                # RAG query endpoints
│   └── telegram.py             # Telegram webhook integration
├── services/                    # Business logic services
│   ├── pdf_service.py          # PDF text extraction
│   ├── embedding_service.py    # OpenAI embedding generation
│   └── qdrant_service.py       # Qdrant vector database operations
├── resources/                   # Sample resources directory
│   └── fake_company.pdf        # Sample PDF file
└── README.md                   # This file
```

## Telegram Bot Integration (optional)

1. **Create a bot** using [@BotFather](https://t.me/BotFather) and copy the token.
2. **Update `.env`** with `TELEGRAM_BOT_TOKEN` and set `TELEGRAM_DEFAULT_COLLECTION` to the Qdrant collection you want queried when users do not specify one.
3. **Expose your FastAPI app** publicly (e.g., HTTPS domain, ngrok, Cloudflare Tunnel).
4. **Set the webhook**:
   ```bash
   curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
        -d "url=https://your-domain.com/webhooks/telegram"
   ```
5. **Use the bot**:
   - Send any question to search the default collection.
   - Use `collection::your question` to target a specific collection.
   - Send `/start` to see usage instructions.

The webhook handler reuses the same embedding + Qdrant workflow as the HTTP API, so all uploaded documents are immediately searchable from Telegram.

## Dependencies

- **fastapi**: Web framework for building APIs
- **uvicorn**: ASGI server for running FastAPI
- **pydantic**: Data validation using Python type annotations
- **python-multipart**: Support for form data and file uploads
- **qdrant-client**: Client library for Qdrant vector database
- **openai**: OpenAI API client for generating embeddings
- **pypdf2**: PDF file reader and text extraction
- **python-dotenv**: Environment variable management
- **httpx**: Async HTTP client used for Telegram interactions
