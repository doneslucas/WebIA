from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import verify_token
from app.services.progress import (
    save_quiz_result,
    get_quiz_results
)


router = APIRouter(
    prefix="/progress",
    tags=["Progression"]
)


class QuizResult(BaseModel):
    score: int
    total_questions: int


@router.get("")
def get_progress(
    payload: dict = Depends(verify_token)
):
    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token."
        )

    return {
        "results": get_quiz_results(user_id)
    }


@router.post("/quiz")
def save_progress(
    result: QuizResult,
    payload: dict = Depends(verify_token)
):
    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token."
        )

    if result.total_questions <= 0:
        raise HTTPException(
            status_code=422,
            detail="Le nombre total de questions doit être supérieur à 0."
        )

    if result.score < 0:
        raise HTTPException(
            status_code=422,
            detail="Le score ne peut pas être négatif."
        )

    if result.score > result.total_questions:
        raise HTTPException(
            status_code=422,
            detail="Le score ne peut pas être supérieur au nombre total de questions."
        )

    return save_quiz_result(
        user_id=user_id,
        score=result.score,
        total_questions=result.total_questions
    )