from pydantic import BaseModel, field_validator
from datetime import datetime

class WorkspaceMemberCreate(BaseModel):
    user_id: int
    workspace_id: int
    role: str
    
class WorkspaceMemberUpdate(BaseModel):
    workspace_id: int
    role: str
    
class WorkspaceMemberDelete(BaseModel):
    user_id: int
    workspace_id: int
    
class WorkspaceMemberResponse(BaseModel):
    user_id: int
    role: str
    joined_at: datetime