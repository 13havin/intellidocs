from sqlalchemy import BIGINT, Column, VARCHAR, TIMESTAMP, ForeignKey, func, CheckConstraint, UniqueConstraint, Identity
from sqlalchemy.orm import relationship
from app.db.database import Base

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        CheckConstraint("role IN ('owner', 'editor', 'viewer')", name="ck_workspace_member_role")
    )
    id = Column(BIGINT, Identity(),primary_key=True, index=True)
    workspace_id = Column(BIGINT, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BIGINT, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(VARCHAR(50), nullable=False)
    joined_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    user = relationship("User", back_populates="workspace_members")
    workspace = relationship("Workspace", back_populates="workspace_members")