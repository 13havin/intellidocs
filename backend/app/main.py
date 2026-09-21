from fastapi import FastAPI
from app.routers import health, info

app = FastAPI(
    title="IntelliDocs API",
    version="0.1.0"
)

app.include_router(health.router)
app.include_router(info.router)