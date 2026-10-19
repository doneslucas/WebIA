
"""Classification contrôlée des chunks WebIA dans la liste fixe de catégories."""

import json
import os
import re
import time
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_ollama import OllamaLLM

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
CATEGORY_MODEL = os.getenv("CATEGORY_MODEL", "qwen2.5:7b")

try:
    OLLAMA_TIMEOUT_SECONDS = max(
        1,
        int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")),
    )
except (TypeError, ValueError):
    OLLAMA_TIMEOUT_SECONDS = 120

DEFAULT_BATCH_SIZE = 5


# ============================================================
# MODÈLE OLLAMA
# ============================================================

llm = OllamaLLM(
    model=CATEGORY_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.1,
    format="json",
    client_kwargs={
        "timeout": OLLAMA_TIMEOUT_SECONDS,
    },
)


def _invoke_classifier(prompt: str, context: str) -> Any:
    """Appelle Ollama avec mesure du temps et journalisation."""
    started_at = time.monotonic()

    print(
        f"[Classifier] Début : {context} | "
        f"modèle={CATEGORY_MODEL} | "
        f"délai maximal={OLLAMA_TIMEOUT_SECONDS}s",
        flush=True,
    )

    try:
        response = llm.invoke(prompt)

        elapsed = time.monotonic() - started_at

        print(
            f"[Classifier] Réponse reçue : {context} | "
            f"durée={elapsed:.1f}s",
            flush=True,
        )

        return response

    except Exception as error:
        elapsed = time.monotonic() - started_at

        print(
            f"[Classifier] Échec : {context} | "
            f"durée={elapsed:.1f}s | "
            f"type={type(error).__name__} | "
            f"erreur={error}",
            flush=True,
        )

        raise


# ============================================================
# LECTURE DE LA RÉPONSE JSON
# ============================================================

def _extract_json(response: Any) -> dict:
    """Parse la réponse JSON d'Ollama, même si elle contient des fences."""
    if hasattr(response, "content"):
        response = response.content

    if isinstance(response, dict):
        return response

    if not isinstance(response, str):
        raise ValueError("Réponse du modèle non textuelle.")

    raw = response.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")

        if start < 0 or end <= start:
            raise ValueError(
                "La réponse du modèle ne contient pas de JSON valide."
            )

        parsed = json.loads(raw[start:end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Le JSON de classification doit être un objet.")

    return parsed


# ============================================================
# CATÉGORIES AUTORISÉES
# ============================================================

def _allowed_category_map(
    allowed_categories: list[dict],
) -> tuple[dict[int, dict], dict[str, dict]]:
    by_id: dict[int, dict] = {}
    by_name: dict[str, dict] = {}

    for category in allowed_categories:
        if not isinstance(category, dict):
            continue

        category_id = category.get("id")
        name = category.get("name")

        if (
            category_id is None
            or not isinstance(name, str)
            or not name.strip()
        ):
            continue

        try:
            numeric_id = int(category_id)
        except (TypeError, ValueError):
            continue

        by_id[numeric_id] = category
        by_name[name.strip().casefold()] = category

    if not by_id:
        raise ValueError(
            "La liste des catégories autorisées est vide ou invalide."
        )

    return by_id, by_name


def _resolve_category(
    value: Any,
    by_id: dict[int, dict],
    by_name: dict[str, dict],
) -> Optional[dict]:
    if value is None or value == "null":
        return None

    if isinstance(value, dict):
        value = value.get(
            "category_id",
            value.get("id", value.get("category")),
        )

    try:
        candidate_id = int(value)

        if candidate_id in by_id:
            return by_id[candidate_id]

    except (TypeError, ValueError):
        pass

    if isinstance(value, str):
        return by_name.get(value.strip().casefold())

    return None


def _build_category_lines(
    by_id: dict[int, dict],
) -> list[str]:
    return [
        (
            f'{category_id}: {category.get("name", "")} '
            f'(famille: {category.get("family", "")})'
        )
        for category_id, category in sorted(by_id.items())
    ]


# ============================================================
# CLASSIFICATION D'UN CHUNK
# ============================================================

def classify_chunk(
    chunk_text: str,
    allowed_categories: list[dict],
    require_category: bool = False,
) -> Optional[dict]:
    """Attribue une catégorie existante à un chunk.

    require_category=True est réservé à la réparation de chunks provenant
    de documents déjà reconnus comme documents de cybersécurité.
    """
    if not isinstance(chunk_text, str) or not chunk_text.strip():
        return None

    by_id, by_name = _allowed_category_map(allowed_categories)
    category_lines = _build_category_lines(by_id)

    if require_category:
        null_rule = (
            "Pour un texte non vide contenant une information exploitable, "
            "choisis obligatoirement la catégorie autorisée la plus proche. "
            "N'utilise null que si le texte est vide, illisible "
            "ou sans information exploitable."
        )
    else:
        null_rule = (
            "Utilise null uniquement si le chunk est vide, illisible, "
            "trop court pour être interprété ou sans lien utile "
            "avec la cybersécurité."
        )

    prompt = f"""Tu classes un extrait documentaire pour une application
de formation en cybersécurité.

Tu dois utiliser exclusivement cette liste fermée de catégories :
{chr(10).join(category_lines)}

Règles :
- Ne crée, ne renomme et ne modifie aucune catégorie.
- Choisis une seule catégorie dont le sujet correspond le mieux au texte.
- {null_rule}
- Retourne uniquement un objet JSON sous la forme
  {{"category_id": 12}} ou {{"category_id": null}}.

Texte du chunk :
<chunk>
{chunk_text[:9000]}
</chunk>
"""

    response = _invoke_classifier(
        prompt,
        context="classification individuelle",
    )

    parsed = _extract_json(response)
    value = parsed.get(
        "category_id",
        parsed.get("category", parsed.get("id")),
    )

    category = _resolve_category(value, by_id, by_name)

    if category is None and require_category:
        raise ValueError(
            "Le modèle n'a pas retourné d'identifiant de catégorie autorisé."
        )

    return category


# ============================================================
# CLASSIFICATION PAR LOTS
# ============================================================

def classify_chunks_batch(
    chunk_texts: list[str],
    allowed_categories: list[dict],
    batch_size: int = DEFAULT_BATCH_SIZE,
    require_category: bool = False,
) -> list[Optional[dict]]:
    """Classe des chunks par petits lots, en conservant leur ordre d'entrée.

    Si un lot est invalide, la fonction réessaie les chunks individuellement.
    Une erreur concernant un chunk n'arrête pas les autres.
    """
    if batch_size < 1 or batch_size > 10:
        raise ValueError("batch_size doit être compris entre 1 et 10.")

    by_id, by_name = _allowed_category_map(allowed_categories)
    category_lines = _build_category_lines(by_id)
    output: list[Optional[dict]] = [None] * len(chunk_texts)

    for offset in range(0, len(chunk_texts), batch_size):
        batch = chunk_texts[offset:offset + batch_size]

        usable_indices = [
            index
            for index, chunk in enumerate(batch)
            if isinstance(chunk, str) and chunk.strip()
        ]

        if not usable_indices:
            continue

        chunk_sections = []

        for index in usable_indices:
            safe_text = batch[index][:7000]
            chunk_sections.append(
                f"CHUNK_INDEX={index}\n"
                f"<chunk>\n{safe_text}\n</chunk>"
            )

        if require_category:
            null_rule = (
                "Pour tout texte non vide exploitable, sélectionne "
                "obligatoirement la catégorie autorisée la plus proche. "
                "Utilise null uniquement si le texte est inutilisable."
            )
        else:
            null_rule = (
                "Retourne null seulement si le texte est vide, illisible "
                "ou sans information exploitable liée à la cybersécurité."
            )

        prompt = f"""Tu classes plusieurs extraits de documents dans une
liste fermée de catégories de cybersécurité.

Catégories autorisées :
{chr(10).join(category_lines)}

Consignes :
- Aucun nouvel identifiant ni aucune catégorie inventée.
- Chaque chunk reçoit une seule catégorie existante ou null.
- {null_rule}
- Chaque index du lot doit apparaître exactement une fois.
- Réponds uniquement en JSON sous la forme :
  {{"classifications":[{{"index":0,"category_id":12}},
                       {{"index":1,"category_id":null}}]}}.

Extraits :
{chr(10).join(chunk_sections)}
"""

        try:
            response = _invoke_classifier(
                prompt,
                context=(
                    f"lot {offset + 1}-"
                    f"{offset + len(batch)}"
                ),
            )

            parsed = _extract_json(response)
            entries = parsed.get("classifications")

            if not isinstance(entries, list):
                raise ValueError(
                    "Le tableau 'classifications' est absent."
                )

            mapped: dict[int, Any] = {}

            for entry in entries:
                if not isinstance(entry, dict):
                    continue

                try:
                    index = int(entry.get("index"))
                except (TypeError, ValueError):
                    continue

                if index in usable_indices:
                    mapped[index] = entry.get(
                        "category_id",
                        entry.get("category", entry.get("id")),
                    )

            for local_index in usable_indices:
                global_index = offset + local_index

                if local_index not in mapped:
                    output[global_index] = classify_chunk(
                        batch[local_index],
                        allowed_categories,
                        require_category=require_category,
                    )
                    continue

                category = _resolve_category(
                    mapped[local_index],
                    by_id,
                    by_name,
                )

                if category is None and require_category:
                    output[global_index] = classify_chunk(
                        batch[local_index],
                        allowed_categories,
                        require_category=True,
                    )
                else:
                    output[global_index] = category

        except Exception as batch_error:
            print(
                f"[Classifier] Lot {offset + 1}-"
                f"{offset + len(batch)} invalide "
                f"({batch_error}); reprise chunk par chunk.",
                flush=True,
            )

            for local_index in usable_indices:
                global_index = offset + local_index

                try:
                    output[global_index] = classify_chunk(
                        batch[local_index],
                        allowed_categories,
                        require_category=require_category,
                    )
                except Exception as error:
                    print(
                        f"[Classifier] Chunk {global_index + 1} "
                        f"non classé : {error}",
                        flush=True,
                    )
                    output[global_index] = None

    return output


# ============================================================
# CATÉGORIES DISTINCTES D'UN DOCUMENT
# ============================================================

def detect_document_categories(
    chunks: list[str],
    allowed_categories: list[dict],
) -> list[dict]:
    """Compatibilité : renvoie les catégories distinctes d'un document."""
    classified = classify_chunks_batch(
        chunks,
        allowed_categories,
        batch_size=DEFAULT_BATCH_SIZE,
    )

    ids = {
        category["id"]
        for category in classified
        if category is not None
    }

    return [
        category
        for category in allowed_categories
        if category.get("id") in ids
    ]
