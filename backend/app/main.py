from fastapi import FastAPI

from app.api.routes import documents

app = FastAPI(title="Kagaz API")

app.include_router(documents.router)
