from fastapi import APIRouter, Depends

from pydantic import BaseModel

from app.services.rag import ask_rag

from app.services.auth import verify_token

from app.services.task_manager import task_manager


router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)


class ChatRequest(BaseModel):

    question: str


@router.post("")
def chat(
    request: ChatRequest,
    payload: dict = Depends(verify_token)
):
    task_manager.start_user_request()

    try:
        return ask_rag(request.question)
    finally:
        task_manager.end_user_request()