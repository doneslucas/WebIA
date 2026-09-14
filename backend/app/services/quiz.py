import json
import re
import time

from langchain_ollama import OllamaEmbeddings, OllamaLLM

from app.services.chroma import search_chunks


embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)


BATCH_SIZE = 5
MAX_ATTEMPTS = 3
QUIZ_NUM_PREDICT = 1000


llm = OllamaLLM(
    model="llama3.2:latest",
    num_predict=QUIZ_NUM_PREDICT,
    format="json",
    temperature=0.2
)


def clean_json_response(response: str) -> str:
    response = response.strip()

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

    response = response.strip()

    first_brace = response.find("{")
    last_brace = response.rfind("}")

    if first_brace != -1 and last_brace != -1:
        response = response[
            first_brace:last_brace + 1
        ]

    return response.strip()


def validate_quiz(
    quiz: dict,
    question_count: int
):
    if not isinstance(quiz, dict):
        raise ValueError(
            "La réponse JSON doit être un objet."
        )

    if "questions" not in quiz:
        raise ValueError(
            "Le JSON ne contient pas le champ 'questions'."
        )

    questions = quiz["questions"]

    if not isinstance(questions, list):
        raise ValueError(
            "Le champ 'questions' doit être une liste."
        )

    if len(questions) != question_count:
        raise ValueError(
            f"Qwen a généré {len(questions)} questions "
            f"au lieu de {question_count}."
        )

    for index, question in enumerate(questions):

        question_number = index + 1

        if not isinstance(question, dict):
            raise ValueError(
                f"La question {question_number} "
                "n'est pas un objet JSON."
            )

        if "question" not in question:
            raise ValueError(
                f"La question {question_number} "
                "ne contient pas le champ 'question'."
            )

        if not isinstance(question["question"], str):
            raise ValueError(
                f"Le texte de la question {question_number} "
                "doit être une chaîne de caractères."
            )

        if not question["question"].strip():
            raise ValueError(
                f"La question {question_number} "
                "est vide."
            )

        if "options" not in question:
            raise ValueError(
                f"La question {question_number} "
                "ne contient pas le champ 'options'."
            )

        options = question["options"]

        if not isinstance(options, list):
            raise ValueError(
                f"Les réponses de la question {question_number} "
                "doivent être une liste."
            )

        if len(options) != 4:
            raise ValueError(
                f"La question {question_number} contient "
                f"{len(options)} réponses au lieu de 4."
            )

        for option_index, option in enumerate(options):

            if not isinstance(option, str):
                raise ValueError(
                    f"La réponse {option_index + 1} de la "
                    f"question {question_number} doit être "
                    "une chaîne."
                )

            if not option.strip():
                raise ValueError(
                    f"La réponse {option_index + 1} de la "
                    f"question {question_number} est vide."
                )

        normalized_options = [
            option.strip().lower()
            for option in options
        ]

        if len(set(normalized_options)) != 4:
            raise ValueError(
                f"La question {question_number} contient "
                "des réponses dupliquées."
            )

        if "correct_answer" not in question:
            raise ValueError(
                f"La question {question_number} ne contient "
                "pas le champ 'correct_answer'."
            )

        correct_answer = question["correct_answer"]

        if isinstance(correct_answer, bool):
            raise ValueError(
                f"La réponse correcte de la question "
                f"{question_number} doit être un entier."
            )

        if not isinstance(correct_answer, int):
            raise ValueError(
                f"La réponse correcte de la question "
                f"{question_number} doit être un entier."
            )

        if correct_answer not in range(4):
            raise ValueError(
                f"La réponse correcte de la question "
                f"{question_number} doit être comprise "
                "entre 0 et 3."
            )

        if "explanation" not in question:
            raise ValueError(
                f"La question {question_number} ne contient "
                "pas le champ 'explanation'."
            )

        explanation = question["explanation"]

        if not isinstance(explanation, str):
            raise ValueError(
                f"L'explication de la question "
                f"{question_number} doit être une chaîne."
            )

        if not explanation.strip():
            raise ValueError(
                f"L'explication de la question "
                f"{question_number} est vide."
            )

    return True


def parse_quiz_response(
    response: str,
    question_count: int
):
    cleaned_response = clean_json_response(
        response
    )

    if not cleaned_response:
        raise ValueError(
            "Qwen a retourné une réponse vide."
        )

    try:
        quiz = json.loads(
            cleaned_response
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            "Qwen n'a pas retourné un JSON valide : "
            f"{error}"
        )

    validate_quiz(
        quiz,
        question_count
    )

    return quiz


def build_excluded_questions(
    questions: list
) -> str:

    if not questions:
        return ""

    previous_questions = []

    for index, question in enumerate(questions):
        previous_questions.append(
            f"{index + 1}. {question['question']}"
        )

    return f"""
QUESTIONS DÉJÀ GÉNÉRÉES :

Les questions suivantes ont déjà été générées
pour ce quiz.

Tu dois créer des questions différentes.

{chr(10).join(previous_questions)}

Ne répète aucune de ces questions.
Ne reformule pas simplement une question existante.
"""


def generate_quiz_batch(
    context: str,
    question_count: int,
    difficulty_label: str,
    previous_questions: list
):

    excluded_questions = build_excluded_questions(
        previous_questions
    )

    base_prompt = f"""
Tu es un générateur de quiz spécialisé
en cybersécurité.

Tu dois créer exactement {question_count} questions
à choix multiple à partir UNIQUEMENT du contexte fourni.

Niveau de difficulté : {difficulty_label}.

{excluded_questions}

FORMAT DE SORTIE OBLIGATOIRE :

Tu dois répondre avec UN SEUL objet JSON valide.

Le JSON doit avoir exactement cette structure :

{{
  "questions": [
    {{
      "question": "Texte de la question",
      "options": [
        "Réponse A",
        "Réponse B",
        "Réponse C",
        "Réponse D"
      ],
      "correct_answer": 0,
      "explanation": "Courte explication pédagogique."
    }}
  ]
}}

RÈGLES :

- Il doit y avoir exactement {question_count} questions.
- Chaque question doit avoir exactement 4 réponses.
- Une seule réponse doit être correcte.
- "correct_answer" doit être un entier entre 0 et 3.
- 0 correspond à la première réponse.
- 1 correspond à la deuxième réponse.
- 2 correspond à la troisième réponse.
- 3 correspond à la quatrième réponse.
- Toutes les réponses doivent être des chaînes de caractères.
- Les quatre réponses doivent être différentes.
- Toutes les questions doivent être basées uniquement sur le contexte.
- N'invente aucune information.
- Réponds en français.
- Les questions doivent correspondre au niveau de difficulté demandé.
- Ne répète aucune question déjà générée.
- Ne reformule pas une question déjà générée.

POUR CHAQUE QUESTION :

- "explanation" doit expliquer brièvement pourquoi
  la réponse correcte est correcte.
- L'explication doit être compréhensible par un étudiant.
- L'explication doit rester courte.
- L'explication doit uniquement utiliser les informations
  présentes dans le contexte.
- Ne donne aucune information absente du contexte.
- Ne fais pas référence aux lettres A, B, C ou D.
- Ne commence pas l'explication par "Correct" ou "Incorrect".
- Ne mets aucun champ supplémentaire.

IMPORTANT :

Réponds uniquement avec le JSON.

Aucun texte avant le JSON.

Aucun texte après le JSON.

Aucun Markdown.

Aucun bloc ```json.

Aucun commentaire.

Respecte strictement la syntaxe JSON.

Contexte :
{context}

Génère maintenant les {question_count} questions.
"""

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):

        print(
            f"\n→ Génération du lot "
            f"({question_count} questions) "
            f"(tentative {attempt}/{MAX_ATTEMPTS})"
        )

        prompt = base_prompt

        if last_error is not None:

            prompt = f"""
La génération précédente était invalide.

Erreur détectée :
{last_error}

Tu dois recommencer entièrement ce lot.

IMPORTANT :

- Génère un nouvel objet JSON complet.
- Génère exactement {question_count} questions.
- Chaque question doit contenir une explication.
- Respecte exactement le format demandé.
- Ne génère aucune question déjà présente.
- Réponds uniquement avec le JSON.
- Aucun texte avant.
- Aucun texte après.
- Aucun Markdown.

{base_prompt}
"""

        try:

            start_time = time.perf_counter()

            response = llm.invoke(
                prompt
            )

            elapsed_time = time.perf_counter() - start_time

            print(
                f"→ Réponse reçue de Qwen "
                f"en {elapsed_time:.2f} secondes."
            )

            parse_start = time.perf_counter()

            quiz = parse_quiz_response(
                response,
                question_count
            )

            parse_elapsed = (
                time.perf_counter() - parse_start
            )

            print(
                f"→ Parsing + validation : "
                f"{parse_elapsed:.4f} secondes."
            )

            print(
                "→ Lot JSON valide."
            )

            print(
                f"→ Lot validé : "
                f"{len(quiz['questions'])} questions."
            )

            return quiz["questions"]

        except ValueError as error:

            last_error = str(error)

            print(
                f"→ Lot invalide : {last_error}"
            )

            if attempt < MAX_ATTEMPTS:

                print(
                    "→ Nouvelle tentative du lot..."
                )

    raise ValueError(
        "Impossible de générer un lot valide "
        f"après {MAX_ATTEMPTS} tentatives. "
        f"Dernière erreur : {last_error}"
    )


def generate_quiz(
    document: str,
    question_count: int,
    difficulty: str
):

    total_start_time = time.perf_counter()

    if question_count <= 0:
        raise ValueError(
            "Le nombre de questions doit être supérieur à 0."
        )

    if difficulty not in {
        "easy",
        "medium",
        "hard"
    }:
        raise ValueError(
            "Niveau de difficulté invalide."
        )

    difficulty_labels = {
        "easy": "facile",
        "medium": "intermédiaire",
        "hard": "difficile"
    }

    difficulty_label = difficulty_labels[
        difficulty
    ]

    if document == "all":

        search_question = (
            "cybersécurité menaces phishing sécurité "
            "informatique attaques protection"
        )

    else:

        search_question = (
            f"cybersécurité contenu du document {document}"
        )

    print(
        "\n→ Recherche du contexte dans ChromaDB..."
    )

    embedding_start = time.perf_counter()

    query_vector = embeddings.embed_query(
        search_question
    )

    embedding_elapsed = (
        time.perf_counter() - embedding_start
    )

    print(
        f"→ Embedding de la requête : "
        f"{embedding_elapsed:.4f} secondes."
    )

    chroma_start = time.perf_counter()

    results = search_chunks(
        query_vector,
        n_results=10
    )

    chroma_elapsed = (
        time.perf_counter() - chroma_start
    )

    print(
        f"→ Recherche ChromaDB : "
        f"{chroma_elapsed:.4f} secondes."
    )

    documents = results.get(
        "documents",
        [[]]
    )

    if not documents or not documents[0]:
        raise ValueError(
            "Aucun contenu disponible dans ChromaDB."
        )

    chunks = documents[0]

    context = "\n\n".join(
        chunks
    )

    print(
        f"→ {len(chunks)} chunks récupérés."
    )

    all_questions = []

    remaining_questions = question_count

    batch_number = 1

    total_llm_time = 0.0

    quiz_generation_start = time.perf_counter()

    while remaining_questions > 0:

        current_batch_size = min(
            BATCH_SIZE,
            remaining_questions
        )

        print(
            "\n=================================================="
        )

        print(
            f"→ LOT {batch_number}"
        )

        print(
            f"→ Questions à générer : "
            f"{current_batch_size}"
        )

        print(
            f"→ Progression : "
            f"{len(all_questions)}/{question_count}"
        )

        print(
            "=================================================="
        )

        batch_start_time = time.perf_counter()

        batch_questions = generate_quiz_batch(
            context=context,
            question_count=current_batch_size,
            difficulty_label=difficulty_label,
            previous_questions=all_questions
        )

        batch_elapsed = (
            time.perf_counter() - batch_start_time
        )

        total_llm_time += batch_elapsed

        print(
            f"→ Temps total du lot {batch_number} : "
            f"{batch_elapsed:.2f} secondes."
        )

        all_questions.extend(
            batch_questions
        )

        remaining_questions = (
            question_count - len(all_questions)
        )

        batch_number += 1

        print(
            f"→ Progression : "
            f"{len(all_questions)}/{question_count}"
        )

    quiz_generation_elapsed = (
        time.perf_counter() - quiz_generation_start
    )

    final_quiz = {
        "questions": all_questions
    }

    validate_quiz(
        final_quiz,
        question_count
    )

    total_elapsed = (
        time.perf_counter() - total_start_time
    )

    print(
        "\n=================================================="
    )

    print(
        f"→ QUIZ FINAL VALIDÉ : "
        f"{len(all_questions)} questions."
    )

    print(
        f"→ Temps génération quiz : "
        f"{quiz_generation_elapsed:.2f} secondes."
    )

    print(
        f"→ Temps total consacré aux lots : "
        f"{total_llm_time:.2f} secondes."
    )

    print(
        f"→ Temps hors génération des lots : "
        f"{quiz_generation_elapsed - total_llm_time:.2f} secondes."
    )

    print(
        f"→ Temps TOTAL : "
        f"{total_elapsed:.2f} secondes."
    )

    print(
        "=================================================="
    )

    return final_quiz