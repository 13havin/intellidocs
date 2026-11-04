from sqlalchemy import BIGINT, Column, VARCHAR, TIMESTAMP, func
from sqlalchemy.orm import relationship
from app.db.database import Base

class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(BIGINT, primary_key=True, index=True)
    name = Column(VARCHAR(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    workspace_members = relationship("WorkspaceMember", backref="workspace", cascade="all, delete-orphan")