from sqlalchemy import BIGINT, Column, String, VARCHAR, TIMESTAMP, func
from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(BIGINT, primary_key=True, index=True)
    name = Column(VARCHAR(255), nullable=False)
    email = Column(VARCHAR(255), unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())