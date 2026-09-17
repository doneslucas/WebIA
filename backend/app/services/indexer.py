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
# PROGRESSION DES GÉNÉRATIONS
# ============================================================

generation_progress = {}


def get_generation_progress(
    filename: str
):
    """
    Retourne la progression actuelle de la génération
    des questions pour un document.
    """

    progress = generation_progress.get(
        filename
    )

    if progress is None:

        return {
            "document": filename,
            "status": "not_started",
            "global_progress": 0,

            "easy": {
                "status": "pending",
                "current": 0,
                "target": QUESTION_BANK_TARGET,
                "progress": 0
            },

            "medium": {
                "status": "pending",
                "current": 0,
                "target": QUESTION_BANK_TARGET,
                "progress": 0
            },

            "hard": {
                "status": "pending",
                "current": 0,
                "target": QUESTION_BANK_TARGET,
                "progress": 0
            }
        }

    return progress


def update_generation_progress(
    filename: str,
    difficulty: str,
    current: int,
    target: int,
    status: str
):
    """
    Met à jour la progression d'une difficulté.
    """

    if filename not in generation_progress:

        generation_progress[filename] = {
            "document": filename,
            "status": "generating",
            "global_progress": 0
        }

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

    progress["global_progress"] = (
        global_progress
    )


def initialize_generation_progress(
    filename: str
):
    """
    Initialise la progression avant de commencer
    la génération des trois banques.
    """

    generation_progress[
        filename
    ] = {
        "document": filename,
        "status": "generating",
        "global_progress": 0
    }

    for difficulty in QUIZ_DIFFICULTIES:

        generation_progress[
            filename
        ][difficulty] = {
            "status": "pending",
            "current": 0,
            "target": QUESTION_BANK_TARGET,
            "progress": 0
        }


# ============================================================
# GÉNÉRATION DES BANQUES DE QUESTIONS
# ============================================================

def generate_document_question_banks(
    filename: str
):
    """
    Génère les trois banques de questions
    en arrière-plan.

    Une banque est indépendante des autres.

    Si une banque contient déjà 50 questions,
    generate_questions_for_bank() ne génère rien
    pour cette difficulté.

    Si une banque est incomplète, seules les questions
    manquantes sont générées.
    """

    initialize_generation_progress(
        filename
    )

    try:

        for difficulty in QUIZ_DIFFICULTIES:

            current_before_generation = count_questions(
                filename,
                difficulty
            )

            # ------------------------------------------------
            # Banque déjà complète
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Banque incomplète
            # ------------------------------------------------

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

        generation_progress[
            filename
        ]["status"] = "error"


# ============================================================
# GESTION DES DOCUMENTS
# ============================================================

def get_all_documents():
    """
    Retourne tous les documents enregistrés en base.
    """

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
    """
    Supprime complètement un document.
    """

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

            # ------------------------------------------------
            # Suppression des chunks
            #
            # Les quiz_questions associés sont supprimés
            # automatiquement grâce à ON DELETE CASCADE.
            #
            # Les quiz_attempt_questions associés sont ensuite
            # supprimés automatiquement eux aussi.
            # ------------------------------------------------

            cursor.execute(
                """
                DELETE FROM document_chunks
                WHERE document_id = %s
                """,
                (document_id,)
            )

            # ------------------------------------------------
            # Suppression du document
            # ------------------------------------------------

            cursor.execute(
                """
                DELETE FROM documents
                WHERE id = %s
                """,
                (document_id,)
            )

            connection.commit()

        # ----------------------------------------------------
        # Suppression ChromaDB
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Suppression du PDF
        # ----------------------------------------------------

        file_deleted = False

        if document_path.exists():

            document_path.unlink()

            file_deleted = True

        # ----------------------------------------------------
        # Suppression de la progression
        # ----------------------------------------------------

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
    """
    Calcule le SHA-256 du fichier PDF.

    Le hash permet de déterminer si un PDF déjà enregistré
    possède exactement le même contenu que celui importé.
    """

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
    """
    Recherche un document existant en base.

    Retourne :
        (document_id, file_hash, chunk_count)

    ou None si le document n'existe pas.
    """

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
    """
    Indexe un PDF.

    Comportement :

    1. calcul du hash du PDF
    2. vérification de l'existence du document
    3. si le document existe avec le même hash :
       - aucune réindexation
       - aucun chunk supprimé
       - aucune question supprimée
       - aucune génération déclenchée ici
    4. si le document est nouveau ou modifié :
       - lecture du PDF
       - découpage en chunks
       - génération des embeddings par lots
       - remplacement de l'index ChromaDB si nécessaire
       - remplacement des anciens chunks PostgreSQL
       - création des nouveaux chunks
    5. la génération des banques de questions
       est lancée séparément en arrière-plan
       depuis la route documents.py.
    """

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

    # --------------------------------------------------------
    # Hash du fichier
    #
    # IMPORTANT :
    # On calcule le hash AVANT toute réindexation.
    # Cela permet de sortir immédiatement si le PDF
    # est déjà présent et strictement identique.
    # --------------------------------------------------------

    file_hash = calculate_file_hash(
        file_path
    )

    print(
        f"[Indexer] "
        f"Hash SHA-256 calculé pour {filename} : "
        f"{file_hash}"
    )

    # --------------------------------------------------------
    # Vérification d'un document existant
    # --------------------------------------------------------

    existing_document = get_existing_document(
        filename
    )

    if existing_document is not None:

        existing_document_id = existing_document[0]
        existing_file_hash = existing_document[1]
        existing_chunk_count = existing_document[2]

        # ----------------------------------------------------
        # Même PDF déjà indexé
        # ----------------------------------------------------

        if existing_file_hash == file_hash:

            print(
                f"[Indexer] "
                f"Le document {filename} existe déjà "
                f"avec le même contenu."
            )

            print(
                f"[Indexer] "
                f"Aucune réindexation nécessaire."
            )

            print(
                f"[Indexer] "
                f"Chunks conservés : "
                f"{existing_chunk_count}"
            )

            return {
                "filename": filename,
                "chunk_count": existing_chunk_count,
                "document_id": existing_document_id,
                "already_indexed": True,
                "content_changed": False
            }

        # ----------------------------------------------------
        # Même nom mais contenu différent
        # ----------------------------------------------------

        print(
            f"[Indexer] "
            f"Le document {filename} existe déjà "
            f"mais son contenu a changé."
        )

        print(
            f"[Indexer] "
            f"Une nouvelle indexation va être effectuée."
        )

        content_changed = True

    else:

        print(
            f"[Indexer] "
            f"Nouveau document : {filename}"
        )

        content_changed = False

    # --------------------------------------------------------
    # Lecture du PDF
    # --------------------------------------------------------

    documents = load_pdf(
        file_path
    )

    # --------------------------------------------------------
    # Découpage
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Embeddings
    # --------------------------------------------------------

    print(
        f"[Indexer] "
        f"Génération des embeddings "
        f"pour {filename}..."
    )

    texts = [
        chunk.page_content
        for chunk in chunks
    ]

    vectors = []

    total_texts = len(texts)

    for batch_start in range(
        0,
        total_texts,
        EMBEDDING_BATCH_SIZE
    ):

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

    # --------------------------------------------------------
    # ChromaDB
    #
    # Si le document existait avec un contenu différent,
    # les anciens vecteurs doivent être supprimés avant
    # d'ajouter les nouveaux vecteurs ayant les mêmes IDs.
    # --------------------------------------------------------

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

    add_chunks(
        chunks=chunks,
        vectors=vectors,
        file_name=filename
    )

    print(
        f"[Indexer] "
        f"Indexation ChromaDB terminée : {filename}"
    )

    # --------------------------------------------------------
    # PostgreSQL
    # --------------------------------------------------------

    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            # ------------------------------------------------
            # Vérification document existant
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Document existant :
            # remplacement de son contenu
            #
            # La suppression des chunks supprime également
            # automatiquement les anciennes questions grâce
            # aux contraintes ON DELETE CASCADE.
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Nouveau document
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Enregistrement des chunks
            # ------------------------------------------------

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
        "chunk_count": len(chunks),
        "document_id": document_id,
        "already_indexed": False,
        "content_changed": content_changed
    }