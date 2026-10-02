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
    delete_file,
    is_file_indexed
)

from app.services.quiz import (
    generate_questions_for_bank,
    count_questions
)

from app.services.category_classifier import (
    classify_chunk
)

from app.services.categories import (
    get_all_categories
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


def get_generation_progress(
    filename: str
):
    progress = generation_progress.get(
        filename
    )

    if progress is None:
        return {
            "document": filename,
            "status": "not_started",

            "indexing":
                get_default_indexing_progress(),

            "indexing_progress": 0,

            "global_progress": 0,

            "easy":
                get_default_difficulty_progress(),

            "medium":
                get_default_difficulty_progress(),

            "hard":
                get_default_difficulty_progress()
        }

    return progress


def initialize_progress(
    filename: str
):
    generation_progress[filename] = {
        "document": filename,

        "status": "indexing",

        "indexing": {
            "status": "indexing",
            "progress": 0,
            "stage": "starting",
            "details":
                "Préparation de l'import du document..."
        },

        "indexing_progress": 0,

        "global_progress": 0,

        "easy":
            get_default_difficulty_progress(),

        "medium":
            get_default_difficulty_progress(),

        "hard":
            get_default_difficulty_progress()
    }


def update_indexing_progress(
    filename: str,
    progress: int,
    status: str = "indexing",
    stage: str = "",
    details: str = ""
):
    if filename not in generation_progress:
        initialize_progress(
            filename
        )

    progress = max(
        0,
        min(
            100,
            int(progress)
        )
    )

    generation_progress[
        filename
    ]["indexing"] = {
        "status": status,
        "progress": progress,
        "stage": stage,
        "details": details
    }

    generation_progress[
        filename
    ]["indexing_progress"] = progress


def update_generation_progress(
    filename: str,
    difficulty: str,
    current: int,
    target: int,
    status: str
):
    if filename not in generation_progress:
        initialize_progress(
            filename
        )

    progress = generation_progress[
        filename
    ]

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

    progress[
        "global_progress"
    ] = global_progress


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
                "details":
                    "Indexation du document terminée."
            },

            "indexing_progress": 100,

            "global_progress": 0,

            "easy":
                get_default_difficulty_progress(),

            "medium":
                get_default_difficulty_progress(),

            "hard":
                get_default_difficulty_progress()
        }

        return

    progress = generation_progress[
        filename
    ]

    progress["status"] = "generating"

    progress["indexing"] = {
        "status": "completed",
        "progress": 100,
        "stage": "completed",
        "details":
            "Indexation du document terminée."
    }

    progress[
        "indexing_progress"
    ] = 100

    for difficulty in QUIZ_DIFFICULTIES:

        progress[difficulty] = {
            "status": "pending",
            "current": 0,
            "target": QUESTION_BANK_TARGET,
            "progress": 0
        }

    progress[
        "global_progress"
    ] = 0


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

            current_before_generation = (
                count_questions(
                    filename,
                    difficulty
                )
            )

            if (
                current_before_generation
                >= QUESTION_BANK_TARGET
            ):

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
            lambda: file.read(
                1024 * 1024
            ),
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


def get_existing_document_by_hash(
    file_hash: str
):

    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    file_name,
                    file_hash,
                    chunk_count
                FROM documents
                WHERE file_hash = %s
                """,
                (file_hash,)
            )

            return cursor.fetchone()

    finally:

        connection.close()


def delete_duplicate_file(
    file_path: str,
    requested_filename: str,
    canonical_filename: str
):

    file_path_object = Path(
        file_path
    )

    if not file_path_object.exists():

        print(
            f"[Indexer] "
            f"Le doublon {requested_filename} "
            f"n'existe déjà plus sur le disque."
        )

        return False

    if (
        requested_filename
        == canonical_filename
    ):

        print(
            f"[Indexer] "
            f"Sécurité : le fichier demandé correspond "
            f"au document canonique. Suppression annulée."
        )

        return False

    try:

        file_path_object.unlink()

        print(
            f"[Indexer] "
            f"Doublon supprimé physiquement : "
            f"{requested_filename}"
        )

        print(
            f"[Indexer] "
            f"Document canonique conservé : "
            f"{canonical_filename}"
        )

        return True

    except Exception as error:

        print(
            f"[Indexer] "
            f"Impossible de supprimer le doublon "
            f"{requested_filename} : {error}"
        )

        raise


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

    requested_filename = filename

    print(
        f"[Indexer] "
        f"Début de l'import : "
        f"{requested_filename}"
    )

    initialize_progress(
        requested_filename
    )

    update_indexing_progress(
        filename=requested_filename,
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
            f"Hash SHA-256 calculé pour "
            f"{requested_filename} : "
            f"{file_hash}"
        )

        update_indexing_progress(
            filename=requested_filename,
            progress=10,
            status="indexing",
            stage="verification",
            details=(
                "Vérification de PostgreSQL "
                "et ChromaDB..."
            )
        )

        # ====================================================
        # RECHERCHE PAR NOM
        # ====================================================

        existing_document = (
            get_existing_document(
                requested_filename
            )
        )

        # ====================================================
        # RECHERCHE PAR HASH
        # ====================================================

        existing_document_by_hash = (
            get_existing_document_by_hash(
                file_hash
            )
        )

        content_changed = True

        # ====================================================
        # HASH DÉJÀ PRÉSENT SOUS UN AUTRE NOM
        # ====================================================

        if (
            existing_document_by_hash is not None
            and existing_document_by_hash[1]
            != requested_filename
        ):

            canonical_document_id = (
                existing_document_by_hash[0]
            )

            canonical_filename = (
                existing_document_by_hash[1]
            )

            canonical_chunk_count = (
                existing_document_by_hash[3]
            )

            print(
                "[Indexer] "
                "Contenu déjà présent dans PostgreSQL."
            )

            print(
                f"[Indexer] "
                f"Nom demandé : "
                f"{requested_filename}"
            )

            print(
                f"[Indexer] "
                f"Nom canonique : "
                f"{canonical_filename}"
            )

            print(
                "[Indexer] "
                "Les deux fichiers possèdent le même "
                "hash SHA-256."
            )

            chroma_indexed = (
                is_file_indexed(
                    canonical_filename
                )
            )

            if chroma_indexed:

                print(
                    "[Indexer] "
                    f"PostgreSQL ✓ | ChromaDB ✓ : "
                    f"{canonical_filename}"
                )

                duplicate_file_deleted = (
                    delete_duplicate_file(
                        file_path=file_path,
                        requested_filename=requested_filename,
                        canonical_filename=canonical_filename
                    )
                )

                update_indexing_progress(
                    filename=requested_filename,
                    progress=100,
                    status="completed",
                    stage="completed",
                    details=(
                        "Doublon supprimé. "
                        "Contenu déjà indexé sous "
                        f"{canonical_filename}."
                    )
                )

                generation_progress[
                    requested_filename
                ]["status"] = "completed"

                generation_progress[
                    requested_filename
                ]["global_progress"] = 100

                return {
                    "filename":
                        canonical_filename,

                    "requested_filename":
                        requested_filename,

                    "file":
                        canonical_filename,

                    "chunk_count":
                        canonical_chunk_count,

                    "document_id":
                        canonical_document_id,

                    "already_indexed":
                        True,

                    "duplicate_content":
                        True,

                    "canonical_filename":
                        canonical_filename,

                    "content_changed":
                        False,

                    "duplicate_file_deleted":
                        duplicate_file_deleted
                }

            print(
                "[Indexer] "
                "PostgreSQL ✓ | ChromaDB ✗"
            )

            print(
                "[Indexer] "
                f"Le contenu existe déjà sous "
                f"{canonical_filename}, mais son "
                "index ChromaDB est absent."
            )

            filename = canonical_filename

            content_changed = True

        else:

            # =================================================
            # DOCUMENT EXISTANT PAR NOM
            # =================================================

            if existing_document is not None:

                existing_document_id = (
                    existing_document[0]
                )

                existing_file_hash = (
                    existing_document[1]
                )

                existing_chunk_count = (
                    existing_document[2]
                )

                # ---------------------------------------------
                # Même contenu
                # ---------------------------------------------

                if (
                    existing_file_hash
                    == file_hash
                ):

                    print(
                        "[Indexer] "
                        f"{requested_filename} existe dans "
                        "PostgreSQL avec le même contenu."
                    )

                    chroma_indexed = (
                        is_file_indexed(
                            requested_filename
                        )
                    )

                    if chroma_indexed:

                        update_indexing_progress(
                            filename=requested_filename,
                            progress=100,
                            status="completed",
                            stage="completed",
                            details=(
                                "Document déjà synchronisé. "
                                f"{existing_chunk_count} chunks."
                            )
                        )

                        generation_progress[
                            requested_filename
                        ]["status"] = "generating"

                        print(
                            "[Indexer] "
                            "PostgreSQL ✓ | ChromaDB ✓"
                        )

                        print(
                            "[Indexer] "
                            "Aucune réindexation nécessaire."
                        )

                        return {
                            "filename":
                                requested_filename,

                            "requested_filename":
                                requested_filename,

                            "file":
                                requested_filename,

                            "chunk_count":
                                existing_chunk_count,

                            "document_id":
                                existing_document_id,

                            "already_indexed":
                                True,

                            "duplicate_content":
                                False,

                            "canonical_filename":
                                requested_filename,

                            "content_changed":
                                False,

                            "duplicate_file_deleted":
                                False
                        }

                    print(
                        "[Indexer] "
                        "PostgreSQL ✓ | ChromaDB ✗"
                    )

                    print(
                        "[Indexer] "
                        f"Index ChromaDB absent pour "
                        f"{requested_filename}."
                    )

                    print(
                        "[Indexer] "
                        "Réindexation nécessaire."
                    )

                    filename = requested_filename

                    content_changed = True

                # ---------------------------------------------
                # Contenu différent
                # ---------------------------------------------

                else:

                    print(
                        "[Indexer] "
                        "PostgreSQL ✓ mais le hash a "
                        f"changé pour {requested_filename}."
                    )

                    hash_owner = (
                        get_existing_document_by_hash(
                            file_hash
                        )
                    )

                    if (
                        hash_owner is not None
                        and hash_owner[0]
                        != existing_document_id
                    ):

                        conflicting_filename = (
                            hash_owner[1]
                        )

                        duplicate_file_deleted = (
                            delete_duplicate_file(
                                file_path=file_path,
                                requested_filename=requested_filename,
                                canonical_filename=conflicting_filename
                            )
                        )

                        update_indexing_progress(
                            filename=requested_filename,
                            progress=100,
                            status="completed",
                            stage="completed",
                            details=(
                                "Doublon supprimé. "
                                "Document canonique : "
                                f"{conflicting_filename}."
                            )
                        )

                        generation_progress[
                            requested_filename
                        ]["status"] = "completed"

                        generation_progress[
                            requested_filename
                        ]["global_progress"] = 100

                        return {
                            "filename":
                                conflicting_filename,

                            "requested_filename":
                                requested_filename,

                            "file":
                                conflicting_filename,

                            "chunk_count":
                                hash_owner[2],

                            "document_id":
                                hash_owner[0],

                            "already_indexed":
                                True,

                            "duplicate_content":
                                True,

                            "canonical_filename":
                                conflicting_filename,

                            "content_changed":
                                False,

                            "duplicate_file_deleted":
                                duplicate_file_deleted
                        }

                    print(
                        "[Indexer] "
                        "Réindexation complète nécessaire."
                    )

                    filename = requested_filename

                    content_changed = True

            # =================================================
            # DOCUMENT ABSENT DE POSTGRESQL
            # =================================================

            else:

                print(
                    "[Indexer] "
                    f"{requested_filename} absent de PostgreSQL."
                )

                chroma_indexed = (
                    is_file_indexed(
                        requested_filename
                    )
                )

                if chroma_indexed:

                    print(
                        "[Indexer] "
                        "PostgreSQL ✗ | ChromaDB ✓"
                    )

                    print(
                        "[Indexer] "
                        f"Index ChromaDB trouvé pour "
                        f"{requested_filename}."
                    )

                    print(
                        "[Indexer] "
                        "Synchronisation PostgreSQL nécessaire."
                    )

                else:

                    print(
                        "[Indexer] "
                        "PostgreSQL ✗ | ChromaDB ✗"
                    )

                    print(
                        "[Indexer] "
                        f"Nouveau document : "
                        f"{requested_filename}"
                    )

                filename = requested_filename

                content_changed = True

        # ====================================================
        # OPÉRATION PDF
        # ====================================================

        task_manager.start_pdf_operation()

        try:

            # ------------------------------------------------
            # Lecture PDF
            # ------------------------------------------------

            update_indexing_progress(
                filename=requested_filename,
                progress=15,
                status="indexing",
                stage="pdf",
                details="Lecture du PDF..."
            )

            documents = load_pdf(
                file_path
            )

            # ------------------------------------------------
            # Découpage en chunks
            # ------------------------------------------------

            update_indexing_progress(
                filename=requested_filename,
                progress=20,
                status="indexing",
                stage="chunks",
                details=(
                    "Découpage du document "
                    "en chunks..."
                )
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
                    "Aucun chunk n'a été généré "
                    "à partir du PDF."
                )

            texts = [
                chunk.page_content
                for chunk in chunks
            ]

            # =================================================
            # CLASSIFICATION DES CHUNKS
            # =================================================
            #
            # Chaque chunk est classifié directement avec
            # les 50 catégories fixes.
            #
            # On n'utilise PLUS detect_document_categories()
            # ici.
            #
            # Cela évite le gros appel qui envoyait plusieurs
            # chunks dans une seule requête Qwen.
            # =================================================

            update_indexing_progress(
                filename=requested_filename,
                progress=22,
                status="indexing",
                stage="categories",
                details=(
                    "Classification des chunks : "
                    f"0/{len(chunks)}"
                )
            )

            task_manager.wait_for_pdf_permission()

            print(
                "[Indexer] "
                f"Classification des catégories pour "
                f"{filename}..."
            )

            allowed_categories = (
                get_all_categories()
            )

            if not allowed_categories:

                raise ValueError(
                    "Aucune catégorie de cybersécurité "
                    "n'est disponible."
                )

            chunk_categories = []

            document_category_ids = set()

            total_chunks = len(chunks)

            for chunk_index, chunk_text in enumerate(
                texts
            ):

                task_manager.wait_for_pdf_permission()

                chunk_number = (
                    chunk_index + 1
                )

                print(
                    "[Indexer] "
                    f"Classification du chunk "
                    f"{chunk_number}/{total_chunks}..."
                )

                category = classify_chunk(
                    chunk_text,
                    allowed_categories
                )

                chunk_categories.append(
                    category
                )

                document_category_ids.add(
                    category["id"]
                )

                category_progress = (
                    22
                    + int(
                        (
                            chunk_number
                            / total_chunks
                        )
                        * 8
                    )
                )

                update_indexing_progress(
                    filename=requested_filename,
                    progress=min(
                        30,
                        category_progress
                    ),
                    status="indexing",
                    stage="categories",
                    details=(
                        "Classification des chunks : "
                        f"{chunk_number}/"
                        f"{total_chunks}"
                    )
                )

                print(
                    "[Indexer] "
                    f"Chunk {chunk_number}/"
                    f"{total_chunks} → "
                    f"{category['name']}"
                )

            if (
                len(chunk_categories)
                != len(chunks)
            ):

                raise ValueError(
                    "Le nombre de catégories de chunks "
                    "ne correspond pas au nombre de chunks."
                )

            # ------------------------------------------------
            # Catégories réellement présentes
            # ------------------------------------------------

            document_categories = [
                category

                for category
                in allowed_categories

                if category["id"]
                in document_category_ids
            ]

            print(
                "[Indexer] "
                f"{len(document_categories)} catégories "
                f"détectées pour {filename} :"
            )

            for category in document_categories:

                print(
                    "[Indexer] "
                    f"- {category['id']} : "
                    f"{category['name']} "
                    f"({category['family']})"
                )

            # =================================================
            # EMBEDDINGS
            # =================================================

            vectors = []

            total_texts = len(texts)

            update_indexing_progress(
                filename=requested_filename,
                progress=30,
                status="indexing",
                stage="embeddings",
                details=(
                    "Préparation des embeddings : "
                    f"0/{total_texts}"
                )
            )

            print(
                "[Indexer] "
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
                    batch_start
                    + EMBEDDING_BATCH_SIZE,
                    total_texts
                )

                batch_texts = texts[
                    batch_start:batch_end
                ]

                print(
                    "[Indexer] "
                    f"Embeddings : "
                    f"{batch_start + 1}-"
                    f"{batch_end}/"
                    f"{total_texts}"
                )

                batch_vectors = (
                    embeddings_model.embed_documents(
                        batch_texts
                    )
                )

                if not batch_vectors:

                    raise ValueError(
                        "Aucun embedding généré "
                        f"pour le lot "
                        f"{batch_start + 1}-"
                        f"{batch_end}."
                    )

                if (
                    len(batch_vectors)
                    != len(batch_texts)
                ):

                    raise ValueError(
                        "Le nombre d'embeddings du lot "
                        "ne correspond pas au nombre de "
                        "textes envoyés."
                    )

                vectors.extend(
                    batch_vectors
                )

                embedding_progress = 30

                if total_texts > 0:

                    embedding_progress = (
                        30
                        + int(
                            (
                                batch_end
                                / total_texts
                            )
                            * 40
                        )
                    )

                update_indexing_progress(
                    filename=requested_filename,
                    progress=min(
                        70,
                        embedding_progress
                    ),
                    status="indexing",
                    stage="embeddings",
                    details=(
                        "Embeddings : "
                        f"{batch_end}/"
                        f"{total_texts}"
                    )
                )

            if not vectors:

                raise ValueError(
                    "Aucun embedding n'a été généré."
                )

            if (
                len(vectors)
                != len(chunks)
            ):

                raise ValueError(
                    "Le nombre total d'embeddings "
                    "ne correspond pas au nombre de chunks."
                )

            print(
                "[Indexer] "
                f"{len(vectors)} embeddings générés "
                f"pour {filename}"
            )

            # =================================================
            # CHROMADB
            # =================================================

            update_indexing_progress(
                filename=requested_filename,
                progress=70,
                status="indexing",
                stage="chroma",
                details="Préparation de ChromaDB..."
            )

            task_manager.wait_for_pdf_permission()

            if content_changed:

                print(
                    "[Indexer] "
                    f"Suppression de l'ancien index "
                    f"ChromaDB pour {filename}..."
                )

                try:

                    chroma_deleted = (
                        delete_file(
                            filename
                        )
                    )

                    print(
                        "[Indexer] "
                        f"{chroma_deleted} anciens chunks "
                        "supprimés de ChromaDB."
                    )

                except Exception as error:

                    print(
                        "[Indexer] "
                        "Erreur suppression ancien index "
                        f"ChromaDB pour {filename} : "
                        f"{error}"
                    )

                    raise

            task_manager.wait_for_pdf_permission()

            add_chunks(
                chunks=chunks,
                vectors=vectors,
                file_name=filename
            )

            print(
                "[Indexer] "
                f"Indexation ChromaDB terminée : "
                f"{filename}"
            )

            # =================================================
            # POSTGRESQL
            # =================================================

            update_indexing_progress(
                filename=requested_filename,
                progress=85,
                status="indexing",
                stage="postgresql",
                details=(
                    "Enregistrement du document "
                    "en base..."
                )
            )

            task_manager.wait_for_pdf_permission()

            connection = get_connection()

            duplicate_file_deleted = False

            try:

                with connection.cursor() as cursor:

                    # -----------------------------------------
                    # Recherche du document par nom
                    # -----------------------------------------

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
                            "[Indexer] "
                            "Remplacement des anciens "
                            f"chunks du document "
                            f"id={document_id}..."
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
                            DELETE FROM document_categories
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
                                created_at =
                                    CURRENT_TIMESTAMP
                            WHERE id = %s
                            """,
                            (
                                file_hash,
                                len(chunks),
                                document_id
                            )
                        )

                    else:

                        # -------------------------------------
                        # Sécurité supplémentaire :
                        # le hash peut avoir été créé entre
                        # les deux vérifications.
                        # -------------------------------------

                        cursor.execute(
                            """
                            SELECT
                                id,
                                file_name,
                                chunk_count
                            FROM documents
                            WHERE file_hash = %s
                            """,
                            (file_hash,)
                        )

                        hash_owner = (
                            cursor.fetchone()
                        )

                        if hash_owner is not None:

                            document_id = (
                                hash_owner[0]
                            )

                            canonical_filename = (
                                hash_owner[1]
                            )

                            print(
                                "[Indexer] "
                                "Le hash existe déjà sous "
                                f"{canonical_filename}."
                            )

                            filename = (
                                canonical_filename
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
                                DELETE FROM document_categories
                                WHERE document_id = %s
                                """,
                                (document_id,)
                            )

                            cursor.execute(
                                """
                                UPDATE documents
                                SET
                                    chunk_count = %s,
                                    created_at =
                                        CURRENT_TIMESTAMP
                                WHERE id = %s
                                """,
                                (
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

                    # -----------------------------------------
                    # Catégories du document
                    # -----------------------------------------

                    for category in (
                        document_categories
                    ):

                        cursor.execute(
                            """
                            INSERT INTO document_categories (
                                document_id,
                                category_id
                            )
                            VALUES (
                                %s,
                                %s
                            )
                            ON CONFLICT (
                                document_id,
                                category_id
                            )
                            DO NOTHING
                            """,
                            (
                                document_id,
                                category["id"]
                            )
                        )

                    print(
                        "[Indexer] "
                        f"{len(document_categories)} "
                        "catégories enregistrées "
                        "pour le document."
                    )

                    # -----------------------------------------
                    # Chunks + catégories
                    # -----------------------------------------

                    for chunk_index in range(
                        len(chunks)
                    ):

                        chroma_id = (
                            f"{filename}_chunk_"
                            f"{chunk_index}"
                        )

                        category = (
                            chunk_categories[
                                chunk_index
                            ]
                        )

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
                            VALUES (
                                %s,
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
                                QUESTION_LIMIT_PER_CHUNK,
                                category["id"]
                            )
                        )

                    connection.commit()

            except Exception:

                connection.rollback()

                raise

            finally:

                connection.close()

            # =================================================
            # SUPPRESSION DU DOUBLON PHYSIQUE
            # =================================================

            if (
                requested_filename
                != filename
                and file_hash
                == calculate_file_hash(
                    file_path
                )
            ):

                duplicate_file_deleted = (
                    delete_duplicate_file(
                        file_path=file_path,
                        requested_filename=
                            requested_filename,
                        canonical_filename=
                            filename
                    )
                )

            # =================================================
            # FIN INDEXATION
            # =================================================

            update_indexing_progress(
                filename=requested_filename,
                progress=100,
                status="completed",
                stage="completed",
                details=(
                    f"Indexation terminée : "
                    f"{len(chunks)} chunks enregistrés "
                    f"sous {filename}."
                    +
                    (
                        f" Doublon "
                        f"{requested_filename} supprimé."
                        if duplicate_file_deleted
                        else ""
                    )
                )
            )

            generation_progress[
                requested_filename
            ]["status"] = "generating"

            print(
                "[Indexer] "
                f"Document enregistré en base : "
                f"id={document_id}"
            )

            print(
                "[Indexer] "
                f"{len(chunks)} chunks enregistrés "
                "dans document_chunks pour "
                f"{filename}"
            )

            print(
                "[Indexer] "
                f"Indexation terminée : {filename}"
            )

            return {
                "filename":
                    filename,

                "requested_filename":
                    requested_filename,

                "file":
                    filename,

                "chunk_count":
                    len(chunks),

                "document_id":
                    document_id,

                "already_indexed":
                    False,

                "duplicate_content":
                    filename != requested_filename,

                "canonical_filename":
                    filename,

                "content_changed":
                    content_changed,

                "duplicate_file_deleted":
                    duplicate_file_deleted
            }

        finally:

            task_manager.end_pdf_operation()

    except Exception as error:

        print(
            "[Indexer] "
            f"Erreur indexation "
            f"{requested_filename} : "
            f"{error}"
        )

        if (
            requested_filename
            not in generation_progress
        ):

            initialize_progress(
                requested_filename
            )

        current_progress = (
            generation_progress[
                requested_filename
            ].get(
                "indexing_progress",
                0
            )
        )

        update_indexing_progress(
            filename=requested_filename,
            progress=current_progress,
            status="error",
            stage="error",
            details=str(error)
        )

        generation_progress[
            requested_filename
        ]["status"] = "error"

        raise