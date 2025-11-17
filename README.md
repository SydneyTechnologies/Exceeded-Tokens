# Exceeded Tokens API

A FastAPI application for processing PDF documents, generating embeddings using OpenAI, and storing them in a Qdrant vector database. It supports both HTTP APIs and a Telegram bot interface for asking questions over your documents.

---

## Requirements

- Python 3.10+ (works fine on 3.13)
- OpenAI API key
- Qdrant Cloud cluster (or self-hosted Qdrant) with API key + URL
- (Optional) Telegram bot token
- (Optional) ngrok / any HTTPS tunnel for webhooks

---

## Setup

### 1. Create and activate a virtual environment

~~~bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
~~~

### 2. Install dependencies

~~~bash
pip install -r requirements.txt
~~~

### 3. Configure environment variables

Create a `.env` file in the project root:

~~~bash
OPENAI_API_KEY=your-openai-api-key
QDRANT_URL=your-qdrant-url
QDRANT_API_KEY=your-qdrant-api-key

# Optional for Telegram integration
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_DEFAULT_COLLECTION=fake_company
~~~

---

## Running the Application

### Local dev server

~~~bash
uvicorn main:app --reload
~~~

The API will be available at:

- <http://localhost:8000>
- <http://localhost:8000/docs> (Swagger UI)
- <http://localhost:8000/redoc> (ReDoc)

### Optional: run with ngrok (for Telegram webhooks)

If you created a helper script like `run_with_ngrok.py`:

~~~bash
python run_with_ngrok.py
~~~

Typical behaviour:

- Starts `uvicorn main:app --host 0.0.0.0 --port 8000`
- Starts `ngrok http 8000`
- Prints your public ngrok URL so you can plug it into Telegram’s `setWebhook`.

---

## High-Level Behaviour Changes

Compared to a naïve “one vector per page” setup, this project now has:

### 1. Semantic chunking of PDFs (Q&A-aware)

- PDFs are not stored as one vector per page anymore.
- Each page is split into smaller text chunks:
  - Lines ending with `?` are treated as question headers.
  - Each question is grouped with its following answer lines until the next question or end of page.
  - Non-question lines (headings, short paragraphs) become their own small chunks.
- This is tuned for FAQ / Q&A-style docs like `fake_company_qa.pdf`.

### 2. Qdrant stores chunks, not pages

Each chunk gets:

- `filename`
- `page_number` (original PDF page, 1-based)
- `text` (one Q&A or paragraph)
- `total_pages` (currently the total number of chunks inserted for this upload)

### 3. Telegram bot with default collection + clean answers

- You can ask questions directly in Telegram.
- If the message contains `collection::question`, it will search that specific collection.
- Otherwise, it searches `TELEGRAM_DEFAULT_COLLECTION` from `.env` (with hard fallback to `"fake_company"` if env is misconfigured).
- Telegram replies now return just the best-matching chunk text (one Q&A) – no extra boilerplate like “Here’s what I found…” and no `(Source: …)` footer.

---

## API Endpoints

### Health & utility

- `GET /` – Root endpoint  
- `GET /health` – Health check

---

### PDF Upload

`POST /api/v1/{collection}/upload`

Upload a PDF, extract text, chunk it into Q&A/paragraph segments, embed each chunk with OpenAI, and store into Qdrant.

**Path parameter**

- `collection` – Target Qdrant collection name (e.g. `fake_company`).

**Body**

- `multipart/form-data` with a `file` field containing the PDF.

**Example**

~~~bash
curl -X POST "http://localhost:8000/api/v1/fake_company/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@fake_company_qa.pdf;type=application/pdf"
~~~

**Typical Response**

~~~json
{
  "message": "PDF processed and uploaded successfully",
  "filename": "fake_company_qa.pdf",
  "pages_processed": 19,
  "embeddings_generated": 19,
  "collection": "fake_company"
}
~~~

`pages_processed` and `embeddings_generated` correspond to extracted text chunks (Q&A items / paragraphs), not literal PDF pages.

---

### RAG Query Endpoint

`POST /api/v1/{collection}/query`

Perform semantic search over a Qdrant collection using OpenAI embeddings. Results correspond to the chunks created during upload.

**Request**

~~~json
{
  "query": "What is the company about?",
  "limit": 5,
  "score_threshold": 0.3
}
~~~

- `query` (**required**) – Natural language question.
- `limit` (optional, default 5) – Max number of hits to return (1–50).
- `score_threshold` (optional) – Minimum similarity score; results below this are filtered out.

**Example**

~~~bash
curl -X POST "http://localhost:8000/api/v1/fake_company/query" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the company about?", "limit": 5}'
~~~

**Typical Response**

~~~json
{
  "query": "What is the company about?",
  "collection": "fake_company",
  "results": [
    {
      "id": "73b6dd99-6449-4055-9871-8fa023e772fe",
      "score": 0.29,
      "filename": "fake_company_qa.pdf",
      "page_number": 1,
      "text": "Q1. What is UrbanVista Real Estate & Marketing Agency?\nA1. UrbanVista Real Estate & Marketing Agency is a full-service firm based in Dubai...",
      "total_pages": 19
    }
  ],
  "total_results": 1
}
~~~

This is exactly what the Telegram bot will surface (cleaned to just the `text` field).

---

## Telegram Bot Integration

The Telegram webhook reuses the same embedding + Qdrant flow as the HTTP API.

### How messages are interpreted

- **Plain question**

  ~~~text
  What is the company about?
  ~~~

  → Searches `TELEGRAM_DEFAULT_COLLECTION` from `.env` (e.g., `fake_company`).

- **Targeting a specific collection**

  ~~~text
  fake_company::What services does UrbanVista offer?
  ~~~

  → Uses `fake_company` as the collection, regardless of the default.

- **`/start`**

  Sends a short help message explaining usage.

---

### Answer formatting (current behaviour)

When you ask a question, the bot:

1. Generates an embedding for your question.  
2. Does a vector search in Qdrant (`limit=3` by default).  
3. Takes the single best result.  
4. Returns only the chunk text (no prefix, no source footer), e.g.:

~~~text
Q1. What is UrbanVista Real Estate & Marketing Agency?
A1. UrbanVista Real Estate & Marketing Agency is a full-service firm based in Dubai that ...
~~~

This keeps the conversation in Telegram looking like normal chat, but backed by your Qdrant collection.

---

### Setting the webhook (once you have a public URL)

~~~bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  -d "url=https://<your-public-domain-or-ngrok-url>/webhooks/telegram"
~~~

---

## PDF Processing Details (`services/pdf_service.py`)

To make Q&A documents work well with RAG and Telegram:

- We use **PyPDF2** to extract text from each page.
- For each page:
  - Split into non-empty lines.
  - If a line ends with `?`, it’s treated as a question line.
  - That question is grouped with subsequent lines as its answer block, until the next question or end of page.
  - Non-question lines (headings, standalone blurbs) become their own chunk.
- If, for some reason, no chunks are detected on a page, the whole page text is stored as a single chunk (fallback).
- Each chunk is then sent to `embedding_service.generate_embeddings()` and persisted via `qdrant_service.store_embeddings()`.

This is why a Q&A-formatted file like `fake_company_qa.pdf` works especially well: each FAQ entry becomes one clean vector that the query & Telegram layers can retrieve directly.

---

## Project Structure

~~~text
.
├── main.py                   # FastAPI app, routers mounted here
├── config.py                 # Loads .env, initializes OpenAI & Qdrant clients
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (not committed)
├── routers/
│   ├── health.py             # / and /health endpoints
│   ├── upload.py             # /api/v1/{collection}/upload
│   ├── query.py              # /api/v1/{collection}/query
│   └── telegram.py           # /webhooks/telegram
├── services/
│   ├── pdf_service.py        # PDF -> Q&A/paragraph chunks
│   ├── embedding_service.py  # OpenAI embedding wrapper
│   └── qdrant_service.py     # Qdrant collection + search helpers
├── resources/
│   └── fake_company_qa.pdf   # Sample Q&A-style PDF
├── run_with_ngrok.py         # (optional) Helper to run uvicorn + ngrok
└── README.md                 # This file
~~~
