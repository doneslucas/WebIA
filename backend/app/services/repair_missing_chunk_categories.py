
"""Répare les catégories des chunks liés aux questions existantes.

- Ne supprime aucune question.
- Ne modifie aucun chunk_id de question.
- Ne réindexe aucun PDF.
- Ne traite que les chunks sans catégorie qui possèdent déjà des questions.
- Utilise exclusivement les 50 catégories prédéfinies.
- Ne modifie pas question_limit.
"""

import argparse

from app.database.connection import get_connection
from app.services.chroma import collection
from app.services.categories import get_all_categories
from app.services.category_classifier import classify_chunks_batch


# ============================================================
# LECTURE DE LA BASE
# ============================================================

def get_missing_chunks_with_questions():
    """Retourne les chunks sans catégorie utilisés par des questions."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    dc.id,
                    dc.document_id,
                    d.file_name,
                    dc.chunk_index,
                    dc.chroma_id,
                    COUNT(qq.id) AS question_count
                FROM document_chunks dc
                JOIN documents d
                    ON d.id = dc.document_id
                JOIN quiz_questions qq
                    ON qq.chunk_id = dc.id
                WHERE dc.category_id IS NULL
                GROUP BY
                    dc.id,
                    dc.document_id,
                    d.file_name,
                    dc.chunk_index,
                    dc.chroma_id
                ORDER BY
                    dc.document_id,
                    dc.chunk_index
                """
            )
            return cursor.fetchall()


def count_questions_without_valid_chunk():
    """Compte les questions sans chunk correspondant."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM quiz_questions qq
                LEFT JOIN document_chunks dc
                    ON dc.id = qq.chunk_id
                WHERE qq.chunk_id IS NULL
                   OR dc.id IS NULL
                """
            )
            return cursor.fetchone()[0]


# ============================================================
# LECTURE DES TEXTES EXISTANTS DANS CHROMADB
# ============================================================

def get_chroma_texts(rows):
    """Récupère les textes existants sans réindexer les documents."""
    ids = [row[4] for row in rows if row[4]]

    if not ids:
        return {}

    result = collection.get(
        ids=ids,
        include=["documents"],
    )

    result_ids = result.get("ids") or []
    documents = result.get("documents") or []

    return {
        chroma_id: text
        for chroma_id, text in zip(result_ids, documents)
        if (
            isinstance(chroma_id, str)
            and isinstance(text, str)
            and text.strip()
        )
    }


# ============================================================
# ENREGISTREMENT DES CATÉGORIES
# ============================================================

def write_categories(rows_and_categories):
    """
    Attribue une catégorie aux chunks encore non classés.

    Les questions restent liées à leurs chunks d'origine.
    """
    updated_count = 0

    with get_connection() as conn:
        with conn.cursor() as cursor:
            for row, category in rows_and_categories:
                (
                    chunk_id,
                    document_id,
                    _file_name,
                    _chunk_index,
                    _chroma_id,
                    _question_count,
                ) = row

                if not isinstance(category, dict) or "id" not in category:
                    continue

                category_id = int(category["id"])

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

                if cursor.fetchone() is None:
                    continue

                # Ajoute le lien document-catégorie s'il manque.
                cursor.execute(
                    """
                    INSERT INTO document_categories (
                        document_id,
                        category_id
                    )
                    SELECT %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM document_categories
                        WHERE document_id = %s
                          AND category_id = %s
                    )
                    """,
                    (
                        document_id,
                        category_id,
                        document_id,
                        category_id,
                    ),
                )

                updated_count += 1

        conn.commit()

    return updated_count


# ============================================================
# SYNCHRONISATION DES COMPTEURS ET DES ASSOCIATIONS
# ============================================================

def sync_category_links_and_counts():
    """
    Complète les associations document-catégorie existantes
    et recalcule les compteurs sans toucher aux questions.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_categories (
                    document_id,
                    category_id
                )
                SELECT DISTINCT
                    dc.document_id,
                    dc.category_id
                FROM document_chunks dc
                WHERE dc.category_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM document_categories dcat
                      WHERE dcat.document_id = dc.document_id
                        AND dcat.category_id = dc.category_id
                  )
                """
            )
            links_added = cursor.rowcount

            cursor.execute(
                """
                UPDATE document_chunks dc
                SET question_count = (
                    SELECT COUNT(*)
                    FROM quiz_questions qq
                    WHERE qq.chunk_id = dc.id
                )
                WHERE dc.question_count IS DISTINCT FROM (
                    SELECT COUNT(*)
                    FROM quiz_questions qq
                    WHERE qq.chunk_id = dc.id
                )
                """
            )
            counters_fixed = cursor.rowcount

        conn.commit()

    return links_added, counters_fixed


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Applique la classification. "
            "Cette opération utilise Ollama."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Nombre de chunks par lot, entre 1 et 10.",
    )

    args = parser.parse_args()

    if not 1 <= args.batch_size <= 10:
        parser.error("--batch-size doit être compris entre 1 et 10.")

    categories = get_all_categories()

    # LA RAISON : conserver exactement les catégories prédéfinies.
    if len(categories) != 50:
        raise RuntimeError(
            f"50 catégories sont attendues, mais la base en retourne "
            f"{len(categories)}. Aucune réparation effectuée."
        )

    rows = get_missing_chunks_with_questions()
    orphan_questions = count_questions_without_valid_chunk()

    print(f"[Repair] Catégories autorisées : {len(categories)}")
    print(
        "[Repair] Chunks sans catégorie utilisés par des questions : "
        f"{len(rows)}"
    )
    print(
        "[Repair] Questions sans chunk correspondant : "
        f"{orphan_questions}"
    )

    if not args.apply:
        print(
            "[Repair] Diagnostic uniquement. "
            "Aucune donnée modifiée."
        )
        print(
            "[Repair] Pour appliquer la réparation, "
            "relancer avec --apply."
        )
        return

    if not rows:
        links_added, counters_fixed = sync_category_links_and_counts()

        print("[Repair] Aucun chunk à catégoriser pour les questions existantes.")
        print(f"[Repair] Associations ajoutées : {links_added}")
        print(f"[Repair] Compteurs corrigés : {counters_fixed}")
        return

    classified_count = 0
    unresolved_count = 0
    missing_chroma_count = 0
    errors = []

    for offset in range(0, len(rows), args.batch_size):
        batch_rows = rows[offset:offset + args.batch_size]
        texts_by_id = get_chroma_texts(batch_rows)

        valid_rows = []
        texts = []

        for row in batch_rows:
            chunk_text = texts_by_id.get(row[4]) if row[4] else None

            if not chunk_text:
                missing_chroma_count += 1
                errors.append(
                    f"Chunk {row[0]} ({row[2]}, index {row[3]}) : "
                    "texte absent de ChromaDB."
                )
                continue

            valid_rows.append(row)
            texts.append(chunk_text)

        if texts:
            try:
                batch_categories = classify_chunks_batch(
                    texts,
                    categories,
                    batch_size=args.batch_size,
                    require_category=True,
                )
            except Exception as error:
                unresolved_count += len(valid_rows)
                errors.append(
                    f"Lot à partir de {offset + 1} : "
                    f"échec de classification : {error}"
                )
                continue

            if len(batch_categories) != len(valid_rows):
                unresolved_count += len(valid_rows)
                errors.append(
                    f"Lot à partir de {offset + 1} : "
                    "le nombre de catégories retournées ne correspond "
                    "pas au nombre de chunks."
                )
                continue

            rows_to_write = []

            for row, category in zip(valid_rows, batch_categories):
                if not isinstance(category, dict) or "id" not in category:
                    unresolved_count += 1
                    errors.append(
                        f"Chunk {row[0]} : aucune catégorie valide retournée."
                    )
                    continue

                try:
                    category_id = int(category["id"])
                except (TypeError, ValueError):
                    unresolved_count += 1
                    errors.append(
                        f"Chunk {row[0]} : identifiant de catégorie invalide."
                    )
                    continue

                if not any(
                    int(known_category["id"]) == category_id
                    for known_category in categories
                ):
                    unresolved_count += 1
                    errors.append(
                        f"Chunk {row[0]} : catégorie {category_id} "
                        "absente de la liste autorisée."
                    )
                    continue

                rows_to_write.append((row, category))

            if rows_to_write:
                try:
                    classified_count += write_categories(rows_to_write)
                except Exception as error:
                    unresolved_count += len(rows_to_write)
                    errors.append(
                        f"Lot à partir de {offset + 1} : "
                        f"échec d'écriture PostgreSQL : {error}"
                    )

        processed = min(offset + len(batch_rows), len(rows))

        print(
            f"[Repair] Traités {processed}/{len(rows)}"
            f" | catégories attribuées={classified_count}"
            f" | non résolus={unresolved_count}"
            f" | textes absents={missing_chroma_count}"
        )

    links_added, counters_fixed = sync_category_links_and_counts()

    remaining = len(get_missing_chunks_with_questions())
    orphan_questions = count_questions_without_valid_chunk()

    print("\n[Repair] Résultat final")
    print(f"[Repair] Chunks catégorisés : {classified_count}")
    print(f"[Repair] Textes absents de ChromaDB : {missing_chroma_count}")
    print(f"[Repair] Chunks non résolus : {unresolved_count}")
    print(f"[Repair] Chunks encore sans catégorie avec questions : {remaining}")
    print(f"[Repair] Questions sans chunk correspondant : {orphan_questions}")
    print(f"[Repair] Associations document-catégorie ajoutées : {links_added}")
    print(f"[Repair] Compteurs corrigés : {counters_fixed}")

    if errors:
        print("\n[Repair] Éléments à examiner :")
        for error in errors:
            print(f"- {error}")

    print(
        "\n[Repair] Les questions et leurs chunk_id ont été conservés. "
        "Aucun PDF n'a été réindexé et question_limit n'a pas été modifié."
    )


if __name__ == "__main__":
    main()
