from fastapi import HTTPException
from psycopg.errors import UniqueViolation

from app.database.connection import get_connection
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token
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
                SELECT id, password_hash, role
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

    user_id = result[0]
    password_hash = result[1]
    role = result[2]

    if not verify_password(password, password_hash):
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )

    access_token = create_access_token(
        user_id=user_id,
        email=email,
        role=role
    )

    refresh_token = create_refresh_token(
        user_id=user_id,
        email=email,
        role=role
    )

    return {
        "message": "Connexion réussie",
        "access_token": access_token,
        "refresh_token": refresh_token
    }


def change_password(
    user_id: int,
    current_password: str,
    new_password: str
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT password_hash
                FROM users
                WHERE id = %s
                """,
                (user_id,)
            )

            result = cursor.fetchone()

            if result is None:
                raise HTTPException(
                    status_code=404,
                    detail="Utilisateur introuvable"
                )

            current_password_hash = result[0]

            if not verify_password(
                current_password,
                current_password_hash
            ):
                raise HTTPException(
                    status_code=401,
                    detail="Ancien mot de passe incorrect"
                )

            new_password_hash = hash_password(
                new_password
            )

            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE id = %s
                """,
                (
                    new_password_hash,
                    user_id
                )
            )

            conn.commit()

    return {
        "message": "Mot de passe modifié avec succès"
    }