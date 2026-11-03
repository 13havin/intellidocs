from pydantic import BaseModel, EmailStr, field_validator


class UserLogin(BaseModel):
    email: EmailStr
    password: str
class UserToken(BaseModel):
    access_token: str
    token_type: str
    
class TokenData(BaseModel):
    id: int