from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import InvalidTokenError

from app.core.config import SECRET_KEY, ALGORITHM
from app.schemas.auth import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    payload = jwt.decode(
        token, 
        SECRET_KEY, 
        algorithms=[ALGORITHM],
    )
    email: str = payload.get("sub")
    if not isinstance(email, str) or not email:
        raise InvalidTokenError("Invalid token: missing subject")
    return TokenData(email=email)
