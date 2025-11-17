"""Main FastAPI application"""

from fastapi import FastAPI
import logging
from fastapi.middleware.cors import CORSMiddleware
from routers import chat, health, upload, query, telegram


logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)

app = FastAPI(
    title="Exceeded Tokens API",
    description="A FastAPI application for processing PDFs and generating embeddings",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(query.router)
app.include_router(telegram.router)
app.include_router(chat.router)

# if __name__ == "__main__":
#     import uvicorn

#     uvicorn.run(app, host="0.0.0.0", port=8000, debug=True)
