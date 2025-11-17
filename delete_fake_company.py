from qdrant_client import QdrantClient
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not QDRANT_URL or not QDRANT_API_KEY:
    raise RuntimeError(
        f"Missing Qdrant config. "
        f"QDRANT_URL={QDRANT_URL!r}, QDRANT_API_KEY set={bool(QDRANT_API_KEY)}. "
        f"Check your .env file."
    )

print(f"Using Qdrant URL: {QDRANT_URL}")

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
)

client.delete_collection("fake_company")
print("Deleted collection 'fake_company'")
