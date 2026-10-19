
"""Classe les chunks WebIA dont la catégorie est manquante.

Garanties :
- Utilise exclusivement les 50 catégories prédéfinies.
- Récupère les textes existants dans ChromaDB sans réindexer les PDF.
- Enregistre les catégories au fur et à mesure.
- Ignore les chunks déjà classés pour permettre la reprise.
- Ne supprime ni ne modifie les questions existantes.
- Ne modifie ni question_count ni question_limit.
- Le mode --dry-run ne lance pas Ollama et ne modifie aucune donnée.
"""

import argparse
from collections import Counter

from app.database.connection import get_connection
from app.services.chroma import collection
from app.services.categories import get_all_categories
from app.services.category_classifier import (
    classify_chunk,
    classify_chunks_batch,
)


EXPECTED_CATEGORY_COUNT = 50
DEFAULT_BATCH_SIZE = 5
CHROMA_BATCH_SIZE = 100
MAX_INDIVIDUAL_RETRIES = 2


def get_missing_chunks():
    """Retourne tous les chunks sans catégorie, avec ou sans QCM."""
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    dc.id,
                    dc.document_id,
                    d.file_name,
                    dc.chunk_index,
                    dc.chroma_id
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE dc.category_id IS NULL
                ORDER BY dc.document_id, dc.chunk_index
                """
            )
            return cursor.fetchall()
    finally:
        conn.close()


def get_chroma_texts(chroma_ids):
    """Récupère les textes déjà indexés dans ChromaDB."""
    texts = {}
    unique_ids = list(dict.fromkeys(
        chroma_id for chroma_id in chroma_ids if chroma_id
    ))

    for offset in range(0, len(unique_ids), CHROMA_BATCH_SIZE):
        batch_ids = unique_ids[offset:offset + CHROMA_BATCH_SIZE]

        result = collection.get(
            ids=batch_ids,
            include=["documents"],
        )

        returned_ids = result.get("ids") or []
        documents = result.get("documents") or []

        for chroma_id, document_text in zip(returned_ids, documents):
            if isinstance(document_text, str) and document_text.strip():
                texts[chroma_id] = document_text

    return texts


def validate_categories(categories):
    """Vérifie la liste fermée des 50 catégories."""
    if len(categories) != EXPECTED_CATEGORY_COUNT:
        raise RuntimeError(
            f"{EXPECTED_CATEGORY_COUNT} catégories attendues, "
            f"{len(categories)} trouvées."
        )

    allowed_ids = set()

    for category in categories:
        try:
            category_id = int(category["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError(
                f"Catégorie invalide : {category!r}"
            ) from error

        if category_id in allowed_ids:
            raise RuntimeError(
                f"Identifiant de catégorie dupliqué : {category_id}"
            )

        allowed_ids.add(category_id)

    return allowed_ids


def save_category(chunk_id, document_id, category_id):
    """Enregistre une catégorie sans modifier les compteurs ni les QCM."""
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            # Ne touche qu'aux chunks toujours sans catégorie.
            cursor.execute(
                """
                UPDATE document_chunks
                SET category_id = %s
                WHERE id = %s
                  AND category_id IS NULL
                RETURNING id
                """,
                (category_id, chunk_id),
            )

            updated = cursor.fetchone()

            if updated is None:
                conn.rollback()
                return False

            cursor.execute(
                """
                INSERT INTO document_categories (
                    document_id,
                    category_id
                )
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (document_id, category_id),
            )

        conn.commit()
        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def classify_with_retry(text, categories):
    """Réessaie individuellement un chunk si le lot ne l'a pas classé."""
    if not isinstance(text, str) or not text.strip():
        return None

    for attempt in range(MAX_INDIVIDUAL_RETRIES):
        try:
            category = classify_chunk(
                text,
                categories,
                require_category=(attempt == 1),
            )

            if isinstance(category, dict) and category.get("id") is not None:
                return category

        except Exception as error:
            print(
                f"[Repair] Nouvelle tentative individuelle "
                f"{attempt + 1}/{MAX_INDIVIDUAL_RETRIES} : {error}"
            )

    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Vérifie les chunks sans lancer Ollama ni modifier la base.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        choices=range(1, 11),
        metavar="{1,2,3,4,5,6,7,8,9,10}",
        help="Nombre de chunks par lot (défaut : 5).",
    )

    args = parser.parse_args()

    categories = get_all_categories()
    allowed_ids = validate_categories(categories)
    chunks = get_missing_chunks()

    print(f"[Repair] Catégories autorisées : {len(categories)}")
    print(f"[Repair] Chunks sans catégorie : {len(chunks)}")

    if not chunks:
        print("[Repair] Aucun chunk à classer.")
        return

    chroma_ids = [row[4] for row in chunks if row[4]]
    texts_by_id = get_chroma_texts(chroma_ids)

    missing_texts = sum(
        1 for row in chunks
        if not row[4] or row[4] not in texts_by_id
    )

    print(f"[Repair] Textes récupérés dans ChromaDB : {len(texts_by_id)}")
    print(f"[Repair] Textes absents : {missing_texts}")

    if args.dry_run:
        print("[Repair] Diagnostic terminé : aucune donnée modifiée.")
        return

    assigned = 0
    unresolved = 0
    sql_errors = 0
    category_counts = Counter()

    for offset in range(0, len(chunks), args.batch_size):
        batch_rows = chunks[offset:offset + args.batch_size]

        valid_rows = []
        batch_texts = []

        for row in batch_rows:
            chroma_id = row[4]
            chunk_text = texts_by_id.get(chroma_id) if chroma_id else None

            if not chunk_text:
                unresolved += 1
                print(
                    f"[Repair] Chunk {row[0]} : texte absent, "
                    "il reste sans catégorie."
                )
                continue

            valid_rows.append(row)
            batch_texts.append(chunk_text)

        results = []

        if batch_texts:
            try:
                results = classify_chunks_batch(
                    batch_texts,
                    categories,
                    batch_size=args.batch_size,
                    require_category=False,
                )
            except Exception as error:
                print(
                    f"[Repair] Échec du lot {offset + 1} : {error}"
                )
                results = [None] * len(valid_rows)

        if len(results) != len(valid_rows):
            results = [None] * len(valid_rows)

        for row, chunk_text, category in zip(
            valid_rows, batch_texts, results
        ):
            chunk_id, document_id, file_name, chunk_index, chroma_id = row

            try:
                category_id = (
                    int(category["id"])
                    if isinstance(category, dict)
                    and category.get("id") is not None
                    else None
                )
            except (TypeError, ValueError):
                category_id = None

            if category_id not in allowed_ids:
                category = classify_with_retry(chunk_text, categories)

                try:
                    category_id = (
                        int(category["id"])
                        if isinstance(category, dict)
                        and category.get("id") is not None
                        else None
                    )
                except (TypeError, ValueError):
                    category_id = None

            if category_id not in allowed_ids:
                unresolved += 1
                print(
                    f"[Repair] Chunk {chunk_id} non résolu ; "
                    "il sera réessayé lors d'une prochaine exécution."
                )
                continue

            try:
                if save_category(chunk_id, document_id, category_id):
                    assigned += 1
                    category_counts[category_id] += 1

            except Exception as error:
                sql_errors += 1
                print(
                    f"[Repair] Erreur PostgreSQL pour le chunk "
                    f"{chunk_id} : {error}"
                )

        processed = min(offset + len(batch_rows), len(chunks))

        print(
            f"[Repair] Progression {processed}/{len(chunks)}"
            f" | attribuées={assigned}"
            f" | non résolus={unresolved}"
            f" | erreurs SQL={sql_errors}"
        )

    remaining = len(get_missing_chunks())

    print("\n========== RÉSULTAT FINAL ==========")
    print(f"Catégories attribuées pendant cette exécution : {assigned}")
    print(f"Chunks non résolus : {unresolved}")
    print(f"Erreurs SQL : {sql_errors}")
    print(f"Chunks encore sans catégorie : {remaining}")
    print(
        "[Repair] Questions, chunk_id, question_count et question_limit "
        "préservés."
    )

    if remaining:
        print(
            "[Repair] Tu peux relancer la même commande : "
            "les chunks déjà classés seront ignorés."
        )


if __name__ == "__main__":
    main()
