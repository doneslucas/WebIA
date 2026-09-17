import json
import re

from typing import Callable

from langchain_ollama import OllamaEmbeddings, OllamaLLM

from app.database.connection import get_connection
from app.services.chroma import collection


CRITICAL_THRESHOLD = 20
GENERATION_THRESHOLD = 35
TARGET_QUESTION_COUNT = 50
QUESTION_LIMIT_PER_CHUNK = 5

BATCH_SIZE = 2
MAX_ATTEMPTS = 10
MAX_EMPTY_PASSES = 3

QUIZ_NUM_PREDICT = 1000


embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)

llm = OllamaLLM(
    model="llama3.2:latest",
    num_predict=QUIZ_NUM_PREDICT,
    format="json",
    temperature=0.5
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

        question_text = question.get("question")

        if not isinstance(
            question_text,
            str
        ):
            return False

        if not question_text.strip():
            return False

        options = question.get("options")

        if not isinstance(
            options,
            list
        ):
            return False

        if len(options) != 4:
            return False

        if not all(
            isinstance(option, str)
            and option.strip()
            for option in options
        ):
            return False

        normalized_options = [
            normalize_question(option)
            for option in options
        ]

        if len(
            set(normalized_options)
        ) != 4:
            return False

        correct_answer = question.get(
            "correct_answer"
        )

        if not isinstance(
            correct_answer,
            int
        ):
            return False

        if correct_answer not in {
            0,
            1,
            2,
            3
        }:
            return False

        explanation = question.get(
            "explanation"
        )

        if not isinstance(
            explanation,
            str
        ):
            return False

        if not explanation.strip():
            return False

    return True


def parse_quiz_response(response: str):
    cleaned_response = clean_json_response(
        response
    )

    try:

        data = json.loads(
            cleaned_response
        )

    except json.JSONDecodeError as error:

        raise ValueError(
            f"JSON invalide retourné par le LLM : {error}"
        )

    if not validate_quiz(data):

        raise ValueError(
            "Le format du quiz généré est invalide."
        )

    return data["questions"]


def get_documents_scope(
    document: str
):
    document_ids = None

    if document == "all":

        with get_connection() as conn:

            with conn.cursor() as cursor:

                cursor.execute(
                    """
                    SELECT id
                    FROM documents
                    ORDER BY id
                    """
                )

                rows = cursor.fetchall()

        document_ids = [
            row[0]
            for row in rows
        ]

    else:

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

        document_ids = [
            result[0]
        ]

    return document_ids


def get_available_chunks(
    document: str,
    difficulty: str
):
    """
    Retourne les chunks qui peuvent encore recevoir
    des questions pour la difficulté demandée.

    La limite de 5 questions est indépendante
    pour chaque difficulté.
    """

    document_ids = get_documents_scope(
        document
    )

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    dc.id,
                    dc.chroma_id,
                    COUNT(qq.id) AS difficulty_count
                FROM document_chunks dc

                LEFT JOIN quiz_questions qq
                    ON qq.chunk_id = dc.id
                    AND qq.difficulty = %s

                WHERE dc.document_id = ANY(%s)

                GROUP BY
                    dc.id,
                    dc.chroma_id

                HAVING COUNT(qq.id) < %s

                ORDER BY dc.id
                """,
                (
                    difficulty,
                    document_ids,
                    QUESTION_LIMIT_PER_CHUNK
                )
            )

            return cursor.fetchall()


def count_questions(
    document: str,
    difficulty: str
):
    document_ids = get_documents_scope(
        document
    )

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


def get_max_capacity(
    document: str
):
    """
    Capacité maximale pour une difficulté.

    Chaque difficulté possède sa propre capacité :

    nombre de chunks × 5 questions.
    """

    document_ids = get_documents_scope(
        document
    )

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
    document_ids = get_documents_scope(
        document
    )

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
    document_ids = get_documents_scope(
        document
    )

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


def get_chunk_context(
    chroma_id: str
):
    result = collection.get(
        ids=[chroma_id],
        include=["documents"]
    )

    documents = result.get(
        "documents",
        []
    )

    if not documents:

        raise ValueError(
            f"Chunk introuvable dans ChromaDB : {chroma_id}"
        )

    context = documents[0]

    if not isinstance(
        context,
        str
    ):
        raise ValueError(
            "Le contenu du chunk est invalide."
        )

    if not context.strip():
        raise ValueError(
            "Le chunk ne contient aucun texte."
        )

    return context


def build_excluded_questions(
    document: str,
    difficulty: str
):
    existing_questions = get_existing_questions(
        document,
        difficulty
    )

    return {
        normalize_question(
            question[1]
        )
        for question in existing_questions
    }


def generate_quiz_batch(
    context: str,
    difficulty: str,
    excluded_questions: set[str],
    batch_size: int = BATCH_SIZE
):
    last_error = None

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1
    ):

        variation_instructions = [
            """
Change complètement l'angle des questions.
Ne demande pas simplement une définition.
""",
            """
Pose des questions sur les conséquences,
les objectifs, les caractéristiques ou les mécanismes.
""",
            """
Utilise des situations concrètes de cybersécurité
lorsque le contenu source le permet.
""",
            """
Cherche des détails précis du contenu source
qui n'ont pas encore été utilisés.
""",
            """
Évite absolument les questions classiques
ou déjà vues et cherche un autre aspect du contenu.
""",
            """
Varie fortement la formulation et le concept testé.
Ne reformule pas une question précédente.
""",
            """
Utilise uniquement des informations précises
du contenu source mais explore un nouvel aspect.
""",
            """
Construis des questions différentes des questions
habituelles sur ce sujet.
""",
            """
Cherche un détail secondaire du contenu source
pour construire la question.
""",
            """
Dernière tentative : produis des questions
totalement nouvelles et non redondantes.
"""
        ]

        variation_instruction = (
            variation_instructions[
                min(
                    attempt - 1,
                    len(variation_instructions) - 1
                )
            ]
        )

        prompt = f"""
Tu es un expert en cybersécurité chargé de créer
des questions à choix multiple.

CONTENU SOURCE :
{context}

DIFFICULTÉ :
{difficulty}

NOMBRE DE QUESTIONS :
{batch_size}

Tu dois générer exactement {batch_size} question(s).

FORMAT OBLIGATOIRE :

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

RÈGLES ABSOLUES :

1. Retourne uniquement du JSON.
2. N'utilise jamais de Markdown.
3. Ne mets jamais le JSON dans ```json.
4. "questions" doit être une liste.
5. Chaque question doit contenir exactement 4 options.
6. Les 4 options doivent être différentes.
7. "correct_answer" doit être un entier : 0, 1, 2 ou 3.
8. L'option située à l'index correct_answer doit être la seule bonne réponse.
9. "explanation" doit expliquer clairement la bonne réponse.
10. Les questions doivent être basées uniquement sur le contenu source fourni.
11. Ne crée aucune information absente du contenu source.
12. La difficulté demandée doit être respectée.
13. Les questions doivent être réellement différentes entre elles.
14. Ne reformule pas simplement la même question.
15. Les options doivent être cohérentes avec la question.
16. La question et ses options doivent être rédigées dans la même langue que le contenu source.
17. Si la question demande un terme anglais, une option doit réellement contenir ce terme anglais.
18. Ne mets jamais une réponse qui contredit directement la question.
19. Ne mets jamais plusieurs réponses correctes.
20. Ne mets jamais une option vide.
21. Ne répète pas une question déjà générée.
22. Chaque question doit tester un aspect différent du contenu source.
23. Ne produis pas deux questions qui demandent essentiellement
    la même information.
24. Si une information a déjà été utilisée sous une forme
    évidente, choisis une autre information du contenu source.

INSTRUCTION DE VARIATION :

{variation_instruction}

IMPORTANT :

Le programme vérifiera lui-même les doublons.

Tu dois donc produire des questions nouvelles,
même si le contenu source est court.

Ne cherche pas à remplir artificiellement la quantité
demandée avec des reformulations.

Retourne uniquement l'objet JSON final.
"""

        try:

            response = llm.invoke(
                prompt
            )

            questions = parse_quiz_response(
                response
            )

            valid_questions = []

            local_questions = set(
                excluded_questions
            )

            for question in questions:

                normalized = normalize_question(
                    question["question"]
                )

                if normalized in local_questions:

                    print(
                        f"[Quiz] "
                        f"Tentative {attempt}/{MAX_ATTEMPTS} : "
                        f"question déjà existante rejetée."
                    )

                    continue

                local_questions.add(
                    normalized
                )

                valid_questions.append(
                    question
                )

                if len(
                    valid_questions
                ) >= batch_size:

                    break

            if valid_questions:

                return valid_questions

            last_error = (
                "Le LLM a retourné des questions "
                "mais elles étaient toutes déjà présentes."
            )

            print(
                f"[Quiz] "
                f"Tentative {attempt}/{MAX_ATTEMPTS} : "
                f"aucune nouvelle question."
            )

        except Exception as error:

            last_error = str(
                error
            )

            print(
                f"Erreur génération quiz "
                f"(tentative {attempt}/{MAX_ATTEMPTS}) : "
                f"{error}"
            )

    raise ValueError(
        "Impossible de générer un lot de questions valide."
        + (
            f" Dernière erreur : {last_error}"
            if last_error
            else ""
        )
    )


def save_questions(
    chunk_id: int,
    questions,
    difficulty: str
):
    saved_questions = []

    with get_connection() as conn:

        with conn.cursor() as cursor:

            # Vérification supplémentaire :
            # le chunk peut avoir été supprimé/recréé
            # entre get_available_chunks() et save_questions().
            cursor.execute(
                """
                SELECT id
                FROM document_chunks
                WHERE id = %s
                """,
                (chunk_id,)
            )

            chunk_exists = (
                cursor.fetchone()
                is not None
            )

            if not chunk_exists:

                print(
                    f"[Quiz] "
                    f"Chunk {chunk_id} introuvable "
                    f"dans document_chunks. "
                    f"Il a probablement été supprimé "
                    f"ou recréé pendant la génération. "
                    f"Lot ignoré."
                )

                return []

            for question in questions:

                normalized = normalize_question(
                    question["question"]
                )

                cursor.execute(
                    """
                    SELECT question
                    FROM quiz_questions
                    WHERE chunk_id = %s
                      AND difficulty = %s
                    """,
                    (
                        chunk_id,
                        difficulty
                    )
                )

                existing_questions = (
                    cursor.fetchall()
                )

                duplicate = False

                for row in existing_questions:

                    if normalize_question(
                        row[0]
                    ) == normalized:

                        duplicate = True
                        break

                if duplicate:
                    continue

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM quiz_questions
                    WHERE chunk_id = %s
                      AND difficulty = %s
                    """,
                    (
                        chunk_id,
                        difficulty
                    )
                )

                current_count = (
                    cursor.fetchone()[0]
                )

                if (
                    current_count
                    >= QUESTION_LIMIT_PER_CHUNK
                ):
                    continue

                # Nouvelle vérification juste avant
                # l'insertion afin de réduire le risque
                # qu'un chunk supprimé entre-temps
                # provoque une violation de clé étrangère.
                cursor.execute(
                    """
                    SELECT id
                    FROM document_chunks
                    WHERE id = %s
                    """,
                    (chunk_id,)
                )

                if cursor.fetchone() is None:

                    print(
                        f"[Quiz] "
                        f"Chunk {chunk_id} supprimé "
                        f"avant l'insertion. "
                        f"Question ignorée."
                    )

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

                question_id = (
                    cursor.fetchone()[0]
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
    target_count: int,
    progress_callback: Callable[[int], None] | None = None
):
    """
    Génère progressivement la banque d'une difficulté.

    Un échec du LLM sur un chunk ne bloque pas
    les autres chunks.

    Les lots peuvent être partiels.

    La génération s'arrête uniquement lorsqu'il n'existe
    plus de capacité disponible ou lorsque plusieurs
    passages complets n'ont produit aucune nouvelle
    question.

    progress_callback est appelé après chaque progression
    réelle de la banque.
    """

    generated_count = count_questions(
        document,
        difficulty
    )

    print(
        f"[{difficulty.upper()}] "
        f"Banque actuelle : "
        f"{generated_count}/{target_count}"
    )

    if progress_callback is not None:

        progress_callback(
            generated_count
        )

    empty_passes = 0

    while generated_count < target_count:

        chunks = get_available_chunks(
            document,
            difficulty
        )

        if not chunks:

            print(
                f"[{difficulty.upper()}] "
                f"Aucun chunk disponible."
            )

            break

        generated_in_pass = False

        for chunk in chunks:

            if generated_count >= target_count:
                break

            chunk_id = chunk[0]
            chroma_id = chunk[1]
            difficulty_count = chunk[2]

            remaining_capacity = (
                QUESTION_LIMIT_PER_CHUNK
                - difficulty_count
            )

            if remaining_capacity <= 0:
                continue

            batch_size = min(
                BATCH_SIZE,
                remaining_capacity,
                target_count - generated_count
            )

            try:

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
                    excluded_questions=excluded_questions,
                    batch_size=batch_size
                )

                questions = questions[
                    :batch_size
                ]

                saved_questions = save_questions(
                    chunk_id=chunk_id,
                    questions=questions,
                    difficulty=difficulty
                )

                if saved_questions:

                    generated_count += len(
                        saved_questions
                    )

                    generated_in_pass = True

                    print(
                        f"[{difficulty.upper()}] "
                        f"+{len(saved_questions)} "
                        f"questions "
                        f"→ {generated_count}/{target_count}"
                    )

                    if progress_callback is not None:

                        progress_callback(
                            generated_count
                        )

            except Exception as error:

                print(
                    f"[{difficulty.upper()}] "
                    f"Chunk {chunk_id} ignoré : "
                    f"{error}"
                )

                continue

        if generated_in_pass:

            empty_passes = 0

        else:

            empty_passes += 1

            print(
                f"[{difficulty.upper()}] "
                f"Aucune nouvelle question "
                f"pendant ce passage "
                f"({empty_passes}/{MAX_EMPTY_PASSES})."
            )

            if empty_passes >= MAX_EMPTY_PASSES:

                print(
                    f"[{difficulty.upper()}] "
                    f"Arrêt de sécurité : "
                    f"aucune progression après "
                    f"{MAX_EMPTY_PASSES} passages."
                )

                break

    print(
        f"[{difficulty.upper()}] "
        f"Banque terminée : "
        f"{generated_count} questions"
    )

    if progress_callback is not None:

        progress_callback(
            generated_count
        )

    return generated_count


def get_random_questions(
    document: str,
    difficulty: str,
    question_count: int,
    user_id: int
):
    document_ids = get_documents_scope(
        document
    )

    seen_question_ids = (
        get_user_seen_question_ids(
            user_id=user_id,
            document=document,
            difficulty=difficulty
        )
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

        if isinstance(
            options,
            str
        ):

            options = json.loads(
                options
            )

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
    if answer not in {
        0,
        1,
        2,
        3
    }:

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

    correct_answer = int(
        result[0]
    )

    explanation = result[1]

    return {
        "is_correct": (
            answer == correct_answer
        ),
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