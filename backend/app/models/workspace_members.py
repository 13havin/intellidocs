from sqlalchemy import BIGINT, Column, VARCHAR, TIMESTAMP, ForeignKey, func, CheckConstraint, UniqueConstraint
from app.db.database import Base

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
    id = Column(BIGINT, primary_key=True, index=True)
    workspace_id = Column(BIGINT, ForeignKey("workspaces.id"), nullable=False)
    user_id = Column(BIGINT, ForeignKey("users.id"), nullable=False)
    role = Column(VARCHAR(50), CheckConstraint("role IN ('owner', 'editor', 'viewer')"), nullable=False)
    joined_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    