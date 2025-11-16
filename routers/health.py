"""Health check and basic endpoints"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to Exceeded Tokens API"}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@router.get("/api/v1/hello/{name}")
async def hello(name: str):
    """Sample endpoint with path parameter"""
    return {"message": f"Hello, {name}!"}
