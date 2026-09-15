from fastapi import APIRouter, Depends

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/health")
def get_health():
    return {"status": "healthy"}