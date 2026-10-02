from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.schemas.users import UserResponse, UserCreate
from app.services.user_service import create_user
from app.dependencies import get_db

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=201)
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    return create_user(db, user)