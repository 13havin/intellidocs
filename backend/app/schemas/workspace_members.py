from enum import Enum
from pydantic import BaseModel, field_validator, EmailStr
from datetime import datetime

class RoleEnum(str, Enum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"
    
class WorkspaceMemberCreate(BaseModel):
    email: EmailStr
    role: RoleEnum
    @field_validator("role")
    def validate_role(cls, v):
        if v not in RoleEnum:
            raise ValueError("Invalid role")
        return v
class WorkspaceMemberUpdate(BaseModel):
    role: RoleEnum
    @field_validator("role")
    def validate_role(cls, v):
        if v not in RoleEnum:
            raise ValueError("Invalid role")
        return v
    
class WorkspaceMemberDelete(BaseModel):
    workspace_id: int
    
class WorkspaceMemberResponse(BaseModel):
    user_id: int
    role: RoleEnum
    joined_at: datetime
    