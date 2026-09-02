from fastapi import APIRouter, Depends

from app.services.auth import verify_token


router = APIRouter(
    tags=["Profile"]
)


@router.get("/profile")
def profile(payload: dict = Depends(verify_token)):

    return {
        "message": "Bienvenue sur ton profil",
        "email": payload["email"]
    }