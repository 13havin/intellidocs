from fastapi import FastAPI
from app.core import config
from app.routers import health, info, users, auth

config.validate_env_vars()

app = FastAPI(
    title="IntelliDocs API",
    version="0.1.0"
)

app.include_router(health.router)
app.include_router(info.router)
app.include_router(auth.router)
app.include_router(users.router)