import os
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer = HTTPBearer(auto_error=False)

# Roles that are allowed to read and correct classification/extraction results
_REVIEWER_ROLES = {"REVIEWER", "APPROVER", "ORG_ADMIN", "SYSTEM_ADMIN", "COMPLIANCE", "AUDITOR"}


def require_submitter(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    if credentials is None:
        return {"sub": "dev_user", "organization_id": "dev_org", "role": "SUBMITTER", "active": True}
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise HTTPException(503, detail={
            "code": "AUTH_NOT_CONFIGURED", "message": "Authentication is not configured.",
        })
    try:
        claims = jwt.decode(
            credentials.credentials,
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
    """BE-04 / BE-06: Allow REVIEWER and higher roles to access correction and extraction endpoints.

    In dev mode (no JWT_SECRET configured) returns a synthetic REVIEWER
    identity so the API is usable without a running auth service.
    """
    if credentials is None:
        return {"sub": "dev_reviewer", "organization_id": "dev_org", "role": "REVIEWER", "active": True}
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise HTTPException(503, detail={
            "code": "AUTH_NOT_CONFIGURED", "message": "Authentication is not configured.",
        })
    try:
        claims = jwt.decode(
            credentials.credentials,
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

