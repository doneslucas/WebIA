import json
import os
from typing import Callable, Dict, List, Optional

from dotenv import load_dotenv
from langchain_ollama import OllamaLLM

from app.services.categories import (
    get_category_by_name,
    get_category_names,
)

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

CATEGORY_MODEL = "qwen2.5:7b"

llm = OllamaLLM(
    model=CATEGORY_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0.1,
    format="json",
)


def _clean_json_response(response: str) -> Dict:
    response = response.strip()

    if response.startswith("```"):
        lines = response.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        response = "\n".join(lines).strip()

    try:
        return json.loads(response)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Réponse JSON invalide du modèle : {response}"
        ) from exc


def _classify_chunk_group(
    chunks: List[str],
    category_names: List[str],
) -> List[Dict[str, str]]:

    if not chunks:
        return []

    group_text = "\n\n".join(chunks)

    prompt = f"""
Tu es un expert en cybersécurité chargé de classifier du contenu.

Tu dois identifier les catégories de cybersécurité réellement représentées
dans le texte fourni.

IMPORTANT :
- Tu dois UNIQUEMENT choisir parmi les catégories présentes dans la liste.
- Tu ne dois JAMAIS créer de nouvelle catégorie.
- Tu ne dois JAMAIS reformuler une catégorie.
- Tu dois recopier exactement le nom des catégories.
- Tu peux sélectionner plusieurs catégories.
- Ne sélectionne une catégorie que si elle est réellement représentée
  dans le texte.
- Si plusieurs sujets sont présents, sélectionne toutes les catégories
  pertinentes.
- Si une catégorie générale et une catégorie plus précise existent,
  privilégie la catégorie la plus précise.

CATÉGORIES AUTORISÉES :

{json.dumps(category_names, ensure_ascii=False, indent=2)}

TEXTE À CLASSIFIER :

{group_text}

Réponds UNIQUEMENT avec ce JSON :

{{
    "categories": [
        "Nom exact de la catégorie"
    ]
}}
"""

    response = llm.invoke(prompt)

    print(
        "[CategoryClassifier] "
        "Réponse brute du groupe :"
    )

    print(response)

    data = _clean_json_response(response)

    selected_categories = data.get(
        "categories",
        []
    )

    if not isinstance(
        selected_categories,
        list
    ):
        print(
            "[CategoryClassifier] "
            "Réponse invalide : "
            "la propriété 'categories' "
            "n'est pas une liste."
        )

        return []

    validated_categories = []

    for category_name in selected_categories:

        if not isinstance(
            category_name,
            str
        ):
            continue

        category = get_category_by_name(
            category_name
        )

        if category is None:

            print(
                "[CategoryClassifier] "
                "Catégorie ignorée car inconnue : "
                f"{category_name}"
            )

            continue

        validated_categories.append(
            category
        )

    return validated_categories


def detect_document_categories(
    chunks: List[str],
    progress_callback: Optional[
        Callable[[int, int], None]
    ] = None,
) -> List[Dict[str, str]]:

    if not chunks:
        return []

    category_names = get_category_names()

    GROUP_SIZE = 10

    print(
        f"[CategoryClassifier] "
        f"Nombre total de chunks : {len(chunks)}"
    )

    print(
        f"[CategoryClassifier] "
        f"Taille moyenne approximative des chunks : "
        f"{sum(len(chunk) for chunk in chunks) // len(chunks)} "
        f"caractères"
    )

    all_categories = {}

    total_groups = (
        len(chunks) + GROUP_SIZE - 1
    ) // GROUP_SIZE

    for group_index in range(
        total_groups
    ):

        start = (
            group_index * GROUP_SIZE
        )

        end = min(
            start + GROUP_SIZE,
            len(chunks)
        )

        group_chunks = chunks[
            start:end
        ]

        print(
            f"[CategoryClassifier] "
            f"Analyse du groupe "
            f"{group_index + 1}/{total_groups} "
            f"({len(group_chunks)} chunks)..."
        )

        try:

            group_categories = (
                _classify_chunk_group(
                    group_chunks,
                    category_names
                )
            )

        except Exception as exc:

            print(
                f"[CategoryClassifier] "
                f"Erreur lors de l'analyse du groupe "
                f"{group_index + 1} : {exc}"
            )

            continue

        for category in group_categories:

            all_categories[
                category["id"]
            ] = category

        print(
            f"[CategoryClassifier] "
            f"Groupe {group_index + 1} : "
            f"{len(group_categories)} "
            f"catégorie(s) valide(s)"
        )

        # ----------------------------------------------------
        # PROGRESSION DE LA DÉTECTION DES CATÉGORIES
        #
        # Cette étape occupe la plage 22 -> 24 %.
        # ----------------------------------------------------

        if progress_callback is not None:

            progress_callback(
                group_index + 1,
                total_groups
            )

    detected_categories = list(
        all_categories.values()
    )

    print(
        f"[CategoryClassifier] "
        f"Nombre total de catégories détectées : "
        f"{len(detected_categories)}"
    )

    for category in detected_categories:

        print(
            f"  - {category['id']} : "
            f"{category['name']} "
            f"({category['family']})"
        )

    return detected_categories


def classify_chunk(
    chunk_text: str,
    allowed_categories: List[Dict[str, str]],
) -> Dict[str, str]:

    if not chunk_text.strip():

        raise ValueError(
            "Le chunk est vide."
        )

    if not allowed_categories:

        raise ValueError(
            "Aucune catégorie autorisée "
            "n'a été fournie."
        )

    allowed_names = [
        category["name"]
        for category in allowed_categories
    ]

    prompt = f"""
Tu es un expert en cybersécurité.

Tu dois attribuer UNE SEULE catégorie principale
au texte fourni.

IMPORTANT :
- Tu dois choisir UNIQUEMENT parmi les catégories autorisées.
- Tu ne dois JAMAIS créer une nouvelle catégorie.
- Tu ne dois JAMAIS reformuler le nom d'une catégorie.
- Tu dois retourner exactement le nom d'une catégorie de la liste.
- Choisis la catégorie qui représente le mieux le sujet principal du texte.
- Si une catégorie très précise correspond au contenu,
  préfère-la à une catégorie plus générale.

CATÉGORIES AUTORISÉES :

{json.dumps(
    allowed_names,
    ensure_ascii=False,
    indent=2
)}

TEXTE DU CHUNK :

{chunk_text}

Réponds UNIQUEMENT avec ce JSON :

{{
    "category": "Nom exact de la catégorie"
}}
"""

    response = llm.invoke(prompt)

    print(
        "[CategoryClassifier] "
        "Réponse brute de Qwen pour le chunk:"
    )

    print(response)

    data = _clean_json_response(
        response
    )

    category_name = data.get(
        "category"
    )

    if not isinstance(
        category_name,
        str
    ):

        raise ValueError(
            "Le modèle n'a pas retourné "
            "de catégorie valide."
        )

    category = get_category_by_name(
        category_name
    )

    if category is None:

        raise ValueError(
            "Catégorie inconnue retournée "
            f"par le modèle : {category_name}"
        )

    if category_name not in allowed_names:

        raise ValueError(
            f"La catégorie '{category_name}' "
            "ne fait pas partie des catégories "
            "autorisées pour ce document."
        )

    return category