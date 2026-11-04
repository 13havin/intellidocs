from sqlalchemy import BIGINT, Column, VARCHAR, TIMESTAMP, func, Identity
from sqlalchemy.orm import relationship
from app.db.database import Base

class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(BIGINT, Identity(),primary_key=True, index=True)
    name = Column(VARCHAR(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    workspace_members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")