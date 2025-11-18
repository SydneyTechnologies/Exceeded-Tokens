import json
from typing import List
from config import redis_client
from pydantic import BaseModel
from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/v1", tags=["chat"])


class SessionRequest(BaseModel):
    session_id: str


class Message(BaseModel):
    role: str
    content: str


class ChatObject(BaseModel):
    session_id: str
    messages: List[Message]


@router.post("/chat/history")
async def get_chat_history(session_request: SessionRequest):
    session_id = session_request.session_id
    # Use pipeline to get data and check TTL in one round-trip
    pipe = redis_client.pipeline()
    pipe.lrange(session_id, 0, -1)
    pipe.ttl(session_id)
    chat_history, ttl = pipe.execute()

    # Decode bytes to JSON objects
    decoded_history = [json.loads(msg.decode("utf-8")) for msg in chat_history]
    return {"messages": decoded_history, "expires_in_seconds": ttl if ttl > 0 else None}


@router.post("/chat")
async def add_message_to_chat(chat_object: ChatObject):
    session_id = chat_object.session_id
    messages = chat_object.messages
    # Use pipeline to batch all operations into a single network round-trip
    pipe = redis_client.pipeline()

    # Serialize all messages
    serialized_messages = [msg.model_dump_json() for msg in messages]

    # Add all messages at once using rpush with unpacking
    if serialized_messages:
        pipe.rpush(session_id, *serialized_messages)

    # Set expiration to 24 hours (86400 seconds) only if not already set
    # NX means set expiry only if the key has no expiry
    pipe.expire(session_id, 86400, nx=True)

    pipe.execute()

    return {"message": f"Added {len(messages)} message(s) to chat history"}


@router.delete("/chat")
async def delete_chat_history(session_request: SessionRequest):
    session_id = session_request.session_id
    redis_client.delete(session_id)
    return {"message": "Chat history deleted"}
