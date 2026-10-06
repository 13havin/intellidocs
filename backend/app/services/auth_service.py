from datetime import timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from psycopg2.errors import UniqueViolation

from app.models.user import User
from app.schemas.users import UserCreate
from app.schemas.auth import UserLogin
from app.core.security import verify_password, hash_password
from app.core.tokens import create_access_token
from app.services.user_service import create_user
from app.services.exceptions import EmailAlreadyExistsError

def authenticate_user(db: Session, credentials: UserLogin) -> User | None:
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if user is None: 
        return None
    
    if not verify_password(credentials.password, user.password):
        return None
    
    return user

def register_user(db: Session, user: UserCreate):
    try:
        existing_user = db.query(User).filter(
            User.email == user.email
        ).first()
        
        if existing_user is not None:
            raise EmailAlreadyExistsError()
        
        db_user = create_user(db, name=user.name, email=user.email, password_hash=hash_password(user.password))
        db.commit()
        
    except IntegrityError as exc:
        db.rollback()
        
        if(
            isinstance(exc.orig, UniqueViolation)
            and exc.orig.diag.constraint_name == "ix_users_email"
        ):
            raise EmailAlreadyExistsError() from exc
        raise
    except Exception:
        db.rollback()
        raise
    
    db.refresh(db_user)
    return db_user

def login_user(db: Session, credentials: UserLogin):
    user = authenticate_user(db, credentials)
    
    if user is None:
        return None
    
    return create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=30)
    )