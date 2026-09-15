import json
import re

from langchain_ollama import OllamaEmbeddings, OllamaLLM

from app.database.connection import get_connection
from app.services.chroma import collection


CRITICAL_THRESHOLD = 20
GENERATION_THRESHOLD = 35
TARGET_QUESTION_COUNT = 50
QUESTION_LIMIT_PER_CHUNK = 5

BATCH_SIZE = 5
MAX_ATTEMPTS = 3
QUIZ_NUM_PREDICT = 1000


embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)

llm = OllamaLLM(
    model="llama3.2:latest",
    num_predict=QUIZ_NUM_PREDICT,
    format="json",
    temperature=0.2
)


def normalize_question(question: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        question.strip().lower()
    )


def clean_json_response(response: str) -> str:
    response = response.strip()

    if response.startswith("```"):
        response = re.sub(
            r"^```(?:json)?\s*",
            "",
            response,
            flags=re.IGNORECASE
        )
        response = re.sub(
            r"\s*```$",
            "",
            response
        )

    start = response.find("{")
    end = response.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(
            "La réponse du LLM ne contient pas de JSON valide."
        )

    return response[start:end + 1]


def validate_quiz(data):
    if not isinstance(data, dict):
        return False

    questions = data.get("questions")

    if not isinstance(questions, list):
        return False

    if not questions:
        return False

    for question in questions:
        if not isinstance(question, dict):
            return False

        if not isinstance(question.get("question"), str):
            return False

        if not isinstance(question.get("options"), list):
            return False

        if len(question["options"]) != 4:
            return False

        if not all(
            isinstance(option, str)
            for option in question["options"]
        ):
            return False

        correct_answer = question.get("correct_answer")

        if not isinstance(correct_answer, int):
            return False

        if correct_answer not in {0, 1, 2, 3}:
            return False

        if not isinstance(
            question.get("explanation"),
            str
        ):
            return False

    return True


def parse_quiz_response(response: str):
    cleaned_response = clean_json_response(response)

    try:
        data = json.loads(cleaned_response)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"JSON invalide retourné par le LLM : {error}"
        )

    if not validate_quiz(data):
        raise ValueError(
            "Le format du quiz généré est invalide."
        )

    return data["questions"]


def get_documents_scope(document: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM documents
                WHERE file_name = %s
                """,
                (document,)
            )

            result = cursor.fetchone()

    if result is None:
        raise ValueError(
            f"Document introuvable : {document}"
        )

    return [result[0]]


def get_available_chunks(document: str):
    document_ids = get_documents_scope(document)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    chroma_id,
                    question_count,
                    question_limit
                FROM document_chunks
                WHERE document_id = ANY(%s)
                  AND question_count < question_limit
                ORDER BY id
                """,
                (document_ids,)
            )

            return cursor.fetchall()


def count_questions(document: str, difficulty: str):
    document_ids = get_documents_scope(document)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quiz_questions qq
                JOIN document_chunks dc
                    ON qq.chunk_id = dc.id
                WHERE dc.document_id = ANY(%s)
                  AND qq.difficulty = %s
                """,
                (
                    document_ids,
                    difficulty
                )
            )

            return cursor.fetchone()[0]


def get_max_capacity(document: str):
    document_ids = get_documents_scope(document)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(
                    SUM(question_limit),
                    0
                )
                FROM document_chunks
                WHERE document_id = ANY(%s)
                """,
                (document_ids,)
            )

            return cursor.fetchone()[0]


def get_existing_questions(
    document: str,
    difficulty: str
):
    document_ids = get_documents_scope(document)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    qq.id,
                    qq.question
                FROM quiz_questions qq
                JOIN document_chunks dc
                    ON qq.chunk_id = dc.id
                WHERE dc.document_id = ANY(%s)
                  AND qq.difficulty = %s
                """,
                (
                    document_ids,
                    difficulty
                )
            )

            return cursor.fetchall()


def get_user_seen_question_ids(
    user_id: int,
    document: str,
    difficulty: str
):
    document_ids = get_documents_scope(document)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT qaq.question_id
                FROM quiz_attempt_questions qaq
                JOIN quiz_results qr
                    ON qaq.quiz_result_id = qr.id
                JOIN quiz_questions qq
                    ON qaq.question_id = qq.id
                JOIN document_chunks dc
                    ON qq.chunk_id = dc.id
                WHERE qr.user_id = %s
                  AND dc.document_id = ANY(%s)
                  AND qq.difficulty = %s
                """,
                (
                    user_id,
                    document_ids,
                    difficulty
                )
            )

            return {
                row[0]
                for row in cursor.fetchall()
            }


def get_chunk_context(chroma_id: str):
    result = collection.get(
        ids=[chroma_id],
        include=["documents"]
    )

    documents = result.get("documents", [])

    if not documents:
        raise ValueError(
            f"Chunk introuvable dans ChromaDB : {chroma_id}"
        )

    return documents[0]


def build_excluded_questions(
    document: str,
    difficulty: str
):
    existing_questions = get_existing_questions(
        document,
        difficulty
    )

    return {
        normalize_question(question[1])
        for question in existing_questions
    }


def generate_quiz_batch(
    context: str,
    difficulty: str,
    excluded_questions: set[str]
):
    prompt = f"""
Tu es un expert en cybersécurité chargé de créer des questions
à choix multiple à partir du contenu fourni.

Contenu du document :
{context}

Génère exactement {BATCH_SIZE} questions.

Difficulté demandée :
{difficulty}

Chaque question doit respecter exactement cette structure :

{{
  "questions": [
    {{
      "question": "Question...",
      "options": [
        "Réponse A",
        "Réponse B",
        "Réponse C",
        "Réponse D"
      ],
      "correct_answer": 0,
      "explanation": "Explication..."
    }}
  ]
}}

Règles :

- Une seule réponse doit être correcte.
- correct_answer doit être 0, 1, 2 ou 3.
- Les quatre options doivent être différentes.
- Les questions doivent être basées uniquement sur le contenu fourni.
- Ne crée pas de question dont la réponse n'est pas justifiable par le contenu.
- Ne répète pas les questions suivantes :

{json.dumps(
    list(excluded_questions),
    ensure_ascii=False
)}

Retourne uniquement le JSON.
"""

    for attempt in range(1, MAX_ATTEMPTS + 1):

        try:
            response = llm.invoke(prompt)

            questions = parse_quiz_response(
                response
            )

            valid_questions = []

            for question in questions:

                normalized = normalize_question(
                    question["question"]
                )

                if normalized in excluded_questions:
                    continue

                if any(
                    normalize_question(
                        existing["question"]
                    ) == normalized
                    for existing in valid_questions
                ):
                    continue

                valid_questions.append(question)

                if len(valid_questions) >= BATCH_SIZE:
                    break

            if valid_questions:
                return valid_questions

        except Exception as error:

            print(
                f"Erreur génération quiz "
                f"(tentative {attempt}/{MAX_ATTEMPTS}) : "
                f"{error}"
            )

    raise ValueError(
        "Impossible de générer un lot de questions valide."
    )


def save_questions(
    chunk_id: int,
    questions,
    difficulty: str
):
    saved_questions = []

    with get_connection() as conn:
        with conn.cursor() as cursor:

            for question in questions:

                normalized = normalize_question(
                    question["question"]
                )

                cursor.execute(
                    """
                    SELECT id
                    FROM quiz_questions
                    WHERE chunk_id = %s
                      AND difficulty = %s
                    """,
                    (
                        chunk_id,
                        difficulty
                    )
                )

                existing = cursor.fetchall()

                duplicate = False

                for row in existing:

                    cursor.execute(
                        """
                        SELECT question
                        FROM quiz_questions
                        WHERE id = %s
                        """,
                        (row[0],)
                    )

                    existing_question = cursor.fetchone()

                    if existing_question is None:
                        continue

                    if normalize_question(
                        existing_question[0]
                    ) == normalized:
                        duplicate = True
                        break

                if duplicate:
                    continue

                cursor.execute(
                    """
                    INSERT INTO quiz_questions (
                        chunk_id,
                        question,
                        options,
                        correct_answer,
                        explanation,
                        difficulty
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id
                    """,
                    (
                        chunk_id,
                        question["question"],
                        json.dumps(
                            question["options"],
                            ensure_ascii=False
                        ),
                        str(
                            question["correct_answer"]
                        ),
                        question["explanation"],
                        difficulty
                    )
                )

                question_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    UPDATE document_chunks
                    SET question_count = question_count + 1
                    WHERE id = %s
                    """,
                    (chunk_id,)
                )

                saved_questions.append(
                    {
                        "id": question_id,
                        "question": question["question"],
                        "options": question["options"],
                        "correct_answer": question["correct_answer"],
                        "explanation": question["explanation"],
                        "difficulty": difficulty
                    }
                )

            conn.commit()

    return saved_questions


def generate_questions_for_bank(
    document: str,
    difficulty: str,
    target_count: int
):
    generated_count = count_questions(
        document,
        difficulty
    )

    while generated_count < target_count:

        chunks = get_available_chunks(document)

        if not chunks:
            break

        generated_in_batch = False

        for chunk in chunks:

            if generated_count >= target_count:
                break

            chunk_id = chunk[0]
            chroma_id = chunk[1]
            question_count = chunk[2]
            question_limit = chunk[3]

            remaining_capacity = (
                question_limit - question_count
            )

            if remaining_capacity <= 0:
                continue

            batch_size = min(
                BATCH_SIZE,
                remaining_capacity,
                target_count - generated_count
            )

            context = get_chunk_context(
                chroma_id
            )

            excluded_questions = (
                build_excluded_questions(
                    document,
                    difficulty
                )
            )

            questions = generate_quiz_batch(
                context=context,
                difficulty=difficulty,
                excluded_questions=excluded_questions
            )

            questions = questions[:batch_size]

            saved_questions = save_questions(
                chunk_id=chunk_id,
                questions=questions,
                difficulty=difficulty
            )

            if saved_questions:
                generated_count += len(
                    saved_questions
                )
                generated_in_batch = True

        if not generated_in_batch:
            break

    return generated_count


def get_random_questions(
    document: str,
    difficulty: str,
    question_count: int,
    user_id: int
):
    document_ids = get_documents_scope(document)

    seen_question_ids = get_user_seen_question_ids(
        user_id=user_id,
        document=document,
        difficulty=difficulty
    )

    with get_connection() as conn:
        with conn.cursor() as cursor:

            if seen_question_ids:

                cursor.execute(
                    """
                    SELECT
                        qq.id,
                        qq.question,
                        qq.options,
                        qq.difficulty
                    FROM quiz_questions qq
                    JOIN document_chunks dc
                        ON qq.chunk_id = dc.id
                    WHERE dc.document_id = ANY(%s)
                      AND qq.difficulty = %s
                      AND NOT (qq.id = ANY(%s))
                    ORDER BY RANDOM()
                    LIMIT %s
                    """,
                    (
                        document_ids,
                        difficulty,
                        list(seen_question_ids),
                        question_count
                    )
                )

            else:

                cursor.execute(
                    """
                    SELECT
                        qq.id,
                        qq.question,
                        qq.options,
                        qq.difficulty
                    FROM quiz_questions qq
                    JOIN document_chunks dc
                        ON qq.chunk_id = dc.id
                    WHERE dc.document_id = ANY(%s)
                      AND qq.difficulty = %s
                    ORDER BY RANDOM()
                    LIMIT %s
                    """,
                    (
                        document_ids,
                        difficulty,
                        question_count
                    )
                )

            rows = cursor.fetchall()

    questions = []

    for row in rows:

        options = row[2]

        if isinstance(options, str):
            options = json.loads(options)

        questions.append(
            {
                "id": row[0],
                "question": row[1],
                "options": options,
                "difficulty": row[3]
            }
        )

    return questions


def check_quiz_answer(
    question_id: int,
    answer: int
):
    if answer not in {0, 1, 2, 3}:
        raise ValueError(
            "La réponse doit être un entier compris entre 0 et 3."
        )

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    correct_answer,
                    explanation
                FROM quiz_questions
                WHERE id = %s
                """,
                (question_id,)
            )

            result = cursor.fetchone()

    if result is None:
        raise ValueError(
            "Question introuvable."
        )

    correct_answer = int(result[0])
    explanation = result[1]

    return {
        "is_correct": answer == correct_answer,
        "correct_answer": correct_answer,
        "explanation": explanation
    }


def generate_quiz(
    document: str,
    question_count: int,
    difficulty: str,
    user_id: int
):
    if question_count not in {
        5,
        10,
        15,
        20
    }:
        raise ValueError(
            "Le nombre de questions doit être 5, 10, 15 ou 20."
        )

    if difficulty not in {
        "easy",
        "medium",
        "hard"
    }:
        raise ValueError(
            "La difficulté doit être easy, medium ou hard."
        )

    max_capacity = get_max_capacity(
        document
    )

    if max_capacity == 0:
        raise ValueError(
            "Aucun chunk disponible pour ce document."
        )

    current_count = count_questions(
        document,
        difficulty
    )

    target_bank_size = min(
        TARGET_QUESTION_COUNT,
        max_capacity
    )

    if current_count < target_bank_size:

        print(
            f"Banque {difficulty} : "
            f"{current_count}/{target_bank_size} questions."
        )

        generate_questions_for_bank(
            document=document,
            difficulty=difficulty,
            target_count=target_bank_size
        )

    questions = get_random_questions(
        document=document,
        difficulty=difficulty,
        question_count=question_count,
        user_id=user_id
    )

    if len(questions) < question_count:

        raise ValueError(
            "Pas assez de questions non vues disponibles "
            "pour cet utilisateur."
        )

    return {
        "questions": questions
    }