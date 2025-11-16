"""Embedding generation service"""

import logging
from typing import List
from openai import OpenAI

logger = logging.getLogger("uvicorn.error")


def generate_embeddings(texts: List[str], openai_client: OpenAI) -> List[List[float]]:
    """Generate embeddings using OpenAI's text-embedding-3-small model"""
    logger.info(f"Starting embedding generation for {len(texts)} text chunks")
    
    if not openai_client:
        logger.error("OpenAI client not initialized")
        raise ValueError("OpenAI client not initialized")

    # Log sample sizes
    total_chars = sum(len(text) for text in texts)
    logger.info(f"Total characters to embed: {total_chars}")
    
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small", input=texts
        )
        embeddings = [item.embedding for item in response.data]
        logger.info(f"Successfully generated {len(embeddings)} embeddings (dimension: {len(embeddings[0]) if embeddings else 0})")
        return embeddings
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        logger.exception("Full exception trace:")
        raise
