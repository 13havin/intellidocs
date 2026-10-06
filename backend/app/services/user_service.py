from sqlalchemy.orm import Session
from app.models.user import User
from app.core.security import hash_password

def create_user(db: Session, name: str, email: str, password_hash: str) -> User:
    db_user = User(name=name, email=email, password=password_hash)
    db.add(db_user)
    db.flush()
    return db_user