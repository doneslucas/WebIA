
import os
import time

from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings, OllamaLLM

from app.services.chroma import search_chunks

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

RAG_NUM_PREDICT = 200
RAG_N_RESULTS = 2
RAG_MAX_CHARS_PER_CHUNK = 1500

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=OLLAMA_BASE_URL,
)

llm = OllamaLLM(
    model="qwen2.5:3b",
    base_url=OLLAMA_BASE_URL,
    num_predict=RAG_NUM_PREDICT,
    num_ctx=2048,
    temperature=0.1,
    keep_alive="10m",
)


def ask_rag(question: str):
    total_start = time.perf_counter()

    start = time.perf_counter()
    query_vector = embeddings.embed_query(question)
    embedding_time = time.perf_counter() - start

    start = time.perf_counter()
    results = search_chunks(query_vector, n_results=RAG_N_RESULTS)
    search_time = time.perf_counter() - start

    documents = results.get("documents", [[]])
    metadatas = results.get("metadatas", [[]])

    chunks = documents[0] if documents and documents[0] else []
    chunk_metadatas = metadatas[0] if metadatas and metadatas[0] else []

    no_answer_message = (
        "Je ne peux pas répondre à cette question "
        "à partir des documents fournis."
    )

    if not chunks:
        print(
            f"[RAG] embedding={embedding_time:.2f}s "
            f"recherche={search_time:.2f}s "
            f"total={time.perf_counter() - total_start:.2f}s"
        )
        return {"answer": no_answer_message, "sources": []}

    context_parts = [
        chunk[:RAG_MAX_CHARS_PER_CHUNK]
        for chunk in chunks
        if chunk
    ]
    context = "\n\n".join(context_parts)

    prompt = f"""Tu es un assistant spécialisé en cybersécurité.
Réponds uniquement avec les informations du CONTEXTE.
Si le contexte est insuffisant, réponds exactement :
{no_answer_message}

Réponse directe et concise : 2 à 3 phrases maximum.
N'invente aucune information.

CONTEXTE :
{context}

QUESTION :
{question}

RÉPONSE :
"""

    start = time.perf_counter()
    response = llm.invoke(prompt)
    generation_time = time.perf_counter() - start

    answer = str(response).strip()
    normalized_answer = " ".join(answer.lower().split())
    normalized_no_answer = " ".join(no_answer_message.lower().split())

    if normalized_answer == normalized_no_answer:
        answer = no_answer_message
        sources = []
    else:
        sources = []
        seen_sources = set()

        for metadata in chunk_metadatas:
            if not metadata:
                continue

            filename = metadata.get("source")
            page = metadata.get("page")

            if not filename:
                continue

            source_key = (filename, page)

            if source_key in seen_sources:
                continue

            seen_sources.add(source_key)
            sources.append({
                "file": filename,
                "page": page,
            })

    total_time = time.perf_counter() - total_start

    print(
        f"[RAG] embedding={embedding_time:.2f}s "
        f"recherche={search_time:.2f}s "
        f"generation={generation_time:.2f}s "
        f"total={total_time:.2f}s"
    )

    return {
        "answer": answer,
        "sources": sources,
    }
