"""Telegram webhook integration for querying uploaded documents"""

import logging
import json
import re
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import (
    TELEGRAM_API_BASE,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_DEFAULT_COLLECTION,
)

OPUS_BASE = "https://operator.opus.com"

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/v1/telegram", tags=["telegram"])


class TelegramMessage(BaseModel):
    """Telegram message model"""

    message_id: int
    text: Optional[str] = None
    chat: Dict[str, Any]
    from_user: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "alias_generator": lambda field_name: field_name.replace(
                "from_user", "from"
            )
        }


class TelegramUpdate(BaseModel):
    """Telegram webhook update model"""

    update_id: int
    message: Optional[TelegramMessage] = None


async def send_telegram_message(
    chat_id: int, text: str, reply_to_message_id: Optional[int] = None
):
    """Send a message via Telegram Bot API"""
    if not TELEGRAM_API_BASE:
        raise HTTPException(status_code=500, detail="Telegram bot not configured")

    url = f"{TELEGRAM_API_BASE}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        if response.status_code != 200:
            logger.error(f"Failed to send message: {response.text}")
            raise HTTPException(status_code=500, detail="Failed to send message")
        return response.json()


def _extract_email_or_phone(message: Dict[str, Any], text: str) -> str:

    # 1. Contact-based phone number (when user shares contact)
    contact = message.get("contact") or {}
    phone_from_contact = contact.get("phone_number")
    if phone_from_contact:
        return phone_from_contact

    # 2. Email in free-form text
    if text:
        email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        if email_match:
            return email_match.group(0)

        # 3. Phone number in free-form text (very permissive)
        phone_match = re.search(r"\+?\d[\d\-\s]{7,}\d", text)
        if phone_match:
            # Normalize: keep digits and leading +
            raw = phone_match.group(0)
            normalized = re.sub(r"[^\d+]", "", raw)
            return normalized

    # 4/5. Fallback to Telegram user metadata
    from_user = message.get("from") or {}
    username = from_user.get("username")
    if username:
        return username

    from_id = from_user.get("id")
    if from_id:
        return str(from_id)

    # 6. Final fallback: chat id
    chat_id = (message.get("chat") or {}).get("id")
    return str(chat_id)


async def call_chat_endpoint(
    message: str, session_id: str, api_base_url: str = "http://localhost:8000"
) -> str:
    """Call the internal chat endpoint to get a response"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Send the message to the chat endpoint
            response = await client.post(
                f"{api_base_url}/api/v1/chat",
                json={
                    "session_id": session_id,
                    "messages": [{"role": "user", "content": message}],
                },
            )

            if response.status_code == 200:
                result = response.json()
                # Return a simple acknowledgment or extract response from the result
                return (
                    f"✅ Message received: "
                    f"{result.get('message', 'Message processed successfully')}"
                )
            else:
                logger.error(
                    f"Chat endpoint returned {response.status_code}: {response.text}"
                )
                return "❌ Sorry, I couldn't process your message at this time."

    except httpx.TimeoutException:
        logger.error("Timeout calling chat endpoint")
        return "⏱️ Request timed out. Please try again."
    except Exception as e:
        logger.error(f"Error calling chat endpoint: {str(e)}")
        return f"❌ Error: {str(e)}"


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Handle incoming Telegram webhook updates.

    This endpoint receives messages from Telegram users and responds with
    relevant information from the configured document collection.
    """
    try:
        # Parse the webhook payload
        body = await request.json()
        logger.info(f"Received Telegram update: {json.dumps(body, indent=2)}")

        # Extract message data
        update = body
        message = update.get("message")

        if not message:
            logger.info("No message in update, ignoring")
            return {"ok": True}

        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        text = (message.get("text") or "").strip()

        if not text:
            logger.info("Empty message, ignoring")
            return {"ok": True}

        # Send "typing" action to show bot is processing
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{TELEGRAM_API_BASE}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"},
            )

        # Use person's phone/email (if available) as session_id, with sensible fallbacks
        identifier = _extract_email_or_phone(message, text)
        session_id = f"telegram_{identifier}"

        logger.info(f"Using session_id={session_id} for incoming Telegram message")

        # Call the chat endpoint to get a response
        response_text = await call_chat_endpoint(text, session_id)

        # Send the response back to the user
        await send_telegram_message(
            chat_id, response_text, reply_to_message_id=message_id
        )

        return {"ok": True}

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        logger.exception("Full exception trace:")

        # Try to send error message to user if we have a chat_id
        try:
            if "chat_id" in locals():
                error_message = "❌ Sorry, I encountered an error processing your request. Please try again later."
                await send_telegram_message(chat_id, error_message)
        except:
            pass

        return {"ok": False, "error": str(e)}
