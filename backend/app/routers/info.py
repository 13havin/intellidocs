from fastapi import APIRouter
from app.schemas.info import InfoResponse
router = APIRouter(prefix="/api/v1/info", tags=["info"])

@router.get("/", response_model=InfoResponse)
def get_info():
    return InfoResponse(name="IntelliDocs", version="0.1.0")