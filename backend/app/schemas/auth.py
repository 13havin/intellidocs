from pydantic import BaseModel, EmailStr

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
class UserToken(BaseModel):
    access_token: str
    token_type: str
    
class TokenData(BaseModel):
    email: str