import os
import hashlib

from app.services.pdf import load_pdf, split_documents
from app.services.chroma import (add_chunks, delete_file, get_file_hash, is_file_indexed)
from langchain_ollama import OllamaEmbeddings


embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)

def calculate_file_hash(file_path: str) -> str:
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()

def index_pdf(file_path: str):
    print(f"Indexation de : {file_path}")

    file_name = os.path.basename(file_path)
    file_hash = calculate_file_hash(file_path)

    print(f"  → Hash SHA-256 : {file_hash}")

    if is_file_indexed(file_name):

        existing_hash = get_file_hash(file_name)

        if existing_hash == file_hash:
            print(
                f"  → {file_name} est déjà indexé "
                "et n'a pas changé, ignoré."
            )

            return {
                "file": file_name,
                "chunks": 0,
                "skipped": True
            }

        print(
            f"  → {file_name} a été modifié, "
            "suppression de l'ancienne version."
        )

        delete_file(file_name)
    # 1. Charger le PDF
    documents = load_pdf(file_path)

    # 2. Découper en chunks
    chunks = split_documents(documents)

    if not chunks:
        raise ValueError("Aucun chunk créé.")

    print(f"  → {len(chunks)} chunks créés")

    # 3. Créer les embeddings
    texts = [
        chunk.page_content
        for chunk in chunks
    ]

    vectors = embeddings.embed_documents(texts)

    print(f"  → {len(vectors)} embeddings créés")

    # 4. Ajouter les chunks à ChromaDB
    file_name = os.path.basename(file_path)
    file_hash = calculate_file_hash(file_path)

    print(f"  → Hash SHA-256 : {file_hash}")

    for chunk in chunks:
        chunk.metadata["file_hash"] = file_hash

    add_chunks(
        chunks,
        vectors,
        file_name
    )

    print("  → Ajouté à ChromaDB")

    return {
        "file": file_name,
        "chunks": len(chunks)
    }