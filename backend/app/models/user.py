from sqlalchemy import BIGINT, Column, String, VARCHAR, TIMESTAMP, func, Identity
from sqlalchemy.orm import relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(BIGINT, Identity(), primary_key=True, index=True)
    name = Column(VARCHAR(255), nullable=False)
    email = Column(VARCHAR(255), unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    workspace_members = relationship("WorkspaceMember", back_populates="user", cascade="all, delete-orphan")