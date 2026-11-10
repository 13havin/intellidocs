from pydantic import BaseModel, field_validator
from datetime import datetime

class WorkspaceCreate(BaseModel):
    name: str
    @field_validator("name")
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Name must not be empty")
        return v
    
class WorkspaceResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    
class WorkspaceMemberCreate(BaseModel):
    user_id: int
    workspace_id: int
    role: str
    
class WorkspaceMemberResponse(BaseModel):
    user_id: int
    role: str
    joined_at: datetime