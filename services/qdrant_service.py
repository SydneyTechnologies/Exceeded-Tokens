"""Qdrant vector database service"""

from typing import List, Dict, Optional
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, ScoredPoint


def store_embeddings(
    qdrant_client: QdrantClient,
    collection: str,
    pages_data: List[Dict[str, any]],
    embeddings: List[List[float]],
    filename: str,
    logger,
) -> None:
    """Store embeddings in Qdrant collection"""
    logger.info("=== ENTERED store_embeddings function ===")
    logger.info(
        f"Collection: {collection}, Filename: {filename}, Pages: {len(pages_data)}, Embeddings: {len(embeddings)}"
    )

    # Ensure collection exists
    logger.info("Fetching existing collections from Qdrant...")
    collections = qdrant_client.get_collections().collections
    logger.info(f"Existing collections: {[col.name for col in collections]}")
    collection_names = [col.name for col in collections]

    if collection not in collection_names:
        logger.info(
            f"Collection '{collection}' does not exist. Creating new collection..."
        )
        # Create collection with appropriate vector size (text-embedding-3-small uses 1536 dimensions)
        qdrant_client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
        logger.info(f"Successfully created collection '{collection}'")
    else:
        logger.info(f"Collection '{collection}' already exists")

    # Prepare points for upload
    logger.info(f"Preparing points for upload...")
    points = []
    for i, (page_data, embedding) in enumerate(zip(pages_data, embeddings)):
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "filename": filename,
                "page_number": page_data["page_number"],
                "text": page_data["text"],
                "total_pages": len(pages_data),
            },
        )
        points.append(point)
        if (i + 1) % 10 == 0 or (i + 1) == len(pages_data):
            logger.info(f"Prepared {i + 1}/{len(pages_data)} points")

    logger.info(
        f"Completed preparing {len(points)} points for collection '{collection}'"
    )

    # Upload to Qdrant
    logger.info(
        f"Starting upsert of {len(points)} points to Qdrant collection '{collection}'..."
    )
    try:
        result = qdrant_client.upsert(collection_name=collection, points=points)
        logger.info(
            f"Successfully upserted {len(points)} points to collection '{collection}'"
        )
        logger.info(f"Upsert operation result: {result}")
        logger.info("=== COMPLETED store_embeddings function ===")
    except Exception as e:
        logger.error(f"Failed to upsert points to Qdrant: {e}")
        logger.exception("Full exception trace:")
        raise


def search_collection(
    qdrant_client: QdrantClient,
    collection: str,
    query_vector: List[float],
    limit: int = 5,
    score_threshold: Optional[float] = None,
    logger=None,
) -> List[ScoredPoint]:
    """
    Search a Qdrant collection for vectors similar to the query vector
    
    Args:
        qdrant_client: The Qdrant client instance
        collection: Name of the collection to search
        query_vector: The embedding vector to search for
        limit: Maximum number of results to return
        score_threshold: Minimum similarity score (0-1) for results
        logger: Logger instance for logging
        
    Returns:
        List of ScoredPoint objects containing the search results
    """
    if logger:
        logger.info(f"=== ENTERED search_collection function ===")
        logger.info(f"Collection: {collection}, Limit: {limit}, Score threshold: {score_threshold}")
    
    try:
        search_params = {
            "collection_name": collection,
            "query_vector": query_vector,
            "limit": limit,
        }
        
        if score_threshold is not None:
            search_params["score_threshold"] = score_threshold
        
        if logger:
            logger.info(f"Executing search with params: collection={collection}, limit={limit}")
        
        results = qdrant_client.search(**search_params)
        
        if logger:
            logger.info(f"Search returned {len(results)} results")
            if results:
                logger.info(f"Top result score: {results[0].score:.4f}")
            logger.info("=== COMPLETED search_collection function ===")
        
        return results
        
    except Exception as e:
        if logger:
            logger.error(f"Failed to search Qdrant collection: {e}")
            logger.exception("Full exception trace:")
        raise
