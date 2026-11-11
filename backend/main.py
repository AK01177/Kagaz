from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from api.health import router as health_router
from api.documents import router as documents_router
from api.auth import router as auth_router
from api.policies import router as policies_router
from api.workflow import router as workflow_router
from app.api.routes.policies import router as policies_retrieval_router
from app.api.routes.policy_validation import router as policy_validation_router

load_dotenv()

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
app.include_router(documents_router)
app.include_router(auth_router)
app.include_router(workflow_router)
app.include_router(policies_retrieval_router)
app.include_router(policies_router)
app.include_router(policy_validation_router)


@app.exception_handler(HTTPException)
async def http_error_handler(request, exc):
    error = exc.detail if isinstance(exc.detail, dict) else {
        "code": "HTTP_ERROR", "message": str(exc.detail),
    }
    return JSONResponse(status_code=exc.status_code, content={"error": error}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse(status_code=422, content={"error": {
        "code": "VALIDATION_ERROR", "message": "The request contains invalid or missing fields.",
    }})
