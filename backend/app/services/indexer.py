from pathlib import Path
import hashlib

from langchain_ollama import OllamaEmbeddings

from app.database.connection import get_connection

from app.services.pdf import (
    load_pdf,
    split_documents
)

from app.services.chroma import (
    add_chunks,
    delete_file
)

from app.services.quiz import (
    generate_questions_for_bank,
    count_questions
)

from app.services.task_manager import task_manager


DOCUMENTS_DIR = "documents"

QUESTION_LIMIT_PER_CHUNK = 5

QUIZ_DIFFICULTIES = (
    "easy",
    "medium",
    "hard"
)

QUESTION_BANK_TARGET = 50

EMBEDDING_BATCH_SIZE = 20


# ============================================================
# EMBEDDINGS
# ============================================================

embeddings_model = OllamaEmbeddings(
    model="nomic-embed-text"
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
        "progress": 0
    }


def get_default_indexing_progress():
    return {
        "status": "not_started",
        "progress": 0,
        "stage": "waiting",
        "details": ""
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
            "hard": get_default_difficulty_progress()
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
            "details": "Préparation de l'import du document..."
        },

        "indexing_progress": 0,

        "global_progress": 0,

        "easy": get_default_difficulty_progress(),
        "medium": get_default_difficulty_progress(),
        "hard": get_default_difficulty_progress()
    }


def update_indexing_progress(
    filename: str,
    progress: int,
    status: str = "indexing",
    stage: str = "",
    details: str = ""
):
    if filename not in generation_progress:
        initialize_progress(filename)

    progress = max(
        0,
        min(
            100,
            int(progress)
        )
    )

    generation_progress[filename][
        "indexing"
    ] = {
        "status": status,
        "progress": progress,
        "stage": stage,
        "details": details
    }

    generation_progress[filename][
        "indexing_progress"
    ] = progress


def update_generation_progress(
    filename: str,
    difficulty: str,
    current: int,
    target: int,
    status: str
):
    if filename not in generation_progress:
        initialize_progress(filename)

    progress = generation_progress[filename]

    percentage = 0

    if target > 0:
        percentage = min(
            100,
            int(
                (current / target) * 100
            )
        )

    progress[difficulty] = {
        "status": status,
        "current": current,
        "target": target,
        "progress": percentage
    }

    difficulties = [
        progress.get(
            difficulty_name,
            {
                "status": "pending",
                "current": 0,
                "target": target,
                "progress": 0
            }
        )

        for difficulty_name
        in QUIZ_DIFFICULTIES
    ]

    global_progress = int(
        sum(
            difficulty_data["progress"]
            for difficulty_data
            in difficulties
        )
        / len(difficulties)
    )

    progress["global_progress"] = global_progress


def initialize_generation_progress(
    filename: str
):
    if filename not in generation_progress:
        generation_progress[filename] = {
            "document": filename,
            "status": "generating",

            "indexing": {
                "status": "completed",
                "progress": 100,
                "stage": "completed",
                "details": "Indexation du document terminée."
            },

            "indexing_progress": 100,

            "global_progress": 0,

            "easy": get_default_difficulty_progress(),
            "medium": get_default_difficulty_progress(),
            "hard": get_default_difficulty_progress()
        }

        return

    progress = generation_progress[filename]

    progress["status"] = "generating"

    progress["indexing"] = {
        "status": "completed",
        "progress": 100,
        "stage": "completed",
        "details": "Indexation du document terminée."
    }

    progress["indexing_progress"] = 100

    for difficulty in QUIZ_DIFFICULTIES:
        progress[difficulty] = {
            "status": "pending",
            "current": 0,
            "target": QUESTION_BANK_TARGET,
            "progress": 0
        }

    progress["global_progress"] = 0


# ============================================================
# GÉNÉRATION DES BANQUES DE QUESTIONS
# ============================================================

def generate_document_question_banks(
    filename: str
):
    initialize_generation_progress(
        filename
    )

    try:

        for difficulty in QUIZ_DIFFICULTIES:

            current_before_generation = count_questions(
                filename,
                difficulty
            )

            if current_before_generation >= QUESTION_BANK_TARGET:

                update_generation_progress(
                    filename=filename,
                    difficulty=difficulty,
                    current=current_before_generation,
                    target=QUESTION_BANK_TARGET,
                    status="completed"
                )

                print(
                    f"[Indexer] "
                    f"Banque {difficulty} déjà complète "
                    f"pour {filename} : "
                    f"{current_before_generation}/"
                    f"{QUESTION_BANK_TARGET}"
                )

                continue

            update_generation_progress(
                filename=filename,
                difficulty=difficulty,
                current=current_before_generation,
                target=QUESTION_BANK_TARGET,
                status="generating"
            )

            try:

                def update_progress(
                    current_count: int
                ):
                    update_generation_progress(
                        filename=filename,
                        difficulty=difficulty,
                        current=current_count,
                        target=QUESTION_BANK_TARGET,
                        status="generating"
                    )

                print(
                    f"[Indexer] "
                    f"Vérification des priorités avant génération "
                    f"{difficulty} pour {filename}..."
                )

                task_manager.wait_for_background_permission()

                print(
                    f"[Indexer] "
                    f"Aucune priorité supérieure active. "
                    f"Démarrage génération {difficulty} "
                    f"pour {filename}."
                )

                generate_questions_for_bank(
                    document=filename,
                    difficulty=difficulty,
                    target_count=QUESTION_BANK_TARGET,
                    progress_callback=update_progress
                )

                current_count = count_questions(
                    filename,
                    difficulty
                )

                update_generation_progress(
                    filename=filename,
                    difficulty=difficulty,
                    current=current_count,
                    target=QUESTION_BANK_TARGET,
                    status="completed"
                )

            except Exception as error:

                print(
                    f"[Indexer] "
                    f"Erreur génération {difficulty} "
                    f"pour {filename} : {error}"
                )

                try:
                    current_count = count_questions(
                        filename,
                        difficulty
                    )

                except Exception:
                    current_count = 0

                update_generation_progress(
                    filename=filename,
                    difficulty=difficulty,
                    current=current_count,
                    target=QUESTION_BANK_TARGET,
                    status="error"
                )

        all_completed = all(
            generation_progress[
                filename
            ][difficulty]["status"]
            == "completed"

            for difficulty
            in QUIZ_DIFFICULTIES
        )

        if all_completed:

            generation_progress[
                filename
            ]["status"] = "completed"

            generation_progress[
                filename
            ]["global_progress"] = 100

            print(
                f"[Indexer] "
                f"Génération terminée pour {filename}"
            )

        else:

            generation_progress[
                filename
            ]["status"] = "error"

            print(
                f"[Indexer] "
                f"Génération terminée avec des erreurs "
                f"pour {filename}"
            )

    except Exception as error:

        print(
            f"[Indexer] "
            f"Erreur générale pour {filename} : {error}"
        )

        if filename in generation_progress:
            generation_progress[
                filename
            ]["status"] = "error"


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
                        )
                    }
                )

            return documents

    finally:
        connection.close()


def delete_document(
    file_name: str,
    documents_dir: str = DOCUMENTS_DIR
):
    file_name = Path(
        file_name
    ).name

    document_path = (
        Path(documents_dir)
        / file_name
    )

    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT id
                FROM documents
                WHERE file_name = %s
                """,
                (file_name,)
            )

            document = cursor.fetchone()

            if document is None:

                raise ValueError(
                    f"Le document {file_name} "
                    f"n'existe pas en base."
                )

            document_id = document[0]

            cursor.execute(
                """
                DELETE FROM document_chunks
                WHERE document_id = %s
                """,
                (document_id,)
            )

            cursor.execute(
                """
                DELETE FROM documents
                WHERE id = %s
                """,
                (document_id,)
            )

            connection.commit()

        chroma_deleted = 0

        try:

            chroma_deleted = delete_file(
                file_name
            )

        except Exception as error:

            print(
                f"[Indexer] "
                f"Erreur suppression ChromaDB "
                f"pour {file_name} : {error}"
            )

        file_deleted = False

        if document_path.exists():

            document_path.unlink()

            file_deleted = True

        generation_progress.pop(
            file_name,
            None
        )

        return {
            "document_id": document_id,
            "chroma_deleted": chroma_deleted,
            "file_deleted": file_deleted
        }

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()


# ============================================================
# HASH DU FICHIER
# ============================================================

def calculate_file_hash(
    file_path: str
):
    sha256 = hashlib.sha256()

    with open(
        file_path,
        "rb"
    ) as file:

        for block in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):

            sha256.update(
                block
            )

    return sha256.hexdigest()


def get_existing_document(
    filename: str
):
    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    file_hash,
                    chunk_count
                FROM documents
                WHERE file_name = %s
                """,
                (filename,)
            )

            return cursor.fetchone()

    finally:

        connection.close()


# ============================================================
# INDEXATION DU PDF
# ============================================================

def index_pdf(
    file_path: str,
    filename: str | None = None
):
    if filename is None:

        filename = Path(
            file_path
        ).name

    filename = Path(
        filename
    ).name

    print(
        f"[Indexer] "
        f"Début de l'import : {filename}"
    )

    initialize_progress(
        filename
    )

    update_indexing_progress(
        filename=filename,
        progress=5,
        status="indexing",
        stage="hash",
        details="Calcul du hash SHA-256..."
    )

    try:

        file_hash = calculate_file_hash(
            file_path
        )

        print(
            f"[Indexer] "
            f"Hash SHA-256 calculé pour {filename} : "
            f"{file_hash}"
        )

        update_indexing_progress(
            filename=filename,
            progress=10,
            status="indexing",
            stage="verification",
            details="Vérification du document existant..."
        )

        existing_document = get_existing_document(
            filename
        )

        if existing_document is not None:

            existing_document_id = existing_document[0]
            existing_file_hash = existing_document[1]
            existing_chunk_count = existing_document[2]

            if existing_file_hash == file_hash:

                print(
                    f"[Indexer] "
                    f"Le document {filename} existe déjà "
                    f"avec le même contenu."
                )

                update_indexing_progress(
                    filename=filename,
                    progress=100,
                    status="completed",
                    stage="completed",
                    details=(
                        f"Document déjà indexé. "
                        f"{existing_chunk_count} chunks conservés."
                    )
                )

                generation_progress[
                    filename
                ]["status"] = "generating"

                print(
                    f"[Indexer] "
                    f"Aucune réindexation nécessaire."
                )

                return {
                    "filename": filename,
                    "file": filename,
                    "chunk_count": existing_chunk_count,
                    "document_id": existing_document_id,
                    "already_indexed": True,
                    "content_changed": False
                }

            print(
                f"[Indexer] "
                f"Le document {filename} existe déjà "
                f"mais son contenu a changé."
            )

            content_changed = True

        else:

            print(
                f"[Indexer] "
                f"Nouveau document : {filename}"
            )

            content_changed = False

        task_manager.start_pdf_operation()

        try:

            update_indexing_progress(
                filename=filename,
                progress=15,
                status="indexing",
                stage="pdf",
                details="Lecture du PDF..."
            )

            documents = load_pdf(
                file_path
            )

            update_indexing_progress(
                filename=filename,
                progress=20,
                status="indexing",
                stage="chunks",
                details="Découpage du document en chunks..."
            )

            chunks = split_documents(
                documents
            )

            print(
                f"[Indexer] "
                f"{len(chunks)} chunks générés "
                f"pour {filename}"
            )

            if not chunks:

                raise ValueError(
                    "Aucun chunk n'a été généré à partir du PDF."
                )

            texts = [
                chunk.page_content
                for chunk in chunks
            ]

            vectors = []

            total_texts = len(texts)

            update_indexing_progress(
                filename=filename,
                progress=25,
                status="indexing",
                stage="embeddings",
                details=(
                    f"Préparation des embeddings : "
                    f"0/{total_texts}"
                )
            )

            print(
                f"[Indexer] "
                f"Génération des embeddings "
                f"pour {filename}..."
            )

            for batch_start in range(
                0,
                total_texts,
                EMBEDDING_BATCH_SIZE
            ):

                task_manager.wait_for_pdf_permission()

                batch_end = min(
                    batch_start + EMBEDDING_BATCH_SIZE,
                    total_texts
                )

                batch_texts = texts[
                    batch_start:batch_end
                ]

                print(
                    f"[Indexer] "
                    f"Embeddings : "
                    f"{batch_start + 1}-{batch_end}/"
                    f"{total_texts}"
                )

                batch_vectors = (
                    embeddings_model.embed_documents(
                        batch_texts
                    )
                )

                if not batch_vectors:

                    raise ValueError(
                        f"Aucun embedding généré "
                        f"pour le lot "
                        f"{batch_start + 1}-{batch_end}."
                    )

                if len(batch_vectors) != len(
                    batch_texts
                ):

                    raise ValueError(
                        "Le nombre d'embeddings du lot "
                        "ne correspond pas au nombre de "
                        "textes envoyés."
                    )

                vectors.extend(
                    batch_vectors
                )

                embedding_progress = 25

                if total_texts > 0:

                    embedding_progress = (
                        25
                        + int(
                            (
                                batch_end
                                / total_texts
                            )
                            * 45
                        )
                    )

                update_indexing_progress(
                    filename=filename,
                    progress=min(
                        70,
                        embedding_progress
                    ),
                    status="indexing",
                    stage="embeddings",
                    details=(
                        f"Embeddings : "
                        f"{batch_end}/{total_texts}"
                    )
                )

            if not vectors:

                raise ValueError(
                    "Aucun embedding n'a été généré."
                )

            if len(vectors) != len(chunks):

                raise ValueError(
                    "Le nombre total d'embeddings "
                    "ne correspond pas au nombre de chunks."
                )

            print(
                f"[Indexer] "
                f"{len(vectors)} embeddings générés "
                f"pour {filename}"
            )

            update_indexing_progress(
                filename=filename,
                progress=70,
                status="indexing",
                stage="chroma",
                details="Préparation de ChromaDB..."
            )

            task_manager.wait_for_pdf_permission()

            if content_changed:

                print(
                    f"[Indexer] "
                    f"Suppression de l'ancien index ChromaDB "
                    f"pour {filename}..."
                )

                try:

                    chroma_deleted = delete_file(
                        filename
                    )

                    print(
                        f"[Indexer] "
                        f"{chroma_deleted} anciens chunks "
                        f"supprimés de ChromaDB."
                    )

                except Exception as error:

                    print(
                        f"[Indexer] "
                        f"Erreur suppression ancien index "
                        f"ChromaDB pour {filename} : {error}"
                    )

                    raise

            task_manager.wait_for_pdf_permission()

            add_chunks(
                chunks=chunks,
                vectors=vectors,
                file_name=filename
            )

            print(
                f"[Indexer] "
                f"Indexation ChromaDB terminée : {filename}"
            )

            update_indexing_progress(
                filename=filename,
                progress=85,
                status="indexing",
                stage="postgresql",
                details="Enregistrement du document en base..."
            )

            task_manager.wait_for_pdf_permission()

            connection = get_connection()

            try:

                with connection.cursor() as cursor:

                    cursor.execute(
                        """
                        SELECT id
                        FROM documents
                        WHERE file_name = %s
                        """,
                        (filename,)
                    )

                    existing_document = (
                        cursor.fetchone()
                    )

                    if existing_document is not None:

                        document_id = (
                            existing_document[0]
                        )

                        print(
                            f"[Indexer] "
                            f"Remplacement des anciens chunks "
                            f"du document id={document_id}..."
                        )

                        cursor.execute(
                            """
                            DELETE FROM document_chunks
                            WHERE document_id = %s
                            """,
                            (document_id,)
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
                                len(chunks),
                                document_id
                            )
                        )

                    else:

                        cursor.execute(
                            """
                            INSERT INTO documents (
                                file_name,
                                file_hash,
                                chunk_count
                            )
                            VALUES (
                                %s,
                                %s,
                                %s
                            )
                            RETURNING id
                            """,
                            (
                                filename,
                                file_hash,
                                len(chunks)
                            )
                        )

                        document_id = (
                            cursor.fetchone()[0]
                        )

                    for chunk_index in range(
                        len(chunks)
                    ):

                        chroma_id = (
                            f"{filename}_chunk_{chunk_index}"
                        )

                        cursor.execute(
                            """
                            INSERT INTO document_chunks (
                                document_id,
                                chunk_index,
                                chroma_id,
                                question_count,
                                question_limit
                            )
                            VALUES (
                                %s,
                                %s,
                                %s,
                                %s,
                                %s
                            )
                            """,
                            (
                                document_id,
                                chunk_index,
                                chroma_id,
                                0,
                                QUESTION_LIMIT_PER_CHUNK
                            )
                        )

                    connection.commit()

            except Exception:

                connection.rollback()

                raise

            finally:

                connection.close()

            update_indexing_progress(
                filename=filename,
                progress=100,
                status="completed",
                stage="completed",
                details=(
                    f"Indexation terminée : "
                    f"{len(chunks)} chunks enregistrés."
                )
            )

            generation_progress[
                filename
            ]["status"] = "generating"

            print(
                f"[Indexer] "
                f"Document enregistré en base : "
                f"id={document_id}"
            )

            print(
                f"[Indexer] "
                f"{len(chunks)} chunks enregistrés dans "
                f"document_chunks pour {filename}"
            )

            print(
                f"[Indexer] "
                f"Indexation terminée : {filename}"
            )

            return {
                "filename": filename,
                "file": filename,
                "chunk_count": len(chunks),
                "document_id": document_id,
                "already_indexed": False,
                "content_changed": content_changed
            }

        finally:

            task_manager.end_pdf_operation()

    except Exception as error:

        print(
            f"[Indexer] "
            f"Erreur indexation {filename} : {error}"
        )

        if filename not in generation_progress:
            initialize_progress(
                filename
            )

        update_indexing_progress(
            filename=filename,
            progress=generation_progress[
                filename
            ].get(
                "indexing_progress",
                0
            ),
            status="error",
            stage="error",
            details=str(error)
        )

        generation_progress[
            filename
        ]["status"] = "error"

        raise