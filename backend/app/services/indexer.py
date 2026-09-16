import os
import hashlib

from app.services.pdf import (
    load_pdf,
    split_documents
)

from app.services.chroma import (
    add_chunks,
    delete_file,
    is_file_indexed
)

from app.database.connection import (
    get_connection
)

from langchain_ollama import (
    OllamaEmbeddings
)


DOCUMENTS_DIR = "documents"

QUESTION_LIMIT_PER_CHUNK = 5

QUIZ_DIFFICULTIES = (
    "easy",
    "medium",
    "hard"
)

QUESTION_BANK_TARGET = 50


embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)


def calculate_file_hash(
    file_path: str
) -> str:

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
            sha256.update(block)

    return sha256.hexdigest()


def get_document_from_database(
    file_name: str
):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    file_hash,
                    chunk_count
                FROM documents
                WHERE file_name = %s
                """,
                (file_name,)
            )

            return cursor.fetchone()


def get_all_documents():

    with get_connection() as conn:
        with conn.cursor() as cursor:

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

    return [
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
        for row in rows
    ]


def delete_document_from_database(
    file_name: str
):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            cursor.execute(
                """
                DELETE FROM documents
                WHERE file_name = %s
                RETURNING id
                """,
                (file_name,)
            )

            result = cursor.fetchone()

        conn.commit()

    return result


def create_document(
    file_name: str,
    file_hash: str,
    chunk_count: int
):

    with get_connection() as conn:
        with conn.cursor() as cursor:

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
                    file_name,
                    file_hash,
                    chunk_count
                )
            )

            document_id = cursor.fetchone()[0]

        conn.commit()

    return document_id


def create_document_chunks(
    document_id: int,
    chunks,
    file_name: str
):

    with get_connection() as conn:
        with conn.cursor() as cursor:

            for index in range(
                len(chunks)
            ):

                chroma_id = (
                    f"{file_name}_chunk_{index}"
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
                        index,
                        chroma_id,
                        0,
                        QUESTION_LIMIT_PER_CHUNK
                    )
                )

        conn.commit()


def delete_document(
    file_name: str,
    documents_dir: str = DOCUMENTS_DIR
):

    file_name = os.path.basename(
        file_name
    )

    if not file_name.lower().endswith(
        ".pdf"
    ):
        raise ValueError(
            "Seuls les fichiers PDF peuvent être supprimés."
        )

    document = get_document_from_database(
        file_name
    )

    chroma_deleted = 0
    postgres_deleted = False
    file_deleted = False

    if is_file_indexed(
        file_name
    ):

        chroma_deleted = delete_file(
            file_name
        )

    if document is not None:

        deleted = delete_document_from_database(
            file_name
        )

        postgres_deleted = (
            deleted is not None
        )

    file_path = os.path.join(
        documents_dir,
        file_name
    )

    if os.path.exists(
        file_path
    ):

        os.remove(
            file_path
        )

        file_deleted = True

    if (
        not postgres_deleted
        and not file_deleted
        and chroma_deleted == 0
    ):
        raise ValueError(
            f"Document introuvable : {file_name}"
        )

    return {
        "file": file_name,
        "file_deleted": file_deleted,
        "postgres_deleted": postgres_deleted,
        "chroma_chunks_deleted": chroma_deleted
    }


def index_pdf(
    file_path: str
):

    print(
        f"Indexation de : {file_path}"
    )

    file_name = os.path.basename(
        file_path
    )

    file_hash = calculate_file_hash(
        file_path
    )

    print(
        f"  → Hash SHA-256 : {file_hash}"
    )

    existing_document = (
        get_document_from_database(
            file_name
        )
    )

    if existing_document is not None:

        existing_hash = (
            existing_document[1]
        )

        if existing_hash == file_hash:

            print(
                f"  → {file_name} est déjà indexé "
                "et n'a pas changé, ignoré."
            )

            return {
                "file": file_name,
                "chunks": existing_document[2],
                "skipped": True
            }

        print(
            f"  → {file_name} a été modifié, "
            "suppression de l'ancienne version."
        )

        if is_file_indexed(
            file_name
        ):

            deleted_chunks = delete_file(
                file_name
            )

            print(
                "  → Ancienne version supprimée "
                f"de ChromaDB ({deleted_chunks} chunks)"
            )

        delete_document_from_database(
            file_name
        )

        print(
            "  → Ancienne version supprimée "
            "de PostgreSQL"
        )

    documents = load_pdf(
        file_path
    )

    print(
        f"  → {len(documents)} page(s) extraite(s)"
    )

    chunks = split_documents(
        documents
    )

    if not chunks:
        raise ValueError(
            "Aucun chunk créé."
        )

    print(
        f"  → {len(chunks)} chunks créés"
    )

    document_id = create_document(
        file_name=file_name,
        file_hash=file_hash,
        chunk_count=len(chunks)
    )

    print(
        f"  → Document créé dans PostgreSQL "
        f"(id={document_id})"
    )

    create_document_chunks(
        document_id=document_id,
        chunks=chunks,
        file_name=file_name
    )

    print(
        f"  → {len(chunks)} chunks enregistrés "
        "dans PostgreSQL"
    )

    texts = [
        chunk.page_content
        for chunk in chunks
    ]

    vectors = embeddings.embed_documents(
        texts
    )

    print(
        f"  → {len(vectors)} embeddings créés"
    )

    for chunk in chunks:

        chunk.metadata[
            "file_hash"
        ] = file_hash

    add_chunks(
        chunks,
        vectors,
        file_name
    )

    print(
        "  → Chunks ajoutés à ChromaDB"
    )

    return {
        "file": file_name,
        "chunks": len(chunks),
        "skipped": False
    }


def generate_document_question_banks(
    document: str
):

    """
    Construit automatiquement les banques
    easy / medium / hard pour un document.

    Chaque difficulté vise 50 questions,
    dans la limite de la capacité réelle
    du document.
    """

    from app.services.quiz import (
        generate_questions_for_bank
    )

    print(
        "\n"
        "========================================\n"
        f"GÉNÉRATION DES BANQUES : {document}\n"
        "========================================"
    )

    results = {}

    for difficulty in QUIZ_DIFFICULTIES:

        try:

            print(
                "\n"
                f"[{difficulty.upper()}] "
                "Début de génération..."
            )

            generated_count = (
                generate_questions_for_bank(
                    document=document,
                    difficulty=difficulty,
                    target_count=QUESTION_BANK_TARGET
                )
            )

            results[difficulty] = {
                "questions": generated_count,
                "success": True
            }

            print(
                f"[{difficulty.upper()}] "
                f"Banque terminée : "
                f"{generated_count} questions"
            )

        except Exception as error:

            results[difficulty] = {
                "questions": 0,
                "success": False,
                "error": str(error)
            }

            print(
                f"[{difficulty.upper()}] "
                f"Erreur : {error}"
            )

    print(
        "\n"
        "========================================\n"
        f"BANKS TERMINÉES : {document}\n"
        f"{results}\n"
        "========================================\n"
    )

    return results


def index_all_documents():

    if not os.path.exists(
        DOCUMENTS_DIR
    ):

        print(
            "Le dossier documents n'existe pas."
        )

        return

    pdf_files = [
        file
        for file in os.listdir(
            DOCUMENTS_DIR
        )
        if file.lower().endswith(".pdf")
    ]

    if not pdf_files:

        print(
            "Aucun PDF trouvé."
        )

        return

    print(
        f"{len(pdf_files)} PDF trouvé(s).\n"
    )

    for file in pdf_files:

        file_path = os.path.join(
            DOCUMENTS_DIR,
            file
        )

        try:

            result = index_pdf(
                file_path
            )

            if result.get(
                "skipped"
            ):

                print(
                    f"✓ {result['file']} "
                    f"({result['chunks']} chunks "
                    "déjà indexés)\n"
                )

            else:

                print(
                    f"✓ {result['file']} "
                    f"({result['chunks']} chunks indexés)\n"
                )

        except Exception as error:

            print(
                f"✗ Erreur avec {file} : {error}\n"
            )


if __name__ == "__main__":
    index_all_documents()