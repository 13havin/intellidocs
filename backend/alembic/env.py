from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

from dotenv import load_dotenv
load_dotenv()

from app.db.database import Base
from app.models import user

config = context.config
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
fileConfig(config.config_file_name)
target_metadata = Base.metadata