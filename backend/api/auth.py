import os
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer = HTTPBearer(auto_error=False)


def require_submitter(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    if credentials is None:
        raise _unauthenticated()
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


def _unauthenticated() -> HTTPException:
    return HTTPException(401, detail={
        "code": "UNAUTHENTICATED", "message": "A valid bearer token is required.",
    }, headers={"WWW-Authenticate": "Bearer"})
