from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "environment": "production"}


@router.get("/hello")
async def hello():
    """Sample endpoint returning a greeting."""
    return {"message": "Hello from FastAPI! 🚀"}
