import os
from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
    
def validate_env_vars():
    '''Validate that the required environment variables are set.
    '''
    validate_database_url(DATABASE_URL)
    validate_secret_key(SECRET_KEY)
    validate_algorithm(ALGORITHM)
    
def validate_database_url(DATABASE_URL: str):
    if not DATABASE_URL or not DATABASE_URL.strip():
        raise ValueError("DATABASE_URL is not set in the environment.")
    try:
        database_url = make_url(DATABASE_URL)
    except ArgumentError:
        raise ValueError("DATABASE_URL must be a valid database URL.") from None
    
    if database_url.drivername not in {"postgresql", "postgresql+psycopg2"}:
        raise ValueError("DATABASE_URL must be a PostgreSQL database URL.")
    
    if not database_url.host:
        raise ValueError("DATABASE_URL must include a host.")
    
    if not database_url.username:
        raise ValueError("DATABASE_URL must include a username.")
    
    if not database_url.database:
        raise ValueError("DATABASE_URL must include a database name.")
    
def validate_secret_key(SECRET_KEY: str):
    if not SECRET_KEY or not SECRET_KEY.strip():
        raise ValueError("SECRET_KEY is not set in the environment.")
    
    if len(SECRET_KEY.encode("utf-8")) < 32:
        raise ValueError("SECRET_KEY must be at least 32 bytes long.")
    
def validate_algorithm(ALGORITHM: str):
    if not ALGORITHM or not ALGORITHM.strip():
        raise ValueError("ALGORITHM is not set in the environment.")
    
    if ALGORITHM != "HS256":
        raise ValueError("ALGORITHM must be set to 'HS256'.")