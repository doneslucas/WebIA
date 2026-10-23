from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.auth import verify_token
from app.services.quiz import (
    generate_quiz,
    generate_mixed_quiz,
    get_quiz_generation_status,
    check_quiz_answer,
)
from app.services.categories import get_all_categories
from app.services.question_bank_manager import question_bank_manager
from app.database.connection import get_connection


router = APIRouter(
    prefix="/quiz",
    tags=["Quiz"],
)


VALID_DIFFICULTIES = {
    "easy",
    "medium",
    "hard",
}

VALID_QUESTION_COUNTS = {
    5,
    10,
    15,
    20,
}


# -------------------------------------------------
# Modèles des requêtes
# -------------------------------------------------

class QuizGenerationRequest(BaseModel):
    category_ids: list[int] = Field(min_length=1)
    question_count: int = Field(ge=1, le=20)
    difficulty: str
    allow_short_quiz: bool = False


class MixedQuizGenerationRequest(BaseModel):
    category_ids: list[int] = Field(min_length=1)
    question_count: int = Field(ge=1, le=20)
    primary_difficulty: str
    secondary_difficulty: str
    allow_short_quiz: bool = False


class QuizQuestionGenerationRequest(BaseModel):
    category_ids: list[int] = Field(min_length=1)
    difficulty: str


class QuizAnswer(BaseModel):
    question_id: int = Field(gt=0)
    answer: int


class QuizSubmissionRequest(BaseModel):
    answers: list[QuizAnswer] = Field(min_length=1)


# -------------------------------------------------
# Validation commune
# -------------------------------------------------

def validate_category_ids(category_ids: list[int]) -> None:
    if not category_ids:
        raise HTTPException(
            status_code=422,
            detail="Au moins une catégorie doit être sélectionnée.",
        )

    if any(
        not isinstance(category_id, int)
        or isinstance(category_id, bool)
        or category_id <= 0
        for category_id in category_ids
    ):
        raise HTTPException(
            status_code=422,
            detail="Les identifiants de catégories doivent être positifs.",
        )

    if len(category_ids) != len(set(category_ids)):
        raise HTTPException(
            status_code=422,
            detail="Les catégories sélectionnées doivent être uniques.",
        )


def validate_question_count(
    question_count: int,
    allow_short_quiz: bool = False,
) -> None:
    if allow_short_quiz:
        if not 1 <= question_count <= 20:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Un quiz raccourci doit contenir "
                    "entre 1 et 20 questions."
                ),
            )
        return

    if question_count not in VALID_QUESTION_COUNTS:
        raise HTTPException(
            status_code=422,
            detail="Le nombre de questions doit être 5, 10, 15 ou 20.",
        )


def validate_difficulty(
    difficulty: str,
    field_name: str = "La difficulté",
) -> None:
    if difficulty not in VALID_DIFFICULTIES:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} doit être easy, medium ou hard.",
        )


def get_authenticated_user_id(payload: dict) -> int:
    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur absent du token.",
        )

    try:
        return int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Identifiant utilisateur invalide dans le token.",
        )


# -------------------------------------------------
# Documents et tâches de génération
# -------------------------------------------------

def get_documents_by_selected_categories(
    category_ids: list[int],
) -> dict[str, set[int]]:
    """
    Retourne les documents qui possèdent des chunks classifiés
    dans les catégories demandées.

    Résultat :
        {
            "document.pdf": {category_id_1, category_id_2}
        }

    Les chunks sans catégorie ne sont pas utilisés pour déclencher
    la génération de QCM.
    """
    query = """
        SELECT DISTINCT
            d.file_name,
            dc.category_id
        FROM document_chunks dc
        JOIN documents d
            ON d.id = dc.document_id
        WHERE dc.category_id = ANY(%s)
        ORDER BY
            d.file_name,
            dc.category_id
    """

    documents: dict[str, set[int]] = defaultdict(set)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                (category_ids,),
            )

            for file_name, category_id in cursor.fetchall():
                if file_name and category_id is not None:
                    documents[str(file_name)].add(int(category_id))

    return dict(documents)


def get_generation_task_summary(
    category_ids: list[int],
    difficulty: str,
) -> dict:
    """
    Vérifie les tâches du gestionnaire correspondant aux catégories
    et à la difficulté sélectionnées.

    Les statuts queued et running indiquent qu'une tâche est
    effectivement en attente ou en cours d'exécution.
    """
    documents = get_documents_by_selected_categories(category_ids)

    active_count = 0
    queued_count = 0
    running_count = 0
    completed_count = 0
    incomplete_count = 0
    errors_count = 0
    cancelled_count = 0

    task_details = []

    for document, document_category_ids in documents.items():
        selected_categories = (
            document_category_ids.intersection(category_ids)
        )

        for category_id in selected_categories:
            task_status = question_bank_manager.get_task_status(
                document=document,
                category_id=category_id,
                difficulty=difficulty,
            )

            status = task_status.get("status", "not_queued")

            if status in {"queued", "running"}:
                active_count += 1

            if status == "queued":
                queued_count += 1
            elif status == "running":
                running_count += 1
            elif status == "completed":
                completed_count += 1
            elif status == "incomplete":
                incomplete_count += 1
            elif status == "error":
                errors_count += 1
            elif status == "cancelled":
                cancelled_count += 1

            task_details.append({
                "document": document,
                "category_id": category_id,
                "difficulty": difficulty,
                "status": status,
                "current": task_status.get("current", 0),
                "target": task_status.get("target", 0),
                "remaining": task_status.get("remaining", 0),
            })

    return {
        "generation_active": active_count > 0,
        "active_count": active_count,
        "queued_count": queued_count,
        "running_count": running_count,
        "completed_count": completed_count,
        "incomplete_count": incomplete_count,
        "errors_count": errors_count,
        "cancelled_count": cancelled_count,
        "tasks": task_details,
    }


# -------------------------------------------------
# Catégories disponibles
# -------------------------------------------------


@router.get("/categories")
def get_quiz_categories(
    payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(payload)

    try:
        categories = get_all_categories()

        query = """
            SELECT
                dc.category_id,
                qq.difficulty,
                COUNT(qq.id) AS question_count
            FROM quiz_questions qq
            JOIN document_chunks dc
                ON dc.id = qq.chunk_id
            WHERE dc.category_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM quiz_attempt_questions ta
                  JOIN quiz_results qr
                      ON qr.id = ta.quiz_result_id
                  WHERE ta.question_id = qq.id
                    AND qr.user_id = %s
              )
            GROUP BY
                dc.category_id,
                qq.difficulty
        """

        question_counts = {}

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (user_id,))

                for category_id, difficulty, count in cursor.fetchall():
                    if category_id not in question_counts:
                        question_counts[category_id] = {
                            "easy": 0,
                            "medium": 0,
                            "hard": 0,
                        }

                    if difficulty in {"easy", "medium", "hard"}:
                        question_counts[category_id][difficulty] = count

        categories_with_counts = []

        for category in categories:
            category_data = dict(category)
            category_id = category_data.get("id")

            category_data["question_counts"] = question_counts.get(
                category_id,
                {
                    "easy": 0,
                    "medium": 0,
                    "hard": 0,
                },
            )

            categories_with_counts.append(category_data)

        return {"categories": categories_with_counts}

    except HTTPException:
        raise

    except Exception as error:
        print(
            "[Quiz] Erreur lors de la récupération "
            f"des catégories : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Impossible de récupérer les catégories.",
        )

# -------------------------------------------------
# Génération d'un quiz
# -------------------------------------------------

@router.post("/generate")
def generate_quiz_route(
    request: QuizGenerationRequest,
    payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(payload)

    validate_category_ids(request.category_ids)
    validate_question_count(
        request.question_count,
        allow_short_quiz=request.allow_short_quiz,
    )
    validate_difficulty(request.difficulty)

    try:
        return generate_quiz(
            question_count=request.question_count,
            difficulty=request.difficulty,
            user_id=user_id,
            category_ids=request.category_ids,
            allow_short_quiz=request.allow_short_quiz,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        print(
            "[Quiz] Erreur lors de la préparation du quiz : "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la préparation du quiz.",
        )


# -------------------------------------------------
# Génération d'un quiz mixte
# -------------------------------------------------

@router.post("/generate-mixed")
def generate_mixed_quiz_route(
    request: MixedQuizGenerationRequest,
    payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(payload)

    validate_category_ids(request.category_ids)
    validate_question_count(
        request.question_count,
        allow_short_quiz=request.allow_short_quiz,
    )

    validate_difficulty(
        request.primary_difficulty,
        "La difficulté principale",
    )
    validate_difficulty(
        request.secondary_difficulty,
        "La difficulté secondaire",
    )

    if request.primary_difficulty == request.secondary_difficulty:
        raise HTTPException(
            status_code=422,
            detail="Les deux difficultés doivent être différentes.",
        )

    try:
        return generate_mixed_quiz(
            question_count=request.question_count,
            primary_difficulty=request.primary_difficulty,
            secondary_difficulty=request.secondary_difficulty,
            user_id=user_id,
            category_ids=request.category_ids,
            allow_short_quiz=request.allow_short_quiz,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        print(
            "[Quiz] Erreur lors de la préparation du quiz mixte : "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la préparation du quiz mixte.",
        )


# -------------------------------------------------
# Déclenchement manuel de la génération
# -------------------------------------------------

@router.post("/request-generation")
def request_quiz_question_generation(
    request: QuizQuestionGenerationRequest,
    payload: dict = Depends(verify_token),
):
    """
    Demande au gestionnaire existant de générer des questions
    pour les catégories et la difficulté sélectionnées.

    La génération reste exécutée par QuestionBankManager :
    cette route n'appelle pas directement le modèle de langage.
    """
    get_authenticated_user_id(payload)

    validate_category_ids(request.category_ids)
    validate_difficulty(request.difficulty)

    try:
        documents = get_documents_by_selected_categories(
            request.category_ids,
        )

        if not documents:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Aucun document indexé ne contient de chunks "
                    "classifiés dans les catégories sélectionnées. "
                    "Vérifie les catégories ou l'indexation des PDF."
                ),
            )

        if not question_bank_manager.is_running():
            question_bank_manager.start()

        new_tasks = 0
        active_tasks = 0
        completed_tasks = 0
        incomplete_tasks = 0
        unavailable_categories = set()

        for document, document_category_ids in documents.items():
            selected_categories = sorted(
                document_category_ids.intersection(
                    request.category_ids,
                ),
            )

            for category_id in selected_categories:
                result = question_bank_manager.ensure_category_difficulty(
                    document=document,
                    category_id=category_id,
                    difficulty=request.difficulty,
                )

                if result.get("queued"):
                    new_tasks += 1

                task_status = question_bank_manager.get_task_status(
                    document=document,
                    category_id=category_id,
                    difficulty=request.difficulty,
                )

                status = task_status.get("status", "not_queued")

                if status in {"queued", "running"}:
                    active_tasks += 1
                elif status == "completed":
                    completed_tasks += 1
                elif status in {"incomplete", "error", "cancelled"}:
                    incomplete_tasks += 1

                if result.get("target", 0) == 0:
                    unavailable_categories.add(category_id)

        if active_tasks == 0 and new_tasks == 0:
            if completed_tasks > 0 and incomplete_tasks == 0:
                return {
                    "status": "completed",
                    "category_ids": request.category_ids,
                    "difficulty": request.difficulty,
                    "queued_count": 0,
                    "active_count": 0,
                    "generation_active": False,
                    "estimated_seconds": None,
                    "message": (
                        "La génération est déjà terminée pour les banques "
                        "qui possèdent une capacité de génération."
                    ),
                }

            return {
                "status": "no_new_tasks",
                "category_ids": request.category_ids,
                "difficulty": request.difficulty,
                "queued_count": 0,
                "active_count": 0,
                "generation_active": False,
                "estimated_seconds": None,
                "message": (
                    "Aucune nouvelle tâche n'a été ajoutée. "
                    "Certaines banques peuvent déjà être complètes, "
                    "en cours de génération ou ne plus avoir de capacité."
                ),
            }

        # Estimation indicative, pas une durée garantie.
        # Le temps réel dépend du nombre de chunks, du modèle et du serveur.
        estimated_seconds = max(
            30,
            active_tasks * 90,
        )

        return {
            "status": "queued",
            "category_ids": request.category_ids,
            "difficulty": request.difficulty,
            "queued_count": new_tasks,
            "active_count": active_tasks,
            "generation_active": active_tasks > 0,
            "estimated_seconds": estimated_seconds,
            "estimate_is_approximate": True,
            "message": (
                f"Génération demandée. {new_tasks} nouvelle(s) tâche(s) "
                f"ajoutée(s), {active_tasks} tâche(s) en attente ou "
                "en cours. L'estimation est indicative."
            ),
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        print(
            "[Quiz] Erreur lors de la demande de génération : "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Impossible de lancer la génération des questions.",
        )


# -------------------------------------------------
# Statut de génération
# -------------------------------------------------

@router.get("/generation-status")
def quiz_generation_status_route(
    category_ids: list[int],
    difficulty: str,
    requested_count: int,
    payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(payload)

    validate_category_ids(category_ids)
    validate_difficulty(difficulty)
    validate_question_count(requested_count)

    try:
        # Le service calcule les questions disponibles pour l'utilisateur
        # ainsi que les banques existantes par difficulté.
        result = get_quiz_generation_status(
            category_ids=category_ids,
            user_id=user_id,
            requested_count=requested_count,
            difficulty=difficulty,
        )

        # Complète le statut avec celui du gestionnaire de tâches réel.
        task_summary = get_generation_task_summary(
            category_ids=category_ids,
            difficulty=difficulty,
        )

        result["generation_active"] = task_summary["generation_active"]
        result["active"] = task_summary["generation_active"]
        result["active_count"] = task_summary["active_count"]
        result["queued_count"] = task_summary["queued_count"]
        result["running_count"] = task_summary["running_count"]
        result["tasks"] = task_summary["tasks"]

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:
        print(
            "[Quiz] Erreur lors de la récupération du statut : "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Impossible de récupérer le statut de génération.",
        )


# -------------------------------------------------
# Vérification d'une réponse
# -------------------------------------------------

@router.post("/answer")
def check_answer(
    request: QuizAnswer,
    payload: dict = Depends(verify_token),
):
    get_authenticated_user_id(payload)

    if request.answer not in {0, 1, 2, 3}:
        raise HTTPException(
            status_code=422,
            detail="La réponse doit être un entier compris entre 0 et 3.",
        )

    try:
        return check_quiz_answer(
            question_id=request.question_id,
            answer=request.answer,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except Exception as error:
        print(
            "[Quiz] Erreur lors de la vérification de la réponse : "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la vérification de la réponse.",
        )


# -------------------------------------------------
# Soumission d'un quiz
# -------------------------------------------------

@router.post("/submit")
def submit_quiz(
    request: QuizSubmissionRequest,
    payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(payload)

    for submitted_answer in request.answers:
        if submitted_answer.answer not in {0, 1, 2, 3}:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Chaque réponse doit être un entier "
                    "compris entre 0 et 3."
                ),
            )

    question_ids = [
        submitted_answer.question_id
        for submitted_answer in request.answers
    ]

    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(
            status_code=422,
            detail="Une question ne peut apparaître qu'une seule fois.",
        )

    try:
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
                    (question_ids,),
                )

                questions = cursor.fetchall()

                if len(questions) != len(set(question_ids)):
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            "Une ou plusieurs questions "
                            "sont introuvables."
                        ),
                    )

                questions_by_id = {
                    question[0]: {
                        "correct_answer": int(question[1]),
                        "explanation": question[2],
                    }
                    for question in questions
                }

                score = 0
                results = []

                for submitted_answer in request.answers:
                    question = questions_by_id.get(
                        submitted_answer.question_id,
                    )

                    if question is None:
                        raise HTTPException(
                            status_code=404,
                            detail=(
                                f"Question {submitted_answer.question_id} "
                                "introuvable."
                            ),
                        )

                    answer_given = submitted_answer.answer
                    correct_answer = question["correct_answer"]

                    is_correct = answer_given == correct_answer

                    if is_correct:
                        score += 1

                    results.append({
                        "question_id": submitted_answer.question_id,
                        "answer_given": answer_given,
                        "correct_answer": correct_answer,
                        "is_correct": is_correct,
                        "explanation": question["explanation"],
                    })

                total_questions = len(request.answers)

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
                        total_questions,
                    ),
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
                            result["is_correct"],
                        ),
                    )

                conn.commit()

        return {
            "message": "Quiz enregistré avec succès.",
            "quiz_result_id": quiz_result_id,
            "score": score,
            "total_questions": total_questions,
            "results": results,
        }

    except HTTPException:
        raise

    except Exception as error:
        print(
            "[Quiz] Erreur lors de l'enregistrement du quiz : "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur lors de l'enregistrement du quiz.",
        )