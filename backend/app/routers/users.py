from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.users import UserResponse, UserCreate
from app.services.user_service import create_user
from app.dependencies import get_db
from app.models.user import User

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=201)
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    if (db.query(User).filter(User.email == user.email).first()):
        raise HTTPException(status_code=409, detail="Email already registered")
    return create_user(db, user)

@router.get("/{user_id}", response_model=UserResponse, status_code=200)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user =  db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user