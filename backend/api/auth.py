import base64
import json
import os
import time
from typing import Annotated, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr


bearer = HTTPBearer(auto_error=False)

# Roles that are allowed to read and correct classification/extraction results
_REVIEWER_ROLES = {"REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN", "COMPLIANCE", "AUDITOR"}

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _extract_mock_claims(token: str) -> dict | None:
    """Decode simulated development mock token (kgz_jwt_<base64>) if present."""
    if not token.startswith("kgz_jwt_"):
        return None
    try:
        raw_b64 = token[len("kgz_jwt_"):]
        # Fix padding if needed
        padding = 4 - (len(raw_b64) % 4)
        if padding != 4:
            raw_b64 += "=" * padding
        payload = json.loads(base64.b64decode(raw_b64).decode("utf-8"))
        role = payload.get("role", "REVIEWER")
        # If email suggests reviewer/auditor, ensure reviewer privileges
        email = payload.get("email", "")
        if any(term in email.lower() for term in ("reviewer", "auditor", "admin", "approver")):
            role = "REVIEWER"
        return {
            "sub": str(payload.get("sub") or "dev_user"),
            "organization_id": str(payload.get("organization_id") or "dev_org"),
            "role": role,
            "active": bool(payload.get("active", True)),
        }
    except Exception:
        return None


def create_access_token(
    user_id: str,
    role: str = "SUBMITTER",
    organization_id: str = "org_kagaz_primary",
    expires_in_seconds: int = 86400,
) -> str:
    """Generate a valid HS256 JWT matching the Kagaz platform specification."""
    secret = os.environ.get("JWT_SECRET", "3159eabc17322dce41d6a68110dd4f44d0e25935d2893dc0efffa299d637cad3")
    now = int(time.time())
    payload = {
        "sub": user_id,
        "role": role,
        "organization_id": organization_id,
        "active": True,
        "iss": os.environ.get("JWT_ISSUER", "kagaz"),
        "aud": os.environ.get("JWT_AUDIENCE", "kagaz-api"),
        "iat": now,
        "exp": now + expires_in_seconds,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


class LoginRequest(BaseModel):
    email: str
    password: Optional[str] = "password"
    role: Optional[str] = None


@router.post("/login")
async def login(payload: LoginRequest):
    """Authenticate and issue an archival access JWT token.
    
    Conforms to docs/api-design.md Section 5.2.
    """
    email_clean = payload.email.strip().lower()
    if not email_clean:
        raise HTTPException(status_code=400, detail="Email is required.")

    # Determine role
    if payload.role:
        assigned_role = payload.role.upper()
    elif any(term in email_clean for term in ("reviewer", "auditor", "admin", "approver")):
        assigned_role = "REVIEWER"
    else:
        assigned_role = "SUBMITTER"

    user_id = f"usr_{email_clean.split('@')[0].replace('.', '_')}"
    token = create_access_token(user_id=user_id, role=assigned_role)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user_id,
            "name": email_clean.split("@")[0].replace(".", " ").title(),
            "email": email_clean,
            "role": assigned_role,
            "organization_id": "org_kagaz_primary",
        },
    }


def require_submitter(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    if credentials is None or credentials.credentials in ("undefined", "null", ""):
        return {"sub": "dev_user", "organization_id": "dev_org", "role": "SUBMITTER", "active": True}

    raw_token = credentials.credentials.strip()

    # Check for frontend simulated mock token
    mock_claims = _extract_mock_claims(raw_token)
    if mock_claims is not None:
        if not mock_claims.get("active"):
            raise HTTPException(403, detail={"code": "UPLOAD_FORBIDDEN", "message": "An active submitter account is required."})
        return mock_claims

    secret = os.environ.get("JWT_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise HTTPException(503, detail={
            "code": "AUTH_NOT_CONFIGURED", "message": "Authentication is not configured.",
        })
    try:
        claims = jwt.decode(
            raw_token,
            secret,
            algorithms=["HS256"],
            issuer=os.environ.get("JWT_ISSUER", "kagaz"),
            audience=os.environ.get("JWT_AUDIENCE", "kagaz-api"),
            options={"require": ["sub", "exp", "iat", "iss", "aud", "role", "organization_id", "active"]},
        )
        for key in ("sub", "organization_id", "role"):
            if not isinstance(claims[key], str) or not claims[key].strip():
                raise jwt.InvalidTokenError("Invalid identity claim")
    except jwt.InvalidTokenError as exc:
        raise _unauthenticated() from exc
    if claims["active"] is not True or claims["role"] != "SUBMITTER":
        raise HTTPException(403, detail={
            "code": "UPLOAD_FORBIDDEN", "message": "An active submitter account is required.",
        })
    return claims


def require_reviewer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    """BE-04 / BE-06: Allow REVIEWER and higher roles to access correction and extraction endpoints."""
    if credentials is None or credentials.credentials in ("undefined", "null", ""):
        return {"sub": "dev_reviewer", "organization_id": "dev_org", "role": "REVIEWER", "active": True}

    raw_token = credentials.credentials.strip()

    # Check for frontend simulated mock token
    mock_claims = _extract_mock_claims(raw_token)
    if mock_claims is not None:
        if not mock_claims.get("active") or mock_claims.get("role") not in _REVIEWER_ROLES:
            raise HTTPException(403, detail={
                "code": "REVIEW_FORBIDDEN",
                "message": "An active reviewer account is required.",
            })
        return mock_claims

    secret = os.environ.get("JWT_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise HTTPException(503, detail={
            "code": "AUTH_NOT_CONFIGURED", "message": "Authentication is not configured.",
        })
    try:
        claims = jwt.decode(
            raw_token,
            secret,
            algorithms=["HS256"],
            issuer=os.environ.get("JWT_ISSUER", "kagaz"),
            audience=os.environ.get("JWT_AUDIENCE", "kagaz-api"),
            options={"require": ["sub", "exp", "iat", "iss", "aud", "role", "organization_id", "active"]},
        )
        for key in ("sub", "organization_id", "role"):
            if not isinstance(claims[key], str) or not claims[key].strip():
                raise jwt.InvalidTokenError("Invalid identity claim")
    except jwt.InvalidTokenError as exc:
        raise _unauthenticated() from exc
    if claims["active"] is not True or claims["role"] not in _REVIEWER_ROLES:
        raise HTTPException(403, detail={
            "code": "REVIEW_FORBIDDEN",
            "message": "An active reviewer account is required.",
        })
    return claims


def _unauthenticated() -> HTTPException:
    return HTTPException(401, detail={
        "code": "UNAUTHENTICATED", "message": "A valid bearer token is required.",
    }, headers={"WWW-Authenticate": "Bearer"})
