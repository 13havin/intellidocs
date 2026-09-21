from fastapi import APIRouter
from app.schemas.users import UserResponse, UserCreate
router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate):
    return UserResponse(id=1, name=user.name, email=user.email)