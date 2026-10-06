from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.schemas.users import UserResponse, UserCreate
from app.schemas.auth import UserLogin
from app.services.auth_service import login_user, register_user
from app.dependencies import get_db
from app.models.user import User
from app.services.exceptions import EmailAlreadyExistsError

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db),
):
    credentials = UserLogin(email=form_data.username, password=form_data.password)
    access_token = login_user(db, credentials)
    
    if access_token is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return {
        "access_token": access_token,
        "token_type": "Bearer"
    }


@router.post("/register", response_model=UserResponse, status_code=201)
def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        return register_user(db, user)
    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        ) from None