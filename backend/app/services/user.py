from fastapi import HTTPException
from psycopg.errors import UniqueViolation

from app.database.connection import get_connection
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token
)


def register_user(email: str, password: str):
    password_hash = hash_password(password)

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (email, password_hash)
                    VALUES (%s, %s)
                    """,
                    (email, password_hash)
                )

                conn.commit()

    except UniqueViolation:
        return {
            "message": "Cet email est déjà utilisé"
        }

    return {
        "message": "Utilisateur créé",
        "email": email
    }


def login_user(email: str, password: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT password_hash, role
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            result = cursor.fetchone()

    if result is None:
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )

    password_hash = result[0]
    role = result[1]

    if not verify_password(password, password_hash):
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )

    token = create_access_token(
        email=email,
        role=role
    )

    return {
        "message": "Connexion réussie",
        "access_token": token
    }