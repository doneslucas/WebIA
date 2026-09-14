from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import verify_token
from app.services.quiz import generate_quiz


router = APIRouter(
    prefix="/quiz",
    tags=["Quiz"]
)


class QuizGenerationRequest(BaseModel):
    document: str
    question_count: int
    difficulty: str


@router.post("/generate")
def generate_quiz_route(
    request: QuizGenerationRequest,
    payload: dict = Depends(verify_token)
):
    if payload.get("user_id") is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token."
        )

    if request.question_count not in {
        5,
        10,
        15,
        20
    }:
        raise HTTPException(
            status_code=422,
            detail="Le nombre de questions doit être 5, 10, 15 ou 20."
        )

    if request.difficulty not in {
        "easy",
        "medium",
        "hard"
    }:
        raise HTTPException(
            status_code=422,
            detail="La difficulté doit être easy, medium ou hard."
        )

    try:
        return generate_quiz(
            document=request.document,
            question_count=request.question_count,
            difficulty=request.difficulty
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        print(
            f"Erreur lors de la génération du quiz : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la génération du quiz."
        )