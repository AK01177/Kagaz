from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.health import router as health_router


app = FastAPI(
    title="Kagaz API",
    description="Backend API for the Kagaz AI Document Workflow System",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)