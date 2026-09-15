from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import verify_token
from app.services.quiz import (
    generate_quiz,
    check_quiz_answer
)
from app.database.connection import get_connection


router = APIRouter(
    prefix="/quiz",
    tags=["Quiz"]
)


class QuizGenerationRequest(BaseModel):
    document: str
    question_count: int
    difficulty: str


class QuizAnswer(BaseModel):
    question_id: int
    answer: int


class QuizSubmissionRequest(BaseModel):
    answers: list[QuizAnswer]


@router.post("/generate")
def generate_quiz_route(
    request: QuizGenerationRequest,
    payload: dict = Depends(verify_token)
):
    user_id = payload.get("user_id")

    if user_id is None:
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
            difficulty=request.difficulty,
            user_id=user_id
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


@router.post("/answer")
def check_answer(
    request: QuizAnswer,
    payload: dict = Depends(verify_token)
):
    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token."
        )

    if request.answer not in {
        0,
        1,
        2,
        3
    }:
        raise HTTPException(
            status_code=422,
            detail="La réponse doit être un entier compris entre 0 et 3."
        )

    try:
        result = check_quiz_answer(
            question_id=request.question_id,
            answer=request.answer
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except Exception as error:
        print(
            f"Erreur lors de la vérification de la réponse : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la vérification de la réponse."
        )


@router.post("/submit")
def submit_quiz(
    request: QuizSubmissionRequest,
    payload: dict = Depends(verify_token)
):
    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token."
        )

    if not request.answers:
        raise HTTPException(
            status_code=422,
            detail="Aucune réponse fournie."
        )

    for answer in request.answers:

        if answer.answer not in {
            0,
            1,
            2,
            3
        }:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Chaque réponse doit être un entier compris "
                    "entre 0 et 3."
                )
            )

    question_ids = [
        answer.question_id
        for answer in request.answers
    ]

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    correct_answer,
                    explanation
                FROM quiz_questions
                WHERE id = ANY(%s)
                """,
                (question_ids,)
            )

            questions = cursor.fetchall()

            if len(questions) != len(set(question_ids)):
                raise HTTPException(
                    status_code=404,
                    detail="Une ou plusieurs questions sont introuvables."
                )

            questions_by_id = {
                question[0]: {
                    "correct_answer": int(question[1]),
                    "explanation": question[2]
                }
                for question in questions
            }

            score = 0
            results = []

            for submitted_answer in request.answers:

                question = questions_by_id.get(
                    submitted_answer.question_id
                )

                if question is None:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"Question "
                            f"{submitted_answer.question_id} introuvable."
                        )
                    )

                answer_given = submitted_answer.answer
                correct_answer = question["correct_answer"]

                is_correct = (
                    answer_given == correct_answer
                )

                if is_correct:
                    score += 1

                results.append(
                    {
                        "question_id": submitted_answer.question_id,
                        "answer_given": answer_given,
                        "correct_answer": correct_answer,
                        "is_correct": is_correct,
                        "explanation": question["explanation"]
                    }
                )

            total_questions = len(
                request.answers
            )

            cursor.execute(
                """
                INSERT INTO quiz_results (
                    user_id,
                    score,
                    total_questions
                )
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    score,
                    total_questions
                )
            )

            quiz_result_id = cursor.fetchone()[0]

            for result in results:

                cursor.execute(
                    """
                    INSERT INTO quiz_attempt_questions (
                        quiz_result_id,
                        question_id,
                        answer_given,
                        is_correct
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        quiz_result_id,
                        result["question_id"],
                        str(result["answer_given"]),
                        result["is_correct"]
                    )
                )

            conn.commit()

    return {
        "message": "Quiz enregistré avec succès.",
        "quiz_result_id": quiz_result_id,
        "score": score,
        "total_questions": total_questions,
        "results": results
    }