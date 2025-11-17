"""Telegram webhook integration for querying uploaded documents"""

import logging
import re
from typing import Optional, Tuple, List

import httpx
from fastapi import APIRouter, HTTPException, Request

from config import (
    TELEGRAM_API_BASE,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_DEFAULT_COLLECTION,
    openai_client,
    qdrant_client,
)
from services.embedding_service import generate_embeddings
from services.qdrant_service import search_collection

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/webhooks", tags=["telegram"])

# Hard fallback if env var is missing or wrong
DEFAULT_FALLBACK_COLLECTION = "fake_company"


async def send_telegram_message(chat_id: int, text: str) -> None:
    """Send a message back to a Telegram chat."""
    if not TELEGRAM_API_BASE:
        logger.error("Telegram API base URL is not configured")
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{TELEGRAM_API_BASE}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
    except Exception as exc:
        logger.error(f"Failed to send Telegram message: {exc}")
        logger.exception("Full exception trace when sending Telegram message:")


def parse_collection_and_query(text: str) -> Tuple[Optional[str], str]:
    """
    Allow users to specify a collection inline using the syntax:
    collection_name::your question
    """
    if "::" in text:
        collection, query = text.split("::", 1)
        return collection.strip() or None, query.strip()
    return None, text.strip()


def _choose_best_qa_result(results) -> Optional[any]:
    """
    From a list of Qdrant search results, choose the one that looks
    most like a real Q&A chunk (starts with 'Q' and contains an 'A' line).

    If none look like Q&A, fall back to the first result.
    """
    if not results:
        return None

    def qa_score(res) -> int:
        text = (res.payload.get("text") or "").strip()
        if not text:
            return 0

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return 0

        first_line = lines[0]
        has_q = first_line.startswith("Q")
        has_a = any(ln.startswith("A") for ln in lines[1:])
        long_enough = len(text) > 80

        return int(has_q) + int(has_a) + int(long_enough)

    best = max(results, key=qa_score)
    if qa_score(best) == 0:
        return results[0]

    return best


def _strip_q_prefix(line: str) -> str:
    return re.sub(r"^Q\d*\.\s*", "", line).strip()


def _strip_a_prefix(line: str) -> str:
    return re.sub(r"^A\d*\.\s*", "", line).strip()


def _format_single_qa_result(result, collection: str, query: str) -> str:
    """
    Turn a single Qdrant result into a clean chat-style answer.

    Expected text format (from your new PDF), e.g.:

        Q1. What is ... ?
        A1. Answer line 1
            bullet / more lines...

    We return ONLY the answer text, nicely cleaned.
    """
    if not result:
        return "I couldn’t find anything that answers that in your documents."

    text = (result.payload.get("text") or "").strip()
    lines: List[str] = [ln.strip() for ln in text.splitlines() if ln.strip()]

    if not lines:
        return "I found a related snippet, but it had no readable text."

    # Try to find a question line and an answer block
    # Assume first non-empty line is question ("Q...")
    q_idx = 0
    question_line = lines[q_idx]

    # Answer starts from next line
    a_idx = q_idx + 1

    # If that line itself starts with Q (malformed), just treat everything after
    # the first line as "answer-ish" content.
    if a_idx >= len(lines):
        # Just fallback: remove Q/A prefixes and send everything
        cleaned = " ".join(_strip_q_prefix(_strip_a_prefix(ln)) for ln in lines)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    # Build answer lines until next Q block (if any)
    answer_lines: List[str] = []
    for i in range(a_idx, len(lines)):
        candidate = lines[i]
        if candidate.startswith("Q") and i != a_idx:
            # next question -> stop
            break
        answer_lines.append(candidate)

    # Clean prefixes and whitespace on each line
    cleaned_answer_lines: List[str] = []
    for ln in answer_lines:
        ln = _strip_a_prefix(_strip_q_prefix(ln))
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            cleaned_answer_lines.append(ln)

    if not cleaned_answer_lines:
        # Fallback: send whole chunk, but strip prefixes
        cleaned = " ".join(_strip_q_prefix(_strip_a_prefix(ln)) for ln in lines)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    # Join answer lines with newlines (keeps bullet/paragraph structure readable)
    answer = "\n".join(cleaned_answer_lines).strip()
    return answer


def format_results_text(results, collection: str, query: str) -> str:
    """Wrapper used by the webhook code."""
    best = _choose_best_qa_result(results)
    return _format_single_qa_result(best, collection, query)


@router.post("/telegram")
async def telegram_webhook(request: Request):
    """
    Receive Telegram webhook updates and respond with RAG results.

    Text format options:
    - Plain question → searches TELEGRAM_DEFAULT_COLLECTION (or fallback)
    - collection::question → searches the named collection
    """
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="Telegram bot token not configured. Set TELEGRAM_BOT_TOKEN.",
        )

    if not (openai_client and qdrant_client):
        raise HTTPException(
            status_code=500,
            detail="Embedding or Qdrant clients not configured.",
        )

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id:
        logger.warning("Received Telegram update without chat_id: %s", update)
        return {"ok": True}

    if not text:
        await send_telegram_message(chat_id, "Please send a text message to search.")
        return {"ok": True}

    if text.startswith("/start"):
        await send_telegram_message(
            chat_id,
            (
                "Hi! Send me a question and I'll search your documents.\n"
                "Use collection::question to target a specific dataset.\n"
                "Example: fake_company::What services does UrbanVista offer?"
            ),
        )
        return {"ok": True}

    inline_collection, query_text = parse_collection_and_query(text)

    # Prefer inline collection > env default > hardcoded fallback
    collection = (
        inline_collection
        or TELEGRAM_DEFAULT_COLLECTION
        or DEFAULT_FALLBACK_COLLECTION
    )

    try:
        collections = qdrant_client.get_collections().collections
        collection_names = [col.name for col in collections]

        if collection not in collection_names:
            await send_telegram_message(
                chat_id,
                f"Collection '{collection}' not found. Available: {', '.join(collection_names)}",
            )
            return {"ok": True}

        query_embedding = generate_embeddings([query_text], openai_client)[0]
        results = search_collection(
            qdrant_client=qdrant_client,
            collection=collection,
            query_vector=query_embedding,
            limit=5,
            score_threshold=None,
            logger=logger,
        )

        response_text = format_results_text(results, collection, query_text)
        await send_telegram_message(chat_id, response_text)

    except Exception as exc:
        logger.error(f"Error handling Telegram query: {exc}")
        logger.exception("Full exception trace during Telegram query:")
        await send_telegram_message(
            chat_id, "Sorry, something went wrong while processing your request."
        )

    return {"ok": True}
