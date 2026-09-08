from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.services.user import register_user, login_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


def validate_password(password: str):
    if len(password) < 8:
        raise HTTPException(
            status_code=422,
            detail="Le mot de passe doit contenir au moins 8 caractères."
        )

    if not any(char.isupper() for char in password):
        raise HTTPException(
            status_code=422,
            detail="Le mot de passe doit contenir au moins une majuscule."
        )

    if not any(char.islower() for char in password):
        raise HTTPException(
            status_code=422,
            detail="Le mot de passe doit contenir au moins une minuscule."
        )

    if not any(char.isdigit() for char in password):
        raise HTTPException(
            status_code=422,
            detail="Le mot de passe doit contenir au moins un chiffre."
        )

    if not any(not char.isalnum() for char in password):
        raise HTTPException(
            status_code=422,
            detail="Le mot de passe doit contenir au moins un caractère spécial."
        )


@router.post("/register")
def register(user: UserRegister):
    validate_password(user.password)

    return register_user(
        str(user.email).lower(),
        user.password
    )


@router.post("/login")
def login(user: UserLogin):
    return login_user(
        str(user.email).lower(),
        user.password
    )