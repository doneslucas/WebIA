import os
import re

import chromadb
from dotenv import load_dotenv

load_dotenv()

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

client = chromadb.HttpClient(
    host=CHROMA_HOST,
    port=CHROMA_PORT,
)

collection = client.get_or_create_collection(
    name="documents",
)


def _normalize_filename(file_name: str) -> str:
    """Normalise un nom de fichier provenant de Windows ou Linux."""
    normalized = str(file_name).replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", 1)[-1]


def add_chunks(chunks, vectors, file_name: str):
    """Ajoute les chunks avec les identifiants utilisés par PostgreSQL."""
    filename = _normalize_filename(file_name)

    if len(chunks) != len(vectors):
        raise ValueError(
            "Le nombre de chunks ne correspond pas au nombre d'embeddings."
        )

    if not chunks:
        raise ValueError("Aucun chunk à ajouter dans ChromaDB.")

    # upsert rend l'écriture idempotente si un précédent import a laissé
    # quelques IDs portant exactement le même nom. Les anciens chunks
    # surnuméraires restent retirés par delete_file() avant cette écriture.
    collection.upsert(
        ids=[f"{filename}_chunk_{i}" for i in range(len(chunks))],
        documents=[chunk.page_content for chunk in chunks],
        embeddings=vectors,
        metadatas=[chunk.metadata for chunk in chunks],
    )


def search_chunks(query_vector, n_results=3):
    return collection.query(
        query_embeddings=[query_vector],
        n_results=n_results,
    )


def get_file_chroma_ids(file_name: str):
    """
    Recherche les chunks d'un PDF à partir de leurs identifiants déterministes
    et de leur métadonnée source. Cela permet de retrouver des chunks dont la
    métadonnée source est absente ou stockée sous un chemin inattendu.
    """
    filename = _normalize_filename(file_name)

    results = collection.get(include=["metadatas"])
    ids = results.get("ids") or []
    metadatas = results.get("metadatas") or []

    matching_ids = []
    expected_id_pattern = re.compile(
        rf"{re.escape(filename)}_chunk_[0-9]+"
    )

    for index, chroma_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) else None

        # Les IDs sont ceux utilisés par indexer.py et document_chunks.chroma_id.
        id_matches = bool(expected_id_pattern.fullmatch(str(chroma_id)))

        source = ""
        if isinstance(metadata, dict):
            source = str(metadata.get("source") or "")

        normalized_source = source.replace("\\", "/").rstrip("/")
        source_matches = (
            normalized_source == filename
            or normalized_source.endswith("/" + filename)
        )

        if id_matches or source_matches:
            matching_ids.append(chroma_id)

    # Évite les doublons tout en conservant l'ordre.
    return list(dict.fromkeys(matching_ids))


def is_file_indexed(file_name: str):
    return bool(get_file_chroma_ids(file_name))


def get_file_hash(file_name: str):
    chroma_ids = get_file_chroma_ids(file_name)

    if not chroma_ids:
        return None

    results = collection.get(
        ids=[chroma_ids[0]],
        include=["metadatas"],
    )
    metadatas = results.get("metadatas") or []

    if not metadatas or not isinstance(metadatas[0], dict):
        return None

    return metadatas[0].get("file_hash")


def delete_file(file_name: str):
    """Supprime uniquement les chunks identifiés comme appartenant au PDF."""
    chroma_ids = get_file_chroma_ids(file_name)

    if not chroma_ids:
        return 0

    collection.delete(ids=chroma_ids)
    return len(chroma_ids)
