from fastapi import FastAPI

from app.api.routes import documents
from app.api.routes import policies

app = FastAPI(title="Kagaz API")

app.include_router(documents.router)
app.include_router(policies.router)
