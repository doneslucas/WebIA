from pathlib import Path
import hashlib

from langchain_ollama import OllamaEmbeddings

from app.database.connection import get_connection

from app.services.pdf import (
    load_pdf,
    split_documents,
)

from app.services.chroma import (
    add_chunks,
    delete_file,
    is_file_indexed,
    get_file_chroma_ids,
)

from app.services.category_classifier import (
    classify_chunk,
)

from app.services.categories import (
    get_all_categories,
)

from app.services.task_manager import (
    task_manager,
)


DOCUMENTS_DIR = "documents"

# Maximum par difficulté : 5 easy, 5 medium et 5 hard.
QUESTION_LIMIT_PER_CHUNK = 5

# Maximum total : 15 questions par chunk toutes difficultés confondues.
TOTAL_QUESTION_LIMIT_PER_CHUNK = 15

QUIZ_DIFFICULTIES = (
    "easy",
    "medium",
    "hard",
)

QUESTION_BANK_TARGET = 50
EMBEDDING_BATCH_SIZE = 20


# ============================================================
# EMBEDDINGS
# ============================================================

embeddings_model = OllamaEmbeddings(
    model="nomic-embed-text",
)


# ============================================================
# PROGRESSION
# ============================================================

generation_progress = {}


def get_default_difficulty_progress():
    return {
        "status": "pending",
        "current": 0,
        "target": QUESTION_BANK_TARGET,
        "progress": 0,
    }


def get_default_indexing_progress():
    return {
        "status": "not_started",
        "progress": 0,
        "stage": "waiting",
        "details": "",
    }


def get_generation_progress(filename: str):
    progress = generation_progress.get(filename)

    if progress is None:
        return {
            "document": filename,
            "status": "not_started",
            "indexing": get_default_indexing_progress(),
            "indexing_progress": 0,
            "global_progress": 0,
            "easy": get_default_difficulty_progress(),
            "medium": get_default_difficulty_progress(),
            "hard": get_default_difficulty_progress(),
        }

    return progress


def initialize_progress(filename: str):
    generation_progress[filename] = {
        "document": filename,
        "status": "indexing",
        "indexing": {
            "status": "indexing",
            "progress": 0,
            "stage": "starting",
            "details": "Préparation de l'import du document...",
        },
        "indexing_progress": 0,
        "global_progress": 0,
        "easy": get_default_difficulty_progress(),
        "medium": get_default_difficulty_progress(),
        "hard": get_default_difficulty_progress(),
    }


def update_indexing_progress(
    filename: str,
    progress: int | None,
    status: str = "indexing",
    stage: str = "",
    details: str = "",
):
    """
    Met à jour l'étape d'indexation.

    La valeur du pourcentage est exclusivement pilotée par la
    classification des chunks.

    progress=None conserve le dernier pourcentage connu. Cela permet
    aux étapes hash, PDF, embeddings, ChromaDB et PostgreSQL de mettre
    à jour leur statut sans modifier le pourcentage de classification.
    """
    if filename not in generation_progress:
        initialize_progress(filename)

    current_indexing = generation_progress[filename].get(
        "indexing",
        get_default_indexing_progress(),
    )

    if progress is None:
        progress = generation_progress[filename].get(
            "indexing_progress",
            current_indexing.get("progress", 0),
        )
    else:
        progress = max(0, min(100, int(progress)))

    generation_progress[filename]["indexing"] = {
        "status": status,
        "progress": progress,
        "stage": stage,
        "details": details,
    }

    generation_progress[filename]["indexing_progress"] = progress


def update_generation_progress(
    filename: str,
    difficulty: str,
    current: int,
    target: int,
    status: str,
    category_id: int | None = None,
):
    """Met à jour la progression par catégorie/difficulté."""
    if filename not in generation_progress:
        initialize_progress(filename)

    progress = generation_progress[filename]
    banks = progress.setdefault("banks", {})

    bank_target = max(0, int(target))
    bank_current = max(0, int(current))
    bank_percentage = (
        100
        if bank_target == 0
        else min(100, int(bank_current / bank_target * 100))
    )

    if category_id is not None:
        bank_key = f"{category_id}:{difficulty}"
    else:
        bank_key = f"all:{difficulty}"

    banks[bank_key] = {
        "category_id": category_id,
        "difficulty": difficulty,
        "status": status,
        "current": bank_current,
        "target": bank_target,
        "progress": bank_percentage,
    }

    for difficulty_name in QUIZ_DIFFICULTIES:
        selected = [
            bank
            for bank in banks.values()
            if bank["difficulty"] == difficulty_name
        ]

        if not selected:
            continue

        total_current = sum(bank["current"] for bank in selected)
        total_target = sum(bank["target"] for bank in selected)
        total_progress = (
            100
            if total_target == 0
            else min(100, int(total_current / total_target * 100))
        )

        statuses = {bank["status"] for bank in selected}

        if statuses <= {"completed"}:
            difficulty_status = "completed"
        elif "running" in statuses:
            difficulty_status = "running"
        elif statuses & {"pending", "queued"}:
            difficulty_status = "queued"
        elif "error" in statuses:
            difficulty_status = "error"
        elif "incomplete" in statuses:
            difficulty_status = "incomplete"
        else:
            difficulty_status = "queued"

        progress[difficulty_name] = {
            "status": difficulty_status,
            "current": total_current,
            "target": total_target,
            "progress": total_progress,
        }

    difficulty_values = [
        progress.get(
            name,
            get_default_difficulty_progress(),
        )
        for name in QUIZ_DIFFICULTIES
    ]

    progress["global_progress"] = int(
        sum(item.get("progress", 0) for item in difficulty_values)
        / len(difficulty_values)
    )

    bank_statuses = [bank["status"] for bank in banks.values()]

    if bank_statuses and all(
        value == "completed" for value in bank_statuses
    ):
        progress["status"] = "completed"
    elif "running" in bank_statuses:
        progress["status"] = "generating"
    elif set(bank_statuses) & {"pending", "queued"}:
        progress["status"] = "queued"
    elif "error" in bank_statuses:
        progress["status"] = "error"
    elif "incomplete" in bank_statuses:
        progress["status"] = "incomplete"


def initialize_generation_progress(
    filename: str,
    category_ids: list[int] | None = None,
):
    """Initialise les banques de génération d'un document."""
    if filename not in generation_progress:
        generation_progress[filename] = {
            "document": filename,
            "status": "queued",
            "indexing": {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "details": "Indexation du document terminée.",
            },
            "indexing_progress": 100,
            "global_progress": 0,
            "easy": get_default_difficulty_progress(),
            "medium": get_default_difficulty_progress(),
            "hard": get_default_difficulty_progress(),
            "banks": {},
        }

    progress = generation_progress[filename]
    progress["status"] = "queued"
    progress["indexing"] = {
        "status": "completed",
        "progress": 100,
        "stage": "completed",
        "details": "Indexation du document terminée.",
    }
    progress["indexing_progress"] = 100

    banks = progress.setdefault("banks", {})

    for category_id in sorted(set(category_ids or [])):
        for difficulty in QUIZ_DIFFICULTIES:
            banks.setdefault(
                f"{category_id}:{difficulty}",
                {
                    "category_id": category_id,
                    "difficulty": difficulty,
                    "status": "pending",
                    "current": 0,
                    "target": QUESTION_BANK_TARGET,
                    "progress": 0,
                },
            )

    for difficulty in QUIZ_DIFFICULTIES:
        selected = [
            bank
            for bank in banks.values()
            if bank["difficulty"] == difficulty
        ]

        if selected:
            progress[difficulty] = {
                "status": "queued",
                "current": sum(bank["current"] for bank in selected),
                "target": sum(bank["target"] for bank in selected),
                "progress": int(
                    sum(bank["progress"] for bank in selected)
                    / len(selected)
                ),
            }
        else:
            progress[difficulty] = get_default_difficulty_progress()


# ============================================================
# DEMANDE DE REMPLISSAGE DE LA BANQUE
# ============================================================

def queue_document_question_banks(
    filename: str,
    category_ids: list[int],
    enqueue: bool = False,
    difficulties: list[str] | None = None,
):
    """
    Transmet le document au QuestionBankManager si la génération
    a été explicitement demandée.

    L'indexation d'un PDF ne déclenche pas automatiquement les QCM.
    """
    category_ids = sorted(set(category_ids))
    selected_difficulties = list(difficulties or QUIZ_DIFFICULTIES)

    invalid_difficulties = (
        set(selected_difficulties) - set(QUIZ_DIFFICULTIES)
    )

    if invalid_difficulties:
        raise ValueError(
            "Difficultés invalides : "
            + ", ".join(sorted(invalid_difficulties))
        )

    initialize_generation_progress(
        filename,
        category_ids=category_ids,
    )

    if not enqueue:
        progress = generation_progress[filename]
        progress["status"] = "waiting_manual"
        progress["global_progress"] = 0

        for bank in progress.setdefault("banks", {}).values():
            bank["status"] = "not_started"

        for difficulty in QUIZ_DIFFICULTIES:
            progress[difficulty] = {
                "status": "not_started",
                "current": 0,
                "target": 0,
                "progress": 0,
            }

        progress["generation_message"] = (
            "Indexation terminée. La génération des questions attend "
            "un lancement manuel."
        )

        print(
            "[Indexer] Génération automatique désactivée pour "
            f"{filename}. En attente d'une demande explicite."
        )

        return {
            "status": "waiting_manual",
            "queued": 0,
        }

    if not category_ids:
        print(
            "[Indexer] Aucune catégorie disponible pour "
            f"{filename}. Aucune tâche de génération ajoutée."
        )

        progress = generation_progress[filename]
        progress["status"] = "completed"
        progress["global_progress"] = 100

        for difficulty in QUIZ_DIFFICULTIES:
            progress[difficulty] = {
                "status": "completed",
                "current": 0,
                "target": 0,
                "progress": 100,
            }

        return {
            "status": "completed",
            "queued": 0,
        }

    from app.services.question_bank_manager import question_bank_manager

    queued = question_bank_manager.enqueue_document(
        document=filename,
        category_ids=category_ids,
        difficulties=selected_difficulties,
    )

    generation_progress[filename]["status"] = "queued"
    generation_progress[filename]["generation_message"] = (
        "Génération demandée manuellement."
    )

    for bank in generation_progress[filename].setdefault("banks", {}).values():
        if bank.get("difficulty") in selected_difficulties:
            bank["status"] = "queued"

    print(
        "[Indexer] Tâches de banque ajoutées pour "
        f"{filename} : {len(queued)}."
    )

    return {
        "status": "queued",
        "queued": queued,
    }


# ============================================================
# RÉCUPÉRATION DES CATÉGORIES D'UN DOCUMENT
# ============================================================

def get_document_category_ids(document_id: int) -> list[int]:
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT category_id
                FROM document_chunks
                WHERE document_id = %s
                  AND category_id IS NOT NULL
                ORDER BY category_id
                """,
                (document_id,),
            )

            return [row[0] for row in cursor.fetchall()]

    finally:
        connection.close()


# ============================================================
# GESTION DES DOCUMENTS
# ============================================================

def get_all_documents():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    file_name,
                    chunk_count,
                    created_at
                FROM documents
                ORDER BY created_at DESC
                """
            )

            rows = cursor.fetchall()
            documents = []

            for row in rows:
                documents.append(
                    {
                        "id": row[0],
                        "file": row[1],
                        "chunks": row[2],
                        "created_at": (
                            row[3].isoformat()
                            if row[3] is not None
                            else None
                        ),
                    }
                )

            return documents

    finally:
        connection.close()


def delete_document(
    file_name: str,
    documents_dir: str = DOCUMENTS_DIR,
):
    file_name = Path(file_name).name
    document_path = Path(documents_dir) / file_name
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM documents
                WHERE file_name = %s
                """,
                (file_name,),
            )

            document = cursor.fetchone()

            if document is None:
                raise ValueError(
                    f"Le document {file_name} n'existe pas en base."
                )

            document_id = document[0]

            cursor.execute(
                """
                DELETE FROM document_chunks
                WHERE document_id = %s
                """,
                (document_id,),
            )

            cursor.execute(
                """
                DELETE FROM documents
                WHERE id = %s
                """,
                (document_id,),
            )

            connection.commit()

        try:
            chroma_deleted = delete_file(file_name)
        except Exception as error:
            print(
                f"[Indexer] Erreur suppression ChromaDB pour "
                f"{file_name} : {error}"
            )
            chroma_deleted = 0

        file_deleted = False

        if document_path.exists():
            document_path.unlink()
            file_deleted = True

        generation_progress.pop(file_name, None)

        return {
            "document_id": document_id,
            "chroma_deleted": chroma_deleted,
            "file_deleted": file_deleted,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ============================================================
# HASH DU FICHIER
# ============================================================

def calculate_file_hash(file_path: str):
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            sha256.update(block)

    return sha256.hexdigest()


def get_existing_document(filename: str):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, file_hash, chunk_count
                FROM documents
                WHERE file_name = %s
                """,
                (filename,),
            )

            return cursor.fetchone()

    finally:
        connection.close()


def get_existing_document_by_hash(file_hash: str):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, file_name, file_hash, chunk_count
                FROM documents
                WHERE file_hash = %s
                """,
                (file_hash,),
            )

            return cursor.fetchone()

    finally:
        connection.close()


def delete_duplicate_file(
    file_path: str,
    requested_filename: str,
    canonical_filename: str,
):
    file_path_object = Path(file_path)

    if not file_path_object.exists():
        print(
            f"[Indexer] Le doublon {requested_filename} "
            "n'existe déjà plus sur le disque."
        )
        return False

    if requested_filename == canonical_filename:
        print(
            "[Indexer] Sécurité : le fichier demandé correspond au "
            "document canonique. Suppression annulée."
        )
        return False

    try:
        file_path_object.unlink()
        print(f"[Indexer] Doublon supprimé physiquement : {requested_filename}")
        print(f"[Indexer] Document canonique conservé : {canonical_filename}")
        return True

    except Exception as error:
        print(
            f"[Indexer] Impossible de supprimer le doublon "
            f"{requested_filename} : {error}"
        )
        raise


# ============================================================
# INDEXATION DU PDF
# ============================================================

def index_pdf(
    file_path: str,
    filename: str | None = None,
    force_reindex: bool = False,
    operation_already_reserved: bool = False,
):
    if filename is None:
        filename = Path(file_path).name

    filename = Path(filename).name
    requested_filename = filename

    print(f"[Indexer] Début de l'import : {requested_filename}")

    if force_reindex:
        print(
            "[Indexer] Réindexation forcée explicitement demandée pour "
            f"{requested_filename}."
        )

    initialize_progress(requested_filename)

    update_indexing_progress(
        filename=requested_filename,
        progress=0,
        status="indexing",
        stage="hash",
        details="Calcul du hash SHA-256...",
    )

    try:
        file_hash = calculate_file_hash(file_path)

        print(
            f"[Indexer] Hash SHA-256 calculé pour "
            f"{requested_filename} : {file_hash}"
        )

        update_indexing_progress(
            filename=requested_filename,
            progress=0,
            status="indexing",
            stage="verification",
            details="Vérification de PostgreSQL et ChromaDB...",
        )

        existing_document = get_existing_document(requested_filename)
        existing_document_by_hash = get_existing_document_by_hash(file_hash)
        content_changed = True
        # Snapshot de l'état PostgreSQL au début de l'opération. Pour un nouveau
        # document, si l'écriture Chroma réussit puis la transaction SQL échoue,
        # on retire les IDs fraîchement écrits pour ne pas recréer un orphelin.
        new_document_at_start = existing_document is None
        orphan_index_recovery = False

        # ----------------------------------------------------
        # Le même contenu existe déjà sous un autre nom.
        # ----------------------------------------------------

        if (
            existing_document_by_hash is not None
            and existing_document_by_hash[1] != requested_filename
        ):
            canonical_document_id = existing_document_by_hash[0]
            canonical_filename = existing_document_by_hash[1]
            canonical_chunk_count = existing_document_by_hash[3]

            print(
                "[Indexer] Contenu déjà présent. "
                f"Nom canonique : {canonical_filename}."
            )

            chroma_indexed = is_file_indexed(canonical_filename)

            if chroma_indexed:
                duplicate_file_deleted = delete_duplicate_file(
                    file_path=file_path,
                    requested_filename=requested_filename,
                    canonical_filename=canonical_filename,
                )

                update_indexing_progress(
                    filename=requested_filename,
                    progress=100,
                    status="completed",
                    stage="completed",
                    details=(
                        "Doublon supprimé. Contenu déjà indexé sous "
                        f"{canonical_filename}."
                    ),
                )

                generation_progress[requested_filename]["status"] = "completed"
                generation_progress[requested_filename]["global_progress"] = 100

                canonical_category_ids = get_document_category_ids(
                    canonical_document_id
                )

                queue_document_question_banks(
                    filename=canonical_filename,
                    category_ids=canonical_category_ids,
                )

                if not canonical_category_ids:
                    print(
                        "[Indexer] Le document canonique n'a pas encore de "
                        "chunks classifiés. Utiliser le script de réparation ; "
                        "aucune donnée existante ne sera supprimée."
                    )

                return {
                    "filename": canonical_filename,
                    "requested_filename": requested_filename,
                    "file": canonical_filename,
                    "chunk_count": canonical_chunk_count,
                    "document_id": canonical_document_id,
                    "already_indexed": True,
                    "duplicate_content": True,
                    "canonical_filename": canonical_filename,
                    "content_changed": False,
                    "duplicate_file_deleted": duplicate_file_deleted,
                }

            print(
                "[Indexer] L'index ChromaDB du document canonique manque. "
                "Une restauration de l'index est nécessaire."
            )
            raise ValueError(
                f"Le document canonique {canonical_filename} existe dans "
                "PostgreSQL mais son index ChromaDB est absent. "
                "Aucune réindexation automatique n'est déclenchée."
            )

        # ----------------------------------------------------
        # Le nom demandé existe déjà.
        # ----------------------------------------------------

        if existing_document is not None:
            existing_document_id = existing_document[0]
            existing_file_hash = existing_document[1]
            existing_chunk_count = existing_document[2]

            if existing_file_hash == file_hash:
                chroma_indexed = is_file_indexed(requested_filename)

                if chroma_indexed and not force_reindex:
                    existing_category_ids = get_document_category_ids(
                        existing_document_id
                    )

                    update_indexing_progress(
                        filename=requested_filename,
                        progress=100,
                        status="completed",
                        stage="completed",
                        details=(
                            "Document déjà présent dans PostgreSQL et "
                            f"ChromaDB : {existing_chunk_count} chunks. "
                            "Aucune réindexation destructive."
                        ),
                    )

                    generation_progress[requested_filename]["status"] = "completed"

                    if not existing_category_ids:
                        print(
                            "[Indexer] Les chunks existent, mais aucune "
                            "catégorie n'est attribuée. Le script de réparation "
                            "est nécessaire ; les questions seront conservées."
                        )

                    queue_document_question_banks(
                        filename=requested_filename,
                        category_ids=existing_category_ids,
                    )

                    return {
                        "filename": requested_filename,
                        "requested_filename": requested_filename,
                        "file": requested_filename,
                        "chunk_count": existing_chunk_count,
                        "document_id": existing_document_id,
                        "already_indexed": True,
                        "duplicate_content": False,
                        "canonical_filename": requested_filename,
                        "content_changed": False,
                        "duplicate_file_deleted": False,
                    }

                if not force_reindex and not chroma_indexed:
                    raise ValueError(
                        f"{requested_filename} existe dans PostgreSQL, "
                        "mais n'est plus indexé dans ChromaDB. La récupération "
                        "de ChromaDB doit être faite séparément ; aucune "
                        "réindexation destructive n'est déclenchée."
                    )

                if force_reindex:
                    print(
                        "[Indexer] Réindexation forcée demandée : "
                        "les données liées aux chunks pourront être supprimées."
                    )

                content_changed = True

            else:
                print(
                    "[Indexer] Le hash a changé pour "
                    f"{requested_filename} : réindexation du contenu nécessaire."
                )

                hash_owner = get_existing_document_by_hash(file_hash)

                if hash_owner is not None and hash_owner[0] != existing_document_id:
                    conflicting_filename = hash_owner[1]
                    duplicate_file_deleted = delete_duplicate_file(
                        file_path=file_path,
                        requested_filename=requested_filename,
                        canonical_filename=conflicting_filename,
                    )

                    conflicting_category_ids = get_document_category_ids(
                        hash_owner[0]
                    )

                    queue_document_question_banks(
                        filename=conflicting_filename,
                        category_ids=conflicting_category_ids,
                    )

                    return {
                        "filename": conflicting_filename,
                        "requested_filename": requested_filename,
                        "file": conflicting_filename,
                        "chunk_count": hash_owner[3],
                        "document_id": hash_owner[0],
                        "already_indexed": True,
                        "duplicate_content": True,
                        "canonical_filename": conflicting_filename,
                        "content_changed": False,
                        "duplicate_file_deleted": duplicate_file_deleted,
                    }

                content_changed = True

        # ----------------------------------------------------
        # Le document n'existe pas en base.
        # ----------------------------------------------------

        else:
            # On vérifie les IDs ChromaDB et les métadonnées source.
            # Leur présence n'est plus un blocage définitif : une nouvelle
            # indexation du PDF fourni peut reconstruire les chunks. La
            # suppression réelle des anciens IDs reste limitée au fichier.
            orphan_chroma_ids = get_file_chroma_ids(requested_filename)

            if orphan_chroma_ids:
                orphan_index_recovery = True
                print(
                    "[Indexer] Index ChromaDB orphelin détecté pour "
                    f"{requested_filename} : {len(orphan_chroma_ids)} chunk(s)."
                )
                print(
                    "[Indexer] Le document n'existe pas dans PostgreSQL. "
                    "Le PDF fourni sera réindexé et l'index orphelin remplacé."
                )

            content_changed = True

        # ====================================================
        # OPÉRATION PDF
        # ====================================================

        operation_started_here = not operation_already_reserved

        if operation_started_here:
            task_manager.start_pdf_operation()

        try:
            update_indexing_progress(
                filename=requested_filename,
                progress=0,
                status="indexing",
                stage="pdf",
                details="Lecture du PDF...",
            )

            documents = load_pdf(file_path)

            update_indexing_progress(
                filename=requested_filename,
                progress=0,
                status="indexing",
                stage="chunks",
                details="Découpage du document en chunks...",
            )

            chunks = split_documents(documents)

            print(
                f"[Indexer] {len(chunks)} chunks générés pour {filename}"
            )

            if not chunks:
                raise ValueError(
                    "Aucun chunk n'a été généré à partir du PDF."
                )

            texts = [chunk.page_content for chunk in chunks]

            # =================================================
            # CLASSIFICATION DES CHUNKS
            # =================================================

            total_chunks = len(chunks)

            update_indexing_progress(
                filename=requested_filename,
                progress=0,
                status="indexing",
                stage="categories",
                details=f"Classification des chunks : 0/{total_chunks}",
            )

            task_manager.wait_for_pdf_permission()

            allowed_categories = get_all_categories()

            if len(allowed_categories) != 50:
                raise ValueError(
                    "LA RAISON attend une liste de 50 catégories prédéfinies ; "
                    f"{len(allowed_categories)} catégories ont été trouvées. "
                    "Aucune nouvelle catégorie n'a été créée."
                )

            # Tous les chunks sont conservés pour le RAG.
            # Un chunk sans catégorie ne peut simplement pas alimenter les QCM.
            valid_chunks = list(chunks)
            valid_texts = list(texts)
            chunk_categories = []
            document_category_ids = set()
            uncategorized_chunks = 0

            allowed_by_id = {
                int(category["id"]): category
                for category in allowed_categories
            }

            for chunk_index, chunk_text in enumerate(texts):
                task_manager.wait_for_pdf_permission()

                chunk_number = chunk_index + 1

                update_indexing_progress(
                    filename=requested_filename,
                    progress=None,
                    status="indexing",
                    stage="categories",
                    details=(
                        f"Classification du chunk {chunk_number}/"
                        f"{total_chunks} en cours..."
                    ),
                )

                print(
                    "[Indexer] Classification du chunk "
                    f"{chunk_number}/{total_chunks}..."
                )

                category = None

                try:
                    category = classify_chunk(
                        chunk_text,
                        allowed_categories,
                    )
                except Exception as error:
                    print(
                        "[Indexer] Classification impossible pour le chunk "
                        f"{chunk_number}/{total_chunks} : {error}. "
                        "Le chunk sera conservé sans catégorie."
                    )

                category_id = None

                if isinstance(category, dict) and category.get("id") is not None:
                    try:
                        candidate_id = int(category["id"])
                    except (TypeError, ValueError):
                        candidate_id = None

                    if candidate_id in allowed_by_id:
                        category_id = candidate_id
                        category = allowed_by_id[candidate_id]
                    else:
                        category = None

                if category is None:
                    uncategorized_chunks += 1
                    chunk_categories.append(None)

                    print(
                        "[Indexer] Chunk "
                        f"{chunk_number}/{total_chunks} conservé sans catégorie."
                    )
                else:
                    chunk_categories.append(category)
                    document_category_ids.add(category_id)

                    print(
                        "[Indexer] Chunk "
                        f"{chunk_number}/{total_chunks} → {category['name']}"
                    )

                category_progress = int(chunk_number / total_chunks * 100)

                update_indexing_progress(
                    filename=requested_filename,
                    progress=category_progress,
                    status="indexing",
                    stage="categories",
                    details=(
                        f"Classification des chunks : "
                        f"{chunk_number}/{total_chunks} terminés "
                        f"({uncategorized_chunks} sans catégorie)"
                    ),
                )

            if len(chunk_categories) != len(valid_chunks):
                raise ValueError(
                    "Le nombre de catégories ne correspond pas au nombre de chunks."
                )

            print(
                f"[Indexer] {len(valid_chunks)} chunks conservés sur "
                f"{total_chunks}; {uncategorized_chunks} sans catégorie."
            )

            document_categories = [
                category
                for category in allowed_categories
                if int(category["id"]) in document_category_ids
            ]

            print(
                f"[Indexer] {len(document_categories)} catégories détectées "
                f"pour {filename}."
            )

            for category in document_categories:
                print(
                    f"[Indexer] - {category['id']} : {category['name']} "
                    f"({category['family']})"
                )

            # =================================================
            # EMBEDDINGS
            # =================================================

            vectors = []
            total_texts = len(valid_texts)

            update_indexing_progress(
                filename=requested_filename,
                progress=None,
                status="indexing",
                stage="embeddings",
                details=f"Préparation des embeddings : 0/{total_texts}",
            )

            for batch_start in range(0, total_texts, EMBEDDING_BATCH_SIZE):
                task_manager.wait_for_pdf_permission()

                batch_end = min(
                    batch_start + EMBEDDING_BATCH_SIZE,
                    total_texts,
                )

                batch_texts = valid_texts[batch_start:batch_end]

                print(
                    "[Indexer] Embeddings : "
                    f"{batch_start + 1}-{batch_end}/{total_texts}"
                )

                batch_vectors = embeddings_model.embed_documents(batch_texts)

                if not batch_vectors:
                    raise ValueError(
                        f"Aucun embedding généré pour le lot "
                        f"{batch_start + 1}-{batch_end}."
                    )

                if len(batch_vectors) != len(batch_texts):
                    raise ValueError(
                        "Le nombre d'embeddings du lot ne correspond pas "
                        "au nombre de textes envoyés."
                    )

                vectors.extend(batch_vectors)

                update_indexing_progress(
                    filename=requested_filename,
                    progress=None,
                    status="indexing",
                    stage="embeddings",
                    details=f"Embeddings : {batch_end}/{total_texts}",
                )

            if not vectors:
                raise ValueError("Aucun embedding n'a été généré.")

            if len(vectors) != len(valid_chunks):
                raise ValueError(
                    "Le nombre d'embeddings ne correspond pas au nombre de chunks."
                )

            # =================================================
            # CHROMADB
            # =================================================

            update_indexing_progress(
                filename=requested_filename,
                progress=None,
                status="indexing",
                stage="chroma",
                details="Préparation de ChromaDB...",
            )

            task_manager.wait_for_pdf_permission()

            if content_changed:
                print(
                    f"[Indexer] Suppression de l'ancien index ChromaDB "
                    f"pour {filename}..."
                )

                chroma_deleted = delete_file(filename)

                print(
                    f"[Indexer] {chroma_deleted} anciens chunks supprimés "
                    "de ChromaDB."
                )

            task_manager.wait_for_pdf_permission()

            try:
                add_chunks(
                    chunks=valid_chunks,
                    vectors=vectors,
                    file_name=filename,
                )
            except Exception:
                # Pour un document absent de PostgreSQL au début de l'opération,
                # aucune ligne SQL existante n'est à préserver. Nettoyer les IDs
                # de ce fichier évite de laisser un index partiel après l'échec.
                if new_document_at_start:
                    try:
                        delete_file(requested_filename)
                    except Exception as cleanup_error:
                        print(
                            "[Indexer] Échec du nettoyage après erreur ChromaDB "
                            f"pour {filename} : {cleanup_error}"
                        )
                raise

            print(f"[Indexer] Indexation ChromaDB terminée : {filename}")

            # =================================================
            # POSTGRESQL
            # =================================================

            update_indexing_progress(
                filename=requested_filename,
                progress=None,
                status="indexing",
                stage="postgresql",
                details="Enregistrement du document en base...",
            )

            task_manager.wait_for_pdf_permission()

            # Ouvrir la connexion à l'intérieur du try est important : si
            # PostgreSQL est momentanément indisponible après l'écriture ChromaDB,
            # le bloc except doit tout de même nettoyer l'index d'un nouveau PDF.
            connection = None
            duplicate_file_deleted = False

            try:
                connection = get_connection()
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id
                        FROM documents
                        WHERE file_name = %s
                        """,
                        (filename,),
                    )

                    existing_document = cursor.fetchone()

                    if existing_document is not None:
                        document_id = existing_document[0]

                        # Ce chemin ne doit être utilisé que pour une véritable
                        # réindexation, pas pour une réparation de catégories.
                        cursor.execute(
                            """
                            DELETE FROM document_chunks
                            WHERE document_id = %s
                            """,
                            (document_id,),
                        )

                        cursor.execute(
                            """
                            DELETE FROM document_categories
                            WHERE document_id = %s
                            """,
                            (document_id,),
                        )

                        cursor.execute(
                            """
                            UPDATE documents
                            SET
                                file_hash = %s,
                                chunk_count = %s,
                                created_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                            """,
                            (
                                file_hash,
                                len(valid_chunks),
                                document_id,
                            ),
                        )

                    else:
                        cursor.execute(
                            """
                            SELECT id, file_name, chunk_count
                            FROM documents
                            WHERE file_hash = %s
                            """,
                            (file_hash,),
                        )

                        hash_owner = cursor.fetchone()

                        if hash_owner is not None:
                            document_id = hash_owner[0]
                            canonical_filename = hash_owner[1]
                            filename = canonical_filename

                            cursor.execute(
                                """
                                DELETE FROM document_chunks
                                WHERE document_id = %s
                                """,
                                (document_id,),
                            )

                            cursor.execute(
                                """
                                DELETE FROM document_categories
                                WHERE document_id = %s
                                """,
                                (document_id,),
                            )

                            cursor.execute(
                                """
                                UPDATE documents
                                SET
                                    chunk_count = %s,
                                    created_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                                """,
                                (
                                    len(valid_chunks),
                                    document_id,
                                ),
                            )

                        else:
                            cursor.execute(
                                """
                                INSERT INTO documents (
                                    file_name,
                                    file_hash,
                                    chunk_count
                                )
                                VALUES (%s, %s, %s)
                                RETURNING id
                                """,
                                (
                                    filename,
                                    file_hash,
                                    len(valid_chunks),
                                ),
                            )

                            document_id = cursor.fetchone()[0]

                    # Liens correspondant aux catégories réellement portées
                    # par les chunks. Aucune catégorie n'est inventée ici.
                    for category in document_categories:
                        cursor.execute(
                            """
                            INSERT INTO document_categories (
                                document_id,
                                category_id
                            )
                            VALUES (%s, %s)
                            ON CONFLICT (document_id, category_id)
                            DO NOTHING
                            """,
                            (
                                document_id,
                                category["id"],
                            ),
                        )

                    # Tous les chunks sont insérés, même sans category_id.
                    for chunk_index in range(len(valid_chunks)):
                        chroma_id = f"{filename}_chunk_{chunk_index}"
                        category = chunk_categories[chunk_index]

                        cursor.execute(
                            """
                            INSERT INTO document_chunks (
                                document_id,
                                chunk_index,
                                chroma_id,
                                question_count,
                                question_limit,
                                category_id
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                document_id,
                                chunk_index,
                                chroma_id,
                                0,
                                TOTAL_QUESTION_LIMIT_PER_CHUNK,
                                (
                                    category["id"]
                                    if category is not None
                                    else None
                                ),
                            ),
                        )

                    connection.commit()

            except Exception:
                if connection is not None:
                    try:
                        connection.rollback()
                    except Exception as rollback_error:
                        print(
                            "[Indexer] Échec du rollback PostgreSQL pour "
                            f"{requested_filename} : {rollback_error}"
                        )

                # Aucun document PostgreSQL n'existait au début de cette opération.
                # Même si l'ouverture de la connexion elle-même échoue après la
                # création Chroma, on retire uniquement les IDs de ce PDF pour
                # éviter de laisser un nouvel index orphelin.
                if new_document_at_start:
                    try:
                        delete_file(requested_filename)
                        print(
                            "[Indexer] Index ChromaDB temporaire retiré après "
                            f"échec PostgreSQL pour {requested_filename}. Le PDF reste "
                            "disponible pour une nouvelle tentative."
                        )
                    except Exception as cleanup_error:
                        print(
                            "[Indexer] Échec du nettoyage ChromaDB après erreur "
                            f"PostgreSQL pour {requested_filename} : {cleanup_error}"
                        )
                raise

            finally:
                if connection is not None:
                    connection.close()

            if (
                requested_filename != filename
                and file_hash == calculate_file_hash(file_path)
            ):
                duplicate_file_deleted = delete_duplicate_file(
                    file_path=file_path,
                    requested_filename=requested_filename,
                    canonical_filename=filename,
                )

            update_indexing_progress(
                filename=requested_filename,
                progress=None,
                status="completed",
                stage="completed",
                details=(
                    f"Indexation terminée : {len(valid_chunks)} chunks "
                    f"enregistrés sous {filename}. "
                    f"{uncategorized_chunks} chunk(s) sans catégorie."
                    + (
                        f" Doublon {requested_filename} supprimé."
                        if duplicate_file_deleted
                        else ""
                    )
                ),
            )

            print(
                f"[Indexer] Document enregistré en base : id={document_id}"
            )
            print(
                f"[Indexer] {len(valid_chunks)} chunks enregistrés "
                f"dans document_chunks pour {filename}"
            )
            print(
                f"[Indexer] {uncategorized_chunks} chunks conservés "
                "sans catégorie."
            )
            print(f"[Indexer] Indexation terminée : {filename}")

            # Important : aucune génération de questions n'est lancée ici.
            queue_document_question_banks(
                filename=filename,
                category_ids=list(document_category_ids),
            )

            return {
                "filename": filename,
                "requested_filename": requested_filename,
                "file": filename,
                "chunk_count": len(valid_chunks),
                "excluded_chunk_count": uncategorized_chunks,
                "uncategorized_chunk_count": uncategorized_chunks,
                "document_id": document_id,
                "already_indexed": False,
                "duplicate_content": filename != requested_filename,
                "canonical_filename": filename,
                "content_changed": content_changed,
                "duplicate_file_deleted": duplicate_file_deleted,
            }

        finally:
            if operation_started_here:
                task_manager.end_pdf_operation()

    except Exception as error:
        print(
            f"[Indexer] Erreur indexation {requested_filename} : {error}"
        )

        if requested_filename not in generation_progress:
            initialize_progress(requested_filename)

        current_progress = generation_progress[requested_filename].get(
            "indexing_progress",
            0,
        )

        update_indexing_progress(
            filename=requested_filename,
            progress=current_progress,
            status="error",
            stage="error",
            details=str(error),
        )

        generation_progress[requested_filename]["status"] = "error"
        raise
