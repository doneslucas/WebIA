from fastapi import APIRouter, Depends

from app.services.auth import verify_token


router = APIRouter(
    tags=["Profile"]
)


@router.get("/profile")
def get_profile(
    payload: dict = Depends(verify_token)
):
    return {
        "email": payload.get("email"),
        "role": payload.get("role")
    }