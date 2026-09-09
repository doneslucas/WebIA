from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import verify_token
from app.services.user import change_password


router = APIRouter(
    tags=["Profile"]
)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


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


@router.get("/profile")
def get_profile(
    payload: dict = Depends(verify_token)
):
    return {
        "email": payload.get("email"),
        "role": payload.get("role")
    }


@router.put("/profile/password")
def update_password(
    password_data: PasswordChange,
    payload: dict = Depends(verify_token)
):
    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token."
        )

    validate_password(password_data.new_password)

    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=422,
            detail="Le nouveau mot de passe doit être différent de l'ancien."
        )

    return change_password(
        user_id=user_id,
        current_password=password_data.current_password,
        new_password=password_data.new_password
    )