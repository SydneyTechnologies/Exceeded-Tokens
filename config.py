"""Application configuration and client initialization"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from openai import OpenAI

# Force .env to override any existing env vars (like old TELEGRAM_DEFAULT_COLLECTION)
load_dotenv(override=True)

# --- raw env values ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_DEFAULT_COLLECTION = os.getenv("TELEGRAM_DEFAULT_COLLECTION")

# Debug print (optional but useful right now)
print(f"[config] TELEGRAM_DEFAULT_COLLECTION = {TELEGRAM_DEFAULT_COLLECTION!r}")

# --- clients ---
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

qdrant_client = (
    QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    if QDRANT_API_KEY and QDRANT_URL
    else None
)

# --- Telegram base URL for API calls ---
TELEGRAM_API_BASE = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else None
)
