import json
import re
from typing import Optional

from langchain_ollama import OllamaLLM

from app.database.connection import get_connection
from app.services.chroma import collection
from app.services.categories import get_category_by_id
from app.services.task_manager import task_manager


# ============================================================
# CONFIGURATION
# ============================================================

CRITICAL_THRESHOLD = 20
GENERATION_THRESHOLD = 35

TARGET_QUESTION_COUNT = 50

# Maximum par difficulté et par chunk.
QUESTION_LIMIT_PER_CHUNK = 5

# Maximum toutes difficultés confondues et par chunk.
TOTAL_QUESTION_LIMIT_PER_CHUNK = 15

BATCH_SIZE = 2
MAX_ATTEMPTS = 3
MAX_EMPTY_PASSES = 3
QUIZ_NUM_PREDICT = 1000

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


# ============================================================
# LLM
# ============================================================

llm = OllamaLLM(
    model="llama3.2:latest",
    num_predict=QUIZ_NUM_PREDICT,
    format="json",
    temperature=0.2,
)


# ============================================================
# OUTILS
# ============================================================

def normalize_question(question: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        question.strip().lower(),
    )


def clean_json_response(response: str) -> str:
    if not isinstance(response, str):
        raise ValueError("La réponse du LLM n'est pas du texte.")

    response = response.strip()

    if response.startswith("```"):
        response = re.sub(
            r"^```(?:json)?\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )
        response = re.sub(r"\s*```$", "", response)

    start = response.find("{")
    end = response.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError(
            "La réponse du LLM ne contient pas d'objet JSON exploitable."
        )

    return response[start:end + 1]


def validate_difficulty(difficulty: str):
    if difficulty not in VALID_DIFFICULTIES:
        raise ValueError(
            "La difficulté doit être easy, medium ou hard."
        )


def validate_question_count(question_count: int):
    if question_count not in VALID_QUESTION_COUNTS:
        raise ValueError(
            "Le nombre de questions doit être 5, 10, 15 ou 20."
        )


# ============================================================
# VALIDATION DES QUESTIONS
# ============================================================

def get_question_validation_error(question) -> Optional[str]:
    """Retourne la raison du rejet, ou None si la question est valide."""
    if not isinstance(question, dict):
        return "La question n'est pas un objet JSON."

    question_text = question.get("question")

    if not isinstance(question_text, str):
        return "Le champ 'question' est absent ou invalide."

    if not question_text.strip():
        return "Le texte de la question est vide."

    options = question.get("options")

    if not isinstance(options, list):
        return "Le champ 'options' n'est pas une liste."

    if len(options) != 4:
        return (
            f"La question contient {len(options)} options "
            "au lieu de 4."
        )

    if not all(
        isinstance(option, str) and option.strip()
        for option in options
    ):
        return "Au moins une option est vide ou invalide."

    normalized_options = [
        normalize_question(option)
        for option in options
    ]

    if len(set(normalized_options)) != 4:
        return "Les quatre options ne sont pas différentes."

    correct_answer = question.get("correct_answer")

    if (
        isinstance(correct_answer, str)
        and correct_answer.strip() in {"0", "1", "2", "3"}
    ):
        question["correct_answer"] = int(correct_answer.strip())
        correct_answer = question["correct_answer"]

    if (
        not isinstance(correct_answer, int)
        or isinstance(correct_answer, bool)
    ):
        return (
            "Le champ 'correct_answer' doit être "
            "un entier compris entre 0 et 3."
        )

    if correct_answer not in {0, 1, 2, 3}:
        return "Le champ 'correct_answer' est en dehors de l'intervalle autorisé."

    explanation = question.get("explanation")

    if not isinstance(explanation, str) or not explanation.strip():
        return "L'explication est absente, invalide ou vide."

    return None


def is_valid_generated_question(question) -> bool:
    return get_question_validation_error(question) is None


def validate_quiz(data):
    """Vérifie la structure générale d'une réponse du modèle."""
    return (
        isinstance(data, dict)
        and isinstance(data.get("questions"), list)
        and bool(data["questions"])
    )


def parse_quiz_response(response: str):
    cleaned_response = clean_json_response(response)

    try:
        data = json.loads(cleaned_response)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"JSON invalide retourné par le LLM : {error}"
        ) from error

    if not validate_quiz(data):
        raise ValueError(
            "Le JSON ne contient pas de liste 'questions' exploitable."
        )

    return data["questions"]


# ============================================================
# DOCUMENTS
# ============================================================

def get_documents_scope(document: str):
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

        return [row[0] for row in rows]

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM documents
                WHERE file_name = %s
                """,
                (document,),
            )
            result = cursor.fetchone()

    if result is None:
        raise ValueError(f"Document introuvable : {document}")

    return [result[0]]


# ============================================================
# CATÉGORIES
# ============================================================

def validate_category_ids(
    category_ids: Optional[list[int]],
):
    if category_ids is None:
        return []

    if not isinstance(category_ids, list):
        raise ValueError("category_ids doit être une liste.")

    if not category_ids:
        return []

    normalized_ids = []

    for category_id in category_ids:
        if (
            not isinstance(category_id, int)
            or isinstance(category_id, bool)
        ):
            raise ValueError("Chaque category_id doit être un entier.")

        category = get_category_by_id(category_id)

        if category is None:
            raise ValueError(f"Catégorie introuvable : {category_id}")

        normalized_ids.append(category_id)

    return list(dict.fromkeys(normalized_ids))


def get_category_filter_sql(
    category_ids: Optional[list[int]],
):
    if not category_ids:
        return "", []

    return (
        """
        AND dc.category_id = ANY(%s)
        """,
        [category_ids],
    )


# ============================================================
# CHUNKS DISPONIBLES POUR LA GÉNÉRATION
# ============================================================

def get_available_chunks(
    document: str,
    difficulty: str,
    category_ids: Optional[list[int]] = None,
):
    """Retourne les chunks classés qui ont encore une capacité disponible."""
    validate_difficulty(difficulty)
    category_ids = validate_category_ids(category_ids)
    document_ids = get_documents_scope(document)
    category_sql, category_params = get_category_filter_sql(category_ids)

    query = f"""
        SELECT
            dc.id,
            dc.chroma_id,
            dc.category_id,
            COUNT(qq.id) AS difficulty_count
        FROM document_chunks dc
        LEFT JOIN quiz_questions qq
            ON qq.chunk_id = dc.id
           AND qq.difficulty = %s
        WHERE dc.document_id = ANY(%s)
          AND dc.category_id IS NOT NULL
          {category_sql}
        GROUP BY dc.id, dc.chroma_id, dc.category_id, dc.question_limit
        HAVING COUNT(qq.id) < LEAST(
                   COALESCE(NULLIF(dc.question_limit, 0), %s),
                   %s
               )
           AND (
               SELECT COUNT(*)
               FROM quiz_questions qq_total
               WHERE qq_total.chunk_id = dc.id
           ) < LEAST(
                   COALESCE(NULLIF(dc.question_limit, 0), %s),
                   %s
               )
        ORDER BY dc.id
    """

    params = [
        difficulty,
        document_ids,
        *category_params,
        TOTAL_QUESTION_LIMIT_PER_CHUNK,
        QUESTION_LIMIT_PER_CHUNK,
        TOTAL_QUESTION_LIMIT_PER_CHUNK,
        TOTAL_QUESTION_LIMIT_PER_CHUNK,
    ]

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


# ============================================================
# COMPTAGE DE LA BANQUE
# ============================================================

def count_questions(
    difficulty: str,
    category_ids: Optional[list[int]] = None,
    document: Optional[str] = None,
):
    validate_difficulty(difficulty)
    category_ids = validate_category_ids(category_ids)

    category_sql, category_params = get_category_filter_sql(category_ids)
    document_sql = ""
    document_params = []

    if document is not None:
        document_ids = get_documents_scope(document)
        document_sql = "AND dc.document_id = ANY(%s)"
        document_params = [document_ids]

    query = f"""
        SELECT COUNT(*)
        FROM quiz_questions qq
        JOIN document_chunks dc ON qq.chunk_id = dc.id
        WHERE qq.difficulty = %s
          AND dc.category_id IS NOT NULL
          {document_sql}
          {category_sql}
    """

    params = [
        difficulty,
        *document_params,
        *category_params,
    ]

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()[0]


def get_max_capacity(
    difficulty: Optional[str] = None,
    category_ids: Optional[list[int]] = None,
    document: Optional[str] = None,
):
    """Calcule la capacité théorique des chunks classifiés."""
    if difficulty is not None:
        validate_difficulty(difficulty)

    category_ids = validate_category_ids(category_ids)
    category_sql, category_params = get_category_filter_sql(category_ids)

    document_sql = ""
    document_params = []

    if document is not None:
        document_ids = get_documents_scope(document)
        document_sql = "AND dc.document_id = ANY(%s)"
        document_params = [document_ids]

    per_chunk_cap = (
        QUESTION_LIMIT_PER_CHUNK
        if difficulty is not None
        else TOTAL_QUESTION_LIMIT_PER_CHUNK
    )

    query = f"""
        SELECT COALESCE(
            SUM(
                LEAST(
                    COALESCE(NULLIF(dc.question_limit, 0), %s),
                    %s
                )
            ),
            0
        )
        FROM document_chunks dc
        WHERE dc.category_id IS NOT NULL
          {document_sql}
          {category_sql}
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                [
                    TOTAL_QUESTION_LIMIT_PER_CHUNK,
                    per_chunk_cap,
                    *document_params,
                    *category_params,
                ],
            )
            return cursor.fetchone()[0]


# ============================================================
# STATUT DE LA BANQUE
# ============================================================

def get_bank_status(
    category_ids: Optional[list[int]] = None,
):
    category_ids = validate_category_ids(category_ids)
    status = {}

    for difficulty in VALID_DIFFICULTIES:
        count = count_questions(
            difficulty=difficulty,
            category_ids=category_ids,
        )

        capacity = get_max_capacity(
            difficulty=difficulty,
            category_ids=category_ids,
        )

        target = min(TARGET_QUESTION_COUNT, capacity)

        status[difficulty] = {
            "current": count,
            "target": target,
            "capacity": capacity,
            "complete": count >= target,
            "critical": count < CRITICAL_THRESHOLD,
            "needs_generation": count < GENERATION_THRESHOLD,
            "remaining": max(0, target - count),
        }

    return status


def get_category_bank_status(
    category_ids: list[int],
):
    category_ids = validate_category_ids(category_ids)
    result = {}

    for category_id in category_ids:
        result[category_id] = {}

        for difficulty in VALID_DIFFICULTIES:
            count = count_questions(
                difficulty=difficulty,
                category_ids=[category_id],
            )

            capacity = get_max_capacity(
                difficulty=difficulty,
                category_ids=[category_id],
            )

            target = min(TARGET_QUESTION_COUNT, capacity)

            result[category_id][difficulty] = {
                "current": count,
                "target": target,
                "capacity": capacity,
                "complete": count >= target,
                "critical": count < CRITICAL_THRESHOLD,
                "needs_generation": count < GENERATION_THRESHOLD,
                "remaining": max(0, target - count),
            }

    return result


# ============================================================
# QUESTIONS EXISTANTES ET DOUBLONS
# ============================================================

def get_existing_questions(
    category_ids: Optional[list[int]] = None,
    document: Optional[str] = None,
):
    """Récupère les questions présentes, éventuellement par document/catégorie."""
    category_ids = validate_category_ids(category_ids)
    category_sql, category_params = get_category_filter_sql(category_ids)

    document_sql = ""
    document_params = []

    if document is not None:
        document_ids = get_documents_scope(document)
        document_sql = "AND dc.document_id = ANY(%s)"
        document_params = [document_ids]

    query = f"""
        SELECT qq.id, qq.question, qq.difficulty
        FROM quiz_questions qq
        JOIN document_chunks dc ON qq.chunk_id = dc.id
        WHERE 1 = 1
          {document_sql}
          {category_sql}
        ORDER BY qq.id DESC
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                [*document_params, *category_params],
            )
            return cursor.fetchall()


def build_excluded_questions(
    category_ids: Optional[list[int]] = None,
    document: Optional[str] = None,
):
    rows = get_existing_questions(
        category_ids=category_ids,
        document=document,
    )

    return {
        normalize_question(row[1])
        for row in rows
        if isinstance(row[1], str) and row[1].strip()
    }


# ============================================================
# CONTEXTE DU CHUNK CHROMADB
# ============================================================

def get_chunk_context(chroma_id: str):
    result = collection.get(
        ids=[chroma_id],
        include=["documents"],
    )

    documents = result.get("documents", [])

    if not documents:
        raise ValueError(f"Chunk introuvable dans ChromaDB : {chroma_id}")

    context = documents[0]

    if not isinstance(context, str):
        raise ValueError("Le contenu du chunk est invalide.")

    if not context.strip():
        raise ValueError("Le chunk ne contient aucun texte.")

    return context


# ============================================================
# GÉNÉRATION LLM
# ============================================================

def generate_quiz_batch(
    context: str,
    difficulty: str,
    category_name: Optional[str],
    excluded_questions: set[str],
    batch_size: int = BATCH_SIZE,
):
    validate_difficulty(difficulty)

    if not isinstance(context, str) or not context.strip():
        raise ValueError("Le contenu source est vide.")

    if batch_size < 1:
        raise ValueError("Le nombre de questions demandé doit être positif.")

    category_instruction = (
        category_name if category_name else "Aucune catégorie spécifique"
    )

    # Conserve une liste limitée pour éviter un prompt initial trop volumineux.
    # Les questions rejetées seront ajoutées explicitement lors des relances.
    excluded_sample = sorted(excluded_questions)[:60]

    prompt = f"""
Tu es un expert chargé de créer des questions de cybersécurité
à partir d'un document source.

CONTENU SOURCE :
{context}

CATÉGORIE :
{category_instruction}

DIFFICULTÉ DEMANDÉE :
{difficulty}

NOMBRE MAXIMAL DE QUESTIONS :
{batch_size}

DÉFINITION DES DIFFICULTÉS :
- easy : compréhension directe d'une information présente dans le document.
- medium : compréhension et interprétation d'informations du document.
- hard : analyse ou mise en relation d'informations du document,
  sans connaissances externes ni informations inventées.

RÈGLE FONDAMENTALE :
Utilise UNIQUEMENT les informations présentes dans le contenu source.
N'ajoute aucune connaissance externe et n'invente aucun fait.
Si le contenu est insuffisant, retourne uniquement les questions fiables.
Si aucune question fiable n'est possible, retourne {{"questions": []}}.

RÈGLES ANTI-DOUBLONS :
- Ne reproduis aucune question déjà utilisée.
- Évite de reformuler simplement une question existante.
- Cherche des informations différentes dans le contenu source.
- Si plusieurs questions sont demandées, varie les informations évaluées.
- Ne crée pas artificiellement de questions si le document ne le permet pas.

FORMAT JSON OBLIGATOIRE :
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
      "explanation": "Explication fondée sur le contenu source."
    }}
  ]
}}

RÈGLES DE VALIDATION :
1. Retourne uniquement un objet JSON valide, sans Markdown.
2. "questions" doit être une liste.
3. Génère au maximum {batch_size} questions.
4. Chaque question doit avoir un texte non vide.
5. Chaque question doit contenir exactement quatre options.
6. Les quatre options doivent être différentes et non vides.
7. Une seule option est correcte.
8. "correct_answer" est l'index de la bonne réponse : 0, 1, 2 ou 3.
9. "explanation" doit être non vide et justifiée par le document.
10. Respecte strictement la difficulté demandée.
11. N'utilise aucune connaissance externe.
12. Écris dans la langue du document.

QUESTIONS DÉJÀ UTILISÉES À NE PAS REPRODUIRE :
{json.dumps(excluded_sample, ensure_ascii=False)}

Retourne uniquement l'objet JSON final.
"""

    last_error = None
    rejected_questions = set()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        retry_prompt = prompt

        if attempt > 1:
            retry_prompt += f"""

CORRECTION OBLIGATOIRE DE TA RÉPONSE PRÉCÉDENTE :
La tentative précédente n'a pas produit suffisamment de questions exploitables.
Erreur détectée : {last_error}

QUESTIONS PRÉCÉDEMMENT REJETÉES :
{json.dumps(sorted(rejected_questions), ensure_ascii=False)}

Consignes supplémentaires :
- Ne reproduis aucune des questions rejetées ci-dessus.
- Ne te contente pas de modifier quelques mots d'une question rejetée.
- Cherche un autre fait ou un autre aspect précis du contenu source.
- Respecte exactement le format JSON, les quatre options et la difficulté demandée.
- Si aucune nouvelle question fiable n'est possible, retourne
  {{"questions": []}}.
- N'ajoute aucun texte en dehors du JSON.
"""

        try:
            response = llm.invoke(retry_prompt)
            questions = parse_quiz_response(response)

            valid_questions = []
            local_questions = set(excluded_questions)
            rejected_count = 0
            rejection_reasons = {}

            for question in questions:
                validation_error = get_question_validation_error(question)

                if validation_error is not None:
                    rejected_count += 1
                    rejection_reasons[validation_error] = (
                        rejection_reasons.get(validation_error, 0) + 1
                    )
                    continue

                normalized = normalize_question(question["question"])

                if normalized in local_questions:
                    rejected_count += 1
                    reason = "Question déjà utilisée."
                    rejection_reasons[reason] = (
                        rejection_reasons.get(reason, 0) + 1
                    )

                    # Transmet les questions effectivement rejetées
                    # au prompt des tentatives suivantes.
                    rejected_questions.add(normalized)
                    continue

                local_questions.add(normalized)
                valid_questions.append(question)

                if len(valid_questions) >= batch_size:
                    break

            if valid_questions:
                if rejected_count:
                    print(
                        "[QUIZ] "
                        f"{rejected_count} question(s) rejetée(s)."
                    )

                    for reason, count in rejection_reasons.items():
                        print(f"[QUIZ] Rejet ({count}) : {reason}")

                if len(valid_questions) < batch_size:
                    print(
                        "[QUIZ] Lot partiel accepté : "
                        f"{len(valid_questions)}/{batch_size} question(s)."
                    )

                return valid_questions

            if not questions:
                last_error = "Le LLM a retourné une liste de questions vide."
            else:
                last_error = (
                    f"Aucune question exploitable parmi {len(questions)}. "
                    f"Motifs : {rejection_reasons}"
                )

            print(
                f"[QUIZ] Tentative {attempt}/{MAX_ATTEMPTS} : {last_error}"
            )

        except Exception as error:
            last_error = str(error)
            print(
                "[QUIZ] Erreur de génération "
                f"(tentative {attempt}/{MAX_ATTEMPTS}) : {last_error}"
            )

    raise ValueError(
        "Impossible de générer un lot de questions valide. "
        f"Dernière erreur : {last_error}"
    )

# ============================================================
# SAUVEGARDE DES QUESTIONS
# ============================================================

def save_questions(
    chunk_id: int,
    questions,
    difficulty: str,
):
    """Sauvegarde avec limites par chunk et contrôle des doublons."""
    validate_difficulty(difficulty)
    saved_questions = []

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Verrouille le chunk afin de limiter les dépassements concurrents.
            cursor.execute(
                """
                SELECT document_id, category_id, question_limit
                FROM document_chunks
                WHERE id = %s
                FOR UPDATE
                """,
                (chunk_id,),
            )

            chunk = cursor.fetchone()

            if chunk is None:
                raise ValueError(f"Chunk introuvable en base : {chunk_id}")

            document_id, category_id, configured_limit = chunk

            # Un QCM de banque doit toujours hériter d'une vraie catégorie.
            if category_id is None:
                raise ValueError(
                    f"Chunk {chunk_id} sans catégorie : "
                    "impossible de créer des QCM."
                )

            if configured_limit is None or configured_limit <= 0:
                configured_limit = TOTAL_QUESTION_LIMIT_PER_CHUNK

            total_limit = min(
                configured_limit,
                TOTAL_QUESTION_LIMIT_PER_CHUNK,
            )

            per_difficulty_limit = min(
                total_limit,
                QUESTION_LIMIT_PER_CHUNK,
            )

            for question in questions:
                if not is_valid_generated_question(question):
                    print("[BANK] Question rejetée : format invalide.")
                    continue

                normalized = normalize_question(question["question"])

                # Les doublons sont vérifiés à l'échelle du document,
                # pas seulement dans la catégorie courante.
                cursor.execute(
                    """
                    SELECT 1
                    FROM quiz_questions qq
                    JOIN document_chunks dc ON qq.chunk_id = dc.id
                    WHERE dc.document_id = %s
                      AND LOWER(
                          REGEXP_REPLACE(
                              TRIM(qq.question),
                              '[[:space:]]+',
                              ' ',
                              'g'
                          )
                      ) = %s
                    LIMIT 1
                    """,
                    (document_id, normalized),
                )

                if cursor.fetchone() is not None:
                    continue

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM quiz_questions
                    WHERE chunk_id = %s
                      AND difficulty = %s
                    """,
                    (chunk_id, difficulty),
                )
                difficulty_count = cursor.fetchone()[0]

                if difficulty_count >= per_difficulty_limit:
                    continue

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM quiz_questions
                    WHERE chunk_id = %s
                    """,
                    (chunk_id,),
                )
                total_count = cursor.fetchone()[0]

                if total_count >= total_limit:
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
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        chunk_id,
                        question["question"],
                        json.dumps(
                            question["options"],
                            ensure_ascii=False,
                        ),
                        str(question["correct_answer"]),
                        question["explanation"],
                        difficulty,
                    ),
                )

                question_id = cursor.fetchone()[0]

                # Le compteur est toujours recalculé depuis la table des questions.
                cursor.execute(
                    """
                    UPDATE document_chunks
                    SET question_count = (
                        SELECT COUNT(*)
                        FROM quiz_questions
                        WHERE chunk_id = %s
                    )
                    WHERE id = %s
                    """,
                    (chunk_id, chunk_id),
                )

                saved_questions.append({
                    "id": question_id,
                    "question": question["question"],
                    "options": question["options"],
                    "correct_answer": question["correct_answer"],
                    "explanation": question["explanation"],
                    "difficulty": difficulty,
                })

            conn.commit()

    return saved_questions


# ============================================================
# GÉNÉRATION D'UNE BANQUE
# ============================================================

def generate_questions_for_bank(
    document: str,
    difficulty: str,
    target_count: int,
    category_ids: Optional[list[int]] = None,
    progress_callback=None,
    continue_callback=None,
):
    validate_difficulty(difficulty)
    category_ids = validate_category_ids(category_ids)
    document_ids = get_documents_scope(document)
    category_sql, category_params = get_category_filter_sql(category_ids)

    # PostgreSQL reste la source de vérité au démarrage de chaque tâche.
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM quiz_questions qq
                JOIN document_chunks dc ON qq.chunk_id = dc.id
                WHERE dc.document_id = ANY(%s)
                  AND qq.difficulty = %s
                  AND dc.category_id IS NOT NULL
                  {category_sql}
                """,
                [
                    document_ids,
                    difficulty,
                    *category_params,
                ],
            )
            generated_count = cursor.fetchone()[0]

    target_count = min(
        max(0, target_count),
        TARGET_QUESTION_COUNT,
    )

    print(
        f"[BANK][{difficulty.upper()}] "
        f"{generated_count}/{target_count}"
    )

    if progress_callback is not None:
        progress_callback(generated_count, target_count)

    empty_passes = 0
    failed_chunks = set()

    while generated_count < target_count:
        chunks = get_available_chunks(
            document=document,
            difficulty=difficulty,
            category_ids=category_ids,
        )

        if not chunks:
            break

        generated_in_pass = False
        attempted_in_pass = 0

        for chunk in chunks:
            task_manager.wait_for_background_permission()

            if continue_callback is not None and not continue_callback():
                print(
                    f"[BANK][{difficulty.upper()}] "
                    "Document supprimé ; arrêt de la génération."
                )
                return generated_count

            if generated_count >= target_count:
                break

            chunk_id = chunk[0]
            chroma_id = chunk[1]
            chunk_category_id = chunk[2]
            difficulty_count = chunk[3]

            if chunk_id in failed_chunks:
                continue

            remaining_capacity = (
                QUESTION_LIMIT_PER_CHUNK - difficulty_count
            )

            if remaining_capacity <= 0:
                continue

            batch_size = min(
                BATCH_SIZE,
                remaining_capacity,
                target_count - generated_count,
            )

            attempted_in_pass += 1

            try:
                context = get_chunk_context(chroma_id)

                if chunk_category_id is None:
                    failed_chunks.add(chunk_id)
                    print(
                        f"[BANK][{difficulty.upper()}] "
                        f"Chunk {chunk_id} ignoré : aucune catégorie."
                    )
                    continue

                category = get_category_by_id(chunk_category_id)

                if not category:
                    failed_chunks.add(chunk_id)
                    print(
                        f"[BANK][{difficulty.upper()}] "
                        f"Chunk {chunk_id} ignoré : "
                        f"catégorie {chunk_category_id} introuvable."
                    )
                    continue

                # Exclut les questions de tout le document, toutes catégories confondues.
                excluded_questions = build_excluded_questions(
                    document=document,
                )

                task_manager.wait_for_background_permission()

                questions = generate_quiz_batch(
                    context=context,
                    difficulty=difficulty,
                    category_name=category["name"],
                    excluded_questions=excluded_questions,
                    batch_size=batch_size,
                )

                task_manager.wait_for_background_permission()

                if continue_callback is not None and not continue_callback():
                    print(
                        f"[BANK][{difficulty.upper()}] "
                        "Document supprimé après génération ; "
                        "questions non enregistrées."
                    )
                    return generated_count

                saved_questions = save_questions(
                    chunk_id=chunk_id,
                    questions=questions[:batch_size],
                    difficulty=difficulty,
                )

                if saved_questions:
                    # Recompte après insertion, sans supposer que toutes les
                    # questions proposées ont effectivement été enregistrées.
                    generated_count = count_questions(
                        difficulty=difficulty,
                        category_ids=category_ids,
                        document=document,
                    )

                    if progress_callback is not None:
                        progress_callback(generated_count, target_count)

                    generated_in_pass = True

                    print(
                        f"[BANK][{difficulty.upper()}] "
                        f"Catégorie={category['name']} "
                        f"Chunk={chunk_id} +{len(saved_questions)} "
                        f"→ {generated_count}/{target_count}"
                    )
                else:
                    failed_chunks.add(chunk_id)
                    print(
                        f"[BANK][{difficulty.upper()}] "
                        f"Chunk {chunk_id} ignoré : aucune question sauvegardée "
                        "(doublons ou limite atteinte)."
                    )

            except Exception as error:
                failed_chunks.add(chunk_id)
                print(
                    f"[BANK][{difficulty.upper()}] "
                    f"Chunk {chunk_id} ignoré : {error}"
                )
                continue

        if generated_in_pass:
            empty_passes = 0
        else:
            empty_passes += 1

            print(
                f"[BANK][{difficulty.upper()}] "
                f"Aucune progression ({empty_passes}/{MAX_EMPTY_PASSES})."
            )

            remaining_chunks = [
                chunk
                for chunk in chunks
                if chunk[0] not in failed_chunks
            ]

            if not remaining_chunks:
                print(
                    f"[BANK][{difficulty.upper()}] "
                    "Arrêt : aucun chunk encore exploitable."
                )
                break

            if empty_passes >= MAX_EMPTY_PASSES:
                break

            if attempted_in_pass == 0:
                break

    print(
        f"[BANK][{difficulty.upper()}] "
        f"Fin de génération : {generated_count}/{target_count}."
    )

    return generated_count


# ============================================================
# QUESTIONS DÉJÀ VUES PAR UN UTILISATEUR
# ============================================================

def get_user_seen_question_ids(
    user_id: int,
    difficulty: str,
    category_ids: Optional[list[int]] = None,
):
    validate_difficulty(difficulty)
    category_ids = validate_category_ids(category_ids)
    category_sql, category_params = get_category_filter_sql(category_ids)

    query = f"""
        SELECT DISTINCT qaq.question_id
        FROM quiz_attempt_questions qaq
        JOIN quiz_results qr ON qaq.quiz_result_id = qr.id
        JOIN quiz_questions qq ON qaq.question_id = qq.id
        JOIN document_chunks dc ON qq.chunk_id = dc.id
        WHERE qr.user_id = %s
          AND qq.difficulty = %s
          {category_sql}
    """

    params = [
        user_id,
        difficulty,
        *category_params,
    ]

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return {
                row[0]
                for row in cursor.fetchall()
            }


# ============================================================
# RÉCUPÉRATION ALÉATOIRE DE QUESTIONS
# ============================================================

def get_random_questions(
    difficulty: str,
    question_count: int,
    user_id: int,
    category_ids: Optional[list[int]] = None,
):
    validate_difficulty(difficulty)
    category_ids = validate_category_ids(category_ids)

    seen_question_ids = get_user_seen_question_ids(
        user_id=user_id,
        difficulty=difficulty,
        category_ids=category_ids,
    )

    category_sql, category_params = get_category_filter_sql(category_ids)

    query = f"""
        SELECT
            qq.id,
            qq.question,
            qq.options,
            qq.difficulty
        FROM quiz_questions qq
        JOIN document_chunks dc ON qq.chunk_id = dc.id
        WHERE qq.difficulty = %s
          {category_sql}
    """

    params = [
        difficulty,
        *category_params,
    ]

    if seen_question_ids:
        query += " AND NOT (qq.id = ANY(%s))"
        params.append(list(seen_question_ids))

    query += """
        ORDER BY RANDOM()
        LIMIT %s
    """
    params.append(question_count)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    questions = []

    for row in rows:
        options = row[2]

        if isinstance(options, str):
            options = json.loads(options)

        questions.append({
            "id": row[0],
            "question": row[1],
            "options": options,
            "difficulty": row[3],
        })

    return questions


# ============================================================
# VÉRIFICATION D'UNE RÉPONSE
# ============================================================

def check_quiz_answer(
    question_id: int,
    answer: int,
):
    if (
        not isinstance(answer, int)
        or isinstance(answer, bool)
        or answer not in {0, 1, 2, 3}
    ):
        raise ValueError(
            "La réponse doit être un entier compris entre 0 et 3."
        )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT correct_answer, explanation
                FROM quiz_questions
                WHERE id = %s
                """,
                (question_id,),
            )
            result = cursor.fetchone()

    if result is None:
        raise ValueError("Question introuvable.")

    correct_answer = int(result[0])

    return {
        "is_correct": answer == correct_answer,
        "correct_answer": correct_answer,
        "explanation": result[1],
    }


# ============================================================
# ÉTAT D'UNE BANQUE
# ============================================================

def ensure_bank(
    difficulty: str,
    category_ids: Optional[list[int]] = None,
):
    validate_difficulty(difficulty)
    category_ids = validate_category_ids(category_ids)

    current_count = count_questions(
        difficulty=difficulty,
        category_ids=category_ids,
    )

    capacity = get_max_capacity(
        difficulty=difficulty,
        category_ids=category_ids,
    )

    target = min(TARGET_QUESTION_COUNT, capacity)

    return {
        "current": current_count,
        "target": target,
        "capacity": capacity,
        "complete": current_count >= target,
        "remaining": max(0, target - current_count),
    }


# ============================================================
# QUIZ UTILISATEUR
# ============================================================

def generate_quiz(
    question_count: int,
    difficulty: str,
    user_id: int,
    category_ids: Optional[list[int]] = None,
):
    validate_question_count(question_count)
    validate_difficulty(difficulty)
    category_ids = validate_category_ids(category_ids)

    if not category_ids:
        raise ValueError(
            "Au moins une catégorie doit être sélectionnée."
        )

    available_count = count_questions(
        difficulty=difficulty,
        category_ids=category_ids,
    )

    if available_count < question_count:
        status = get_bank_status(category_ids=category_ids)
        difficulty_status = status[difficulty]

        return {
            "status": "insufficient_questions",
            "category_ids": category_ids,
            "difficulty": difficulty,
            "requested_count": question_count,
            "available_count": available_count,
            "missing_count": max(0, question_count - available_count),
            "target_count": difficulty_status["target"],
            "capacity": difficulty_status["capacity"],
            "generation_active": difficulty_status["needs_generation"],
            "options": {
                "available": {
                    "enabled": available_count > 0,
                    "question_count": min(
                        available_count,
                        question_count,
                    ),
                },
                "mixed": {
                    "enabled": False,
                    "difficulties": [],
                },
                "wait": {
                    "enabled": True,
                    "missing_count": max(
                        0,
                        question_count - available_count,
                    ),
                    "generation_active": difficulty_status["needs_generation"],
                },
            },
        }

    questions = get_random_questions(
        difficulty=difficulty,
        question_count=question_count,
        user_id=user_id,
        category_ids=category_ids,
    )

    if len(questions) < question_count:
        raise ValueError(
            "Pas assez de questions non vues disponibles pour cet utilisateur."
        )

    return {
        "status": "ready",
        "category_ids": category_ids,
        "difficulty": difficulty,
        "questions": questions,
    }


# ============================================================
# QUIZ MIXTE
# ============================================================

def generate_mixed_quiz(
    question_count: int,
    primary_difficulty: str,
    secondary_difficulty: str,
    user_id: int,
    category_ids: Optional[list[int]] = None,
):
    validate_question_count(question_count)
    validate_difficulty(primary_difficulty)
    validate_difficulty(secondary_difficulty)
    category_ids = validate_category_ids(category_ids)

    if not category_ids:
        raise ValueError(
            "Au moins une catégorie doit être sélectionnée."
        )

    if primary_difficulty == secondary_difficulty:
        raise ValueError(
            "Les deux difficultés doivent être différentes."
        )

    primary_count = (question_count + 1) // 2
    secondary_count = question_count - primary_count

    primary_available = count_questions(
        difficulty=primary_difficulty,
        category_ids=category_ids,
    )

    if primary_available < primary_count:
        raise ValueError(
            "Pas assez de questions disponibles pour la difficulté "
            f"{primary_difficulty}. Disponibles : {primary_available}. "
            f"Demandées : {primary_count}."
        )

    secondary_available = count_questions(
        difficulty=secondary_difficulty,
        category_ids=category_ids,
    )

    if secondary_available < secondary_count:
        raise ValueError(
            "Pas assez de questions disponibles pour la difficulté "
            f"{secondary_difficulty}. Disponibles : {secondary_available}. "
            f"Demandées : {secondary_count}."
        )

    primary_questions = get_random_questions(
        difficulty=primary_difficulty,
        question_count=primary_count,
        user_id=user_id,
        category_ids=category_ids,
    )

    secondary_questions = get_random_questions(
        difficulty=secondary_difficulty,
        question_count=secondary_count,
        user_id=user_id,
        category_ids=category_ids,
    )

    questions = primary_questions + secondary_questions

    if len(questions) < question_count:
        raise ValueError(
            "Pas assez de questions non vues disponibles pour générer ce quiz."
        )

    return {
        "status": "ready",
        "category_ids": category_ids,
        "questions": questions,
    }


# ============================================================
# STATUT DE GÉNÉRATION POUR L'API
# ============================================================

def get_quiz_generation_status(
    category_ids: Optional[list[int]] = None,
):
    category_ids = validate_category_ids(category_ids)

    if not category_ids:
        raise ValueError(
            "Au moins une catégorie doit être sélectionnée."
        )

    status = get_bank_status(category_ids=category_ids)

    return {
        "category_ids": category_ids,
        "target_per_category_difficulty": TARGET_QUESTION_COUNT,
        "status": status,
        "categories": get_category_bank_status(
            category_ids=category_ids,
        ),
    }