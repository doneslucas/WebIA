from fastapi import APIRouter
from pydantic import BaseModel

from app.services.user import register_user, login_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


class UserRegister(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(user: UserRegister):

    return register_user(
        user.email,
        user.password
    )


@router.post("/login")
def login(user: UserLogin):

    return login_user(
        user.email,
        user.password
    )
