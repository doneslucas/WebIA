from fastapi import APIRouter, Depends

from pydantic import BaseModel

from app.services.rag import ask_rag

from app.services.auth import verify_token



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
    # La priorité est gérée de façon centralisée par le middleware HTTP
    # pour le chatbot et le quiz. Ne pas incrémenter ici une seconde fois.
    return ask_rag(request.question)