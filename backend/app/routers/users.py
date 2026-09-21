from fastapi import APIRouter
from app.schemas.users import UserBase, UserCreate
router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.post("/", response_model=UserBase, status_code=201)
def create_user(user: UserCreate):
    return UserBase(id=1, name=user.name, email=user.email)