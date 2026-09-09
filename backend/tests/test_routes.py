import io

from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import create_access_token


client = TestClient(app)


def get_token(
    user_id: int,
    email: str,
    role: str
) -> str:
    return create_access_token(
        user_id=user_id,
        email=email,
        role=role
    )


def test_profile_without_token():
    response = client.get("/profile")

    assert response.status_code == 401


def test_profile_with_invalid_token():
    response = client.get(
        "/profile",
        headers={
            "Authorization": "Bearer token_invalide"
        }
    )

    assert response.status_code == 401


def test_profile_with_user_token():
    token = get_token(
        user_id=2,
        email="user@test.com",
        role="user"
    )

    response = client.get(
        "/profile",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200
    assert response.json()["email"] == "user@test.com"
    assert response.json()["role"] == "user"


def test_profile_with_admin_token():
    token = get_token(
        user_id=1,
        email="admin@test.com",
        role="admin"
    )

    response = client.get(
        "/profile",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200
    assert response.json()["email"] == "admin@test.com"
    assert response.json()["role"] == "admin"


def test_document_upload_without_token():
    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "test.pdf",
                io.BytesIO(b"fake pdf"),
                "application/pdf"
            )
        }
    )

    assert response.status_code == 401


def test_document_upload_with_user_token():
    token = get_token(
        user_id=2,
        email="user@test.com",
        role="user"
    )

    response = client.post(
        "/documents/upload",
        headers={
            "Authorization": f"Bearer {token}"
        },
        files={
            "file": (
                "test.pdf",
                io.BytesIO(b"fake pdf"),
                "application/pdf"
            )
        }
    )

    assert response.status_code == 403
    assert "administrateurs" in response.json()["detail"]


def test_document_upload_with_invalid_token():
    response = client.post(
        "/documents/upload",
        headers={
            "Authorization": "Bearer token_invalide"
        },
        files={
            "file": (
                "test.pdf",
                io.BytesIO(b"fake pdf"),
                "application/pdf"
            )
        }
    )

    assert response.status_code == 401