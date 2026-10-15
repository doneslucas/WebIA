from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.auth import verify_token
from app.services.quiz import (
    generate_quiz,
    generate_mixed_quiz,
    get_quiz_generation_status,
    check_quiz_answer
)
from app.services.categories import get_all_categories
from app.database.connection import get_connection


router = APIRouter(
    prefix="/quiz",
    tags=["Quiz"]
)


# -------------------------------------------------
# Modèles des requêtes
# -------------------------------------------------

class QuizGenerationRequest(BaseModel):
    category_ids: list[int]
    question_count: int
    difficulty: str


class MixedQuizGenerationRequest(BaseModel):
    category_ids: list[int]
    question_count: int
    primary_difficulty: str
    secondary_difficulty: str


class QuizAnswer(BaseModel):
    question_id: int
    answer: int


class QuizSubmissionRequest(BaseModel):
    answers: list[QuizAnswer]


# -------------------------------------------------
# Validation commune
# -------------------------------------------------

VALID_DIFFICULTIES = {
    "easy",
    "medium",
    "hard"
}

VALID_QUESTION_COUNTS = {
    5,
    10,
    15,
    20
}


def validate_category_ids(category_ids: list[int]):
    if not category_ids:
        raise HTTPException(
            status_code=422,
            detail="Au moins une catégorie doit être sélectionnée."
        )

    if any(category_id <= 0 for category_id in category_ids):
        raise HTTPException(
            status_code=422,
            detail="Les identifiants de catégories doivent être positifs."
        )

    if len(category_ids) != len(set(category_ids)):
        raise HTTPException(
            status_code=422,
            detail="Les catégories sélectionnées doivent être uniques."
        )


def validate_question_count(question_count: int):
    if question_count not in VALID_QUESTION_COUNTS:
        raise HTTPException(
            status_code=422,
            detail=(
                "Le nombre de questions doit être "
                "5, 10, 15 ou 20."
            )
        )


def validate_difficulty(
    difficulty: str,
    field_name: str = "La difficulté"
):
    if difficulty not in VALID_DIFFICULTIES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{field_name} doit être "
                "easy, medium ou hard."
            )
        )


# -------------------------------------------------
# Catégories disponibles
# -------------------------------------------------

@router.get("/categories")
def get_quiz_categories(
    payload: dict = Depends(verify_token)
):
    """
    Retourne les 50 catégories fixes disponibles
    pour la configuration des quiz.

    Pour chaque catégorie, retourne également le nombre
    de questions disponibles pour chaque difficulté.

    Aucun appel LLM n'est effectué ici.
    """

    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token."
        )

    try:
        categories = get_all_categories()

        # -------------------------------------------------
        # Récupération des compteurs de questions
        #
        # quiz_questions
        #       ↓
        # document_chunks
        #       ↓
        # categories
        #
        # Une question appartient à un chunk.
        # Le chunk possède sa catégorie principale.
        # -------------------------------------------------

        question_counts = {}

        with get_connection() as conn:

            with conn.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT
                        dc.category_id,
                        qq.difficulty,
                        COUNT(*) AS question_count
                    FROM quiz_questions qq
                    INNER JOIN document_chunks dc
                        ON dc.id = qq.chunk_id
                    WHERE dc.category_id IS NOT NULL
                    GROUP BY
                        dc.category_id,
                        qq.difficulty
                    """
                )

                rows = cursor.fetchall()

                for category_id, difficulty, count in rows:

                    if category_id not in question_counts:
                        question_counts[category_id] = {
                            "easy": 0,
                            "medium": 0,
                            "hard": 0
                        }

                    question_counts[category_id][difficulty] = int(
                        count
                    )

        # -------------------------------------------------
        # Construction de la réponse finale
        #
        # Même une catégorie sans question est retournée
        # avec 0 / 0 / 0.
        # -------------------------------------------------

        categories_with_counts = []

        for category in categories:

            category_id = category["id"]

            counts = question_counts.get(
                category_id,
                {
                    "easy": 0,
                    "medium": 0,
                    "hard": 0
                }
            )

            categories_with_counts.append(
                {
                    "id": category_id,
                    "name": category["name"],
                    "family": category["family"],
                    "question_counts": counts
                }
            )

        return {
            "categories": categories_with_counts
        }

    except Exception as error:
        print(
            "Erreur lors de la récupération "
            f"des catégories et des compteurs : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Impossible de récupérer les catégories "
                "et leurs compteurs."
            )
        )


# -------------------------------------------------
# Génération / récupération d'un quiz
# -------------------------------------------------

@router.post("/generate")
def generate_quiz_route(
    request: QuizGenerationRequest,
    payload: dict = Depends(verify_token)
):
    """
    Prépare un quiz uniquement à partir des catégories
    et de la difficulté sélectionnées.

    Aucun document n'est demandé au frontend.

    Aucun appel LLM n'est effectué ici.
    """

    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token."
        )

    validate_category_ids(request.category_ids)
    validate_question_count(request.question_count)
    validate_difficulty(request.difficulty)

    try:
        return generate_quiz(
            category_ids=request.category_ids,
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
            f"Erreur lors de la récupération du quiz : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la récupération du quiz."
        )


# -------------------------------------------------
# Génération / récupération d'un quiz mixte
# -------------------------------------------------

@router.post("/generate-mixed")
def generate_mixed_quiz_route(
    request: MixedQuizGenerationRequest,
    payload: dict = Depends(verify_token)
):
    """
    Prépare un quiz utilisant deux difficultés.

    Aucun document n'est demandé au frontend.
    Aucun appel LLM n'est effectué ici.
    """

    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token."
        )

    validate_category_ids(request.category_ids)
    validate_question_count(request.question_count)

    validate_difficulty(
        request.primary_difficulty,
        "La difficulté principale"
    )

    validate_difficulty(
        request.secondary_difficulty,
        "La difficulté secondaire"
    )

    if (
        request.primary_difficulty
        == request.secondary_difficulty
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Les deux difficultés doivent être différentes."
            )
        )

    try:
        return generate_mixed_quiz(
            category_ids=request.category_ids,
            question_count=request.question_count,
            primary_difficulty=request.primary_difficulty,
            secondary_difficulty=request.secondary_difficulty,
            user_id=user_id
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        print(
            "Erreur lors de la récupération "
            f"du quiz mixte : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Erreur lors de la récupération "
                "du quiz mixte."
            )
        )


# -------------------------------------------------
# Statut de génération
# -------------------------------------------------

@router.get("/generation-status")
def quiz_generation_status_route(
    category_ids: list[int],
    difficulty: str,
    requested_count: int,
    payload: dict = Depends(verify_token)
):
    """
    Retourne l'état de la banque correspondant aux
    catégories et à la difficulté demandées.

    Aucun document n'est nécessaire.
    """

    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token."
        )

    validate_category_ids(category_ids)
    validate_difficulty(difficulty)
    validate_question_count(requested_count)

    try:
        return get_quiz_generation_status(
            category_ids=category_ids,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        print(
            "Erreur lors de la récupération "
            f"du statut de génération : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Impossible de récupérer "
                "le statut de génération."
            )
        )


# -------------------------------------------------
# Vérification d'une réponse
# -------------------------------------------------

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

    if request.answer not in {0, 1, 2, 3}:
        raise HTTPException(
            status_code=422,
            detail=(
                "La réponse doit être un entier "
                "compris entre 0 et 3."
            )
        )

    try:
        return check_quiz_answer(
            question_id=request.question_id,
            answer=request.answer
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except Exception as error:
        print(
            "Erreur lors de la vérification "
            f"de la réponse : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Erreur lors de la vérification "
                "de la réponse."
            )
        )


# -------------------------------------------------
# Soumission d'un quiz
# -------------------------------------------------

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
        if answer.answer not in {0, 1, 2, 3}:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Chaque réponse doit être un entier "
                    "compris entre 0 et 3."
                )
            )

    question_ids = [
        answer.question_id
        for answer in request.answers
    ]

    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(
            status_code=422,
            detail="Une question ne peut apparaître qu'une seule fois."
        )

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
                    detail=(
                        "Une ou plusieurs questions "
                        "sont introuvables."
                    )
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
                            "Question "
                            f"{submitted_answer.question_id} "
                            "introuvable."
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
                        "question_id":
                            submitted_answer.question_id,
                        "answer_given":
                            answer_given,
                        "correct_answer":
                            correct_answer,
                        "is_correct":
                            is_correct,
                        "explanation":
                            question["explanation"]
                    }
                )

            total_questions = len(request.answers)

            cursor.execute(
                """
                INSERT INTO quiz_results (
                    user_id,
                    score,
                    total_questions
                )
                VALUES (
                    %s,
                    %s,
                    %s
                )
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
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s
                    )
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