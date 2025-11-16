"""PDF upload and processing endpoints"""

import logging
from fastapi import APIRouter, UploadFile, HTTPException
from services.pdf_service import extract_text_from_pdf
from services.embedding_service import generate_embeddings
from services.qdrant_service import store_embeddings
from config import qdrant_client, openai_client

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/v1", tags=["upload"])


@router.post("/{collection}/upload")
async def upload_to_qdrant(collection: str, file: UploadFile):
    """
    Upload a PDF file, extract text from each page, generate embeddings,
    and store them in Qdrant
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

    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        logger.info(
            f"=== Starting upload process for file: {file.filename} to collection: {collection} ==="
        )

        # Read PDF file
        logger.info("Reading PDF file...")
        pdf_bytes = await file.read()
        logger.info(f"Read {len(pdf_bytes)} bytes from PDF file")

        # Extract text from each page
        logger.info("Extracting text from PDF...")
        pages_data = extract_text_from_pdf(pdf_bytes)
        logger.info(f"Extracted text from {len(pages_data)} pages")

        if not pages_data:
            raise HTTPException(status_code=400, detail="No text found in PDF")

        # Generate embeddings for all pages
        logger.info("Generating embeddings...")
        texts = [page["text"] for page in pages_data]
        logger.info(f"Prepared {len(texts)} text chunks for embedding")
        embeddings = generate_embeddings(texts, openai_client)
        logger.info(f"Generated {len(embeddings)} embeddings")

        # Store embeddings in Qdrant
        logger.info("Storing embeddings in Qdrant...")
        store_embeddings(
            qdrant_client=qdrant_client,
            collection=collection,
            pages_data=pages_data,
            embeddings=embeddings,
            filename=file.filename,
            logger=logger,
        )

        logger.info(
            f"=== Upload process completed successfully for {file.filename} ==="
        )

        return {
            "message": "PDF processed and uploaded successfully",
            "filename": file.filename,
            "pages_processed": len(pages_data),
            "embeddings_generated": len(embeddings),
            "collection": collection,
        }

    except HTTPException as http_exc:
        logger.error(f"HTTP exception during upload: {http_exc.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing PDF: {str(e)}")
        logger.exception("Full exception trace:")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")
