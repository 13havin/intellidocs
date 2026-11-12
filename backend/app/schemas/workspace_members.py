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
class WorkspaceMemberUpdate(BaseModel):
    role: RoleEnum
class WorkspaceMemberDelete(BaseModel):
    workspace_id: int
    
class WorkspaceMemberResponse(BaseModel):
    email: EmailStr
    role: RoleEnum
    joined_at: datetime
    