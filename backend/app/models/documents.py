from sqlalchemy import BIGINT, Column, VARCHAR, TIMESTAMP, ForeignKey, func, CheckConstraint, Identity
from sqlalchemy.orm import relationship
from app.db.database import Base

class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("file_type IN ('pdf', 'txt', 'md')", name="ck_file_type"),
        CheckConstraint("file_size > 0", name="ck_file_size")
    )
    id = Column(BIGINT, Identity(),primary_key=True)
    name = Column(VARCHAR(255), nullable=False)
    file_type = Column(VARCHAR(50), nullable=False)
    file_size = Column(BIGINT, nullable=False)
    storage_key = Column(VARCHAR(255), nullable=False, unique=True)
    workspace_id = Column(BIGINT, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by = Column(BIGINT, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    
    user = relationship("User", back_populates="documents")
    workspace = relationship("Workspace", back_populates="documents")