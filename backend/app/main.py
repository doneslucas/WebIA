from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import psycopg
from psycopg.errors import UniqueViolation
import bcrypt
from dotenv import load_dotenv
import os
import jwt
from datetime import datetime, timedelta, timezone

load_dotenv()
security = HTTPBearer()
app = FastAPI()
JWT_SECRET = os.getenv("JWT_SECRET")

def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"]
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expiré"
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token invalide"
        )

@app.get("/profile")
def profile(payload: dict = Depends(verify_token)):

    return {
        "message": "Bienvenue sur ton profil",
        "email": payload["email"]
    }

class UserRegister(BaseModel):
    email: str
    password: str

@app.post("/auth/register")
def register(user: UserRegister):

    password_hash = bcrypt.hashpw(
        user.password.encode("utf-8"),
        bcrypt.gensalt()
    )

    try:
        with psycopg.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        ) as conn:

            with conn.cursor() as cursor:

                cursor.execute(
                    """
                    INSERT INTO users (email, password_hash)
                    VALUES (%s, %s)
                    """,
                    (user.email, password_hash.decode("utf-8"))
                )

                conn.commit()

    except UniqueViolation:
        return {
            "message": "Cet email est déjà utilisé"
        }

    return {
        "message": "Utilisateur créé",
        "email": user.email
    }

class UserLogin(BaseModel):
    email: str
    password: str

@app.post("/auth/login")
def login(user: UserLogin):

    with psycopg.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    ) as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT password_hash
                FROM users
                WHERE email = %s
                """,
                (user.email,)
            )

            result = cursor.fetchone()

    if result is None:
        return {
            "message": "Email ou mot de passe incorrect"
        }

    password_hash = result[0]

    if not bcrypt.checkpw(
        user.password.encode("utf-8"),
        password_hash.encode("utf-8")
    ):
        return {
            "message": "Email ou mot de passe incorrect"
        }

    token = jwt.encode(
        {
            "email": user.email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        },
        JWT_SECRET,
        algorithm="HS256"
    )

    return {
        "message": "Connexion réussie",
        "access_token": token
    }
