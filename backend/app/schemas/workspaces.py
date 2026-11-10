from pydantic import BaseModel, field_validator
from datetime import datetime

class WorkspaceCreate(BaseModel):
    name: str
    @field_validator("name")
    def name_must_not_be_empty(cls, v):
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("Name must contain between 1 and 255 characters")
        return v

class WorkspaceLeave(BaseModel):
    id: int
class WorkspaceResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime