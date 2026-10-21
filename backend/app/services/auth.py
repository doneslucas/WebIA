
import os
import jwt
import bcrypt

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
)

from dotenv import load_dotenv


load_dotenv()


security = HTTPBearer()


JWT_SECRET = os.getenv("JWT_SECRET")


ACCESS_TOKEN_EXPIRE_MINUTES = 15

REFRESH_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    )

    return password_hash.decode("utf-8")


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def create_access_token(
    user_id: int,
    email: str,
    role: str,
) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "exp": (
            datetime.now(timezone.utc)
            + timedelta(
                minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
            )
        ),
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm="HS256",
    )


def create_refresh_token(
    user_id: int,
    email: str,
    role: str,
) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "type": "refresh",
        "exp": (
            datetime.now(timezone.utc)
            + timedelta(
                days=REFRESH_TOKEN_EXPIRE_DAYS,
            )
        ),
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm="HS256",
    )


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
        )

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=401,
                detail="Token d'accès invalide.",
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expiré",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token invalide",
        )


def require_admin(
    current_user: dict = Depends(verify_token),
) -> dict:
    """
    Autorise uniquement les utilisateurs ayant le rôle admin.
    À utiliser sur les routes réservées à l'administration.
    """

    role = str(current_user.get("role", "")).strip().lower()

    if role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Accès réservé aux administrateurs.",
        )

    return current_user


def verify_refresh_token(
    token: str,
):
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
        )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=401,
                detail="Refresh token invalide.",
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Refresh token expiré.",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Refresh token invalide.",
        )
