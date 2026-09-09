import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from app.services.auth import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
)


def test_hash_password():
    password = "TestPassword123!"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$2")


def test_verify_correct_password():
    password = "TestPassword123!"

    password_hash = hash_password(password)

    assert verify_password(password, password_hash) is True


def test_verify_wrong_password():
    password = "TestPassword123!"
    wrong_password = "WrongPassword123!"

    password_hash = hash_password(password)

    assert verify_password(wrong_password, password_hash) is False


def test_create_access_token():
    user_id = 1
    email = "test@example.com"
    role = "admin"

    token = create_access_token(
        user_id=user_id,
        email=email,
        role=role
    )

    assert isinstance(token, str)
    assert len(token) > 0


def test_access_token_contains_expected_data():
    user_id = 1
    email = "test@example.com"
    role = "admin"

    token = create_access_token(
        user_id=user_id,
        email=email,
        role=role
    )

    secret = os.getenv("JWT_SECRET")

    assert secret is not None

    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"]
    )

    assert payload["user_id"] == user_id
    assert payload["email"] == email
    assert payload["role"] == role
    assert "exp" in payload


def test_expired_token_is_rejected():
    secret = os.getenv("JWT_SECRET")

    assert secret is not None

    expired_token = jwt.encode(
        {
            "user_id": 1,
            "email": "test@example.com",
            "role": "user",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1)
        },
        secret,
        algorithm="HS256"
    )

    credentials = type(
        "Credentials",
        (),
        {"credentials": expired_token}
    )()

    with pytest.raises(HTTPException) as error:
        verify_token(credentials)

    assert error.value.status_code == 401
    assert error.value.detail == "Token expiré"


def test_invalid_token_is_rejected():
    credentials = type(
        "Credentials",
        (),
        {"credentials": "token_completement_faux"}
    )()

    with pytest.raises(HTTPException) as error:
        verify_token(credentials)

    assert error.value.status_code == 401
    assert error.value.detail == "Token invalide"


def test_token_signed_with_wrong_secret_is_rejected():
    token = jwt.encode(
        {
            "user_id": 1,
            "email": "test@example.com",
            "role": "user",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        },
        "mauvaise-cle-secrete-de-test-32-octets-minimum",
        algorithm="HS256"
    )

    credentials = type(
        "Credentials",
        (),
        {"credentials": token}
    )()

    with pytest.raises(HTTPException) as error:
        verify_token(credentials)

    assert error.value.status_code == 401
    assert error.value.detail == "Token invalide"