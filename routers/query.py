"""RAG query endpoints for searching collections"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.embedding_service import generate_embeddings
from services.qdrant_service import search_collection
from config import qdrant_client, openai_client

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/v1", tags=["query"])


class QueryRequest(BaseModel):
    """Request model for RAG queries"""

    query: str = Field(..., description="The search query text", min_length=1)
    limit: int = Field(
        default=5, description="Number of results to return", ge=1, le=50
    )
    score_threshold: Optional[float] = Field(
        default=None,
        description="Minimum similarity score threshold (0-1)",
        ge=0.0,
        le=1.0,
    )


class SearchResult(BaseModel):
    """Model for individual search result"""

    id: str
    score: float
    filename: str
    page_number: int
    text: str
    total_pages: int


class QueryResponse(BaseModel):
    """Response model for RAG queries"""

    query: str
    collection: str
    results: List[SearchResult]
    total_results: int


@router.post("/{collection}/query", response_model=QueryResponse)
async def query_collection(collection: str, request: QueryRequest):
    """
    Query a specific collection using RAG (Retrieval Augmented Generation).

    This endpoint:
    1. Takes a natural language query
    2. Generates an embedding for the query
    3. Searches the specified collection for semantically similar content
    4. Returns the most relevant results with their context

    Args:
        collection: Name of the Qdrant collection to search
        request: Query parameters including the search text, limit, and score threshold

    Returns:
        QueryResponse containing the query, collection name, and list of relevant results
    """
    # Validate clients are initialized
    if not qdrant_client:
        raise HTTPException(
            status_code=500,
            detail="Qdrant client not initialized. Check QDRANT_API_KEY and QDRANT_URL environment variables.",
        )

    if not openai_client:
        raise HTTPException(
            status_code=500,
            detail="OpenAI client not initialized. Check OPENAI_API_KEY environment variable.",
        )

    try:
        logger.info(f"=== Starting RAG query for collection: {collection} ===")
        logger.info(f"Query: {request.query}")
        logger.info(
            f"Limit: {request.limit}, Score threshold: {request.score_threshold}"
        )

        # Check if collection exists
        collections = qdrant_client.get_collections().collections
        collection_names = [col.name for col in collections]

        if collection not in collection_names:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{collection}' not found. Available collections: {collection_names}",
            )

        # Generate embedding for the query
        logger.info("Generating embedding for query...")
        query_embedding = generate_embeddings([request.query], openai_client)[0]
        logger.info(f"Generated query embedding with dimension: {len(query_embedding)}")

        # Search the collection
        logger.info(f"Searching collection '{collection}'...")
        search_results = search_collection(
            qdrant_client=qdrant_client,
            collection=collection,
            query_vector=query_embedding,
            limit=request.limit,
            score_threshold=request.score_threshold,
            logger=logger,
        )

        logger.info(f"Found {len(search_results)} results")

        # Format results
        formatted_results = [
            SearchResult(
                id=result.id,
                score=result.score,
                filename=result.payload.get("filename", "unknown"),
                page_number=result.payload.get("page_number", 0),
                text=result.payload.get("text", ""),
                total_pages=result.payload.get("total_pages", 0),
            )
            for result in search_results
        ]

        logger.info(
            f"=== RAG query completed successfully for collection: {collection} ==="
        )

        return QueryResponse(
            query=request.query,
            collection=collection,
            results=formatted_results,
            total_results=len(formatted_results),
        )

    except HTTPException as http_exc:
        logger.error(f"HTTP exception during query: {http_exc.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during query: {str(e)}")
        logger.exception("Full exception trace:")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
