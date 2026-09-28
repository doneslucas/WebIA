import json
import os

from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings, OllamaLLM

from app.services.chroma import search_chunks


load_dotenv()


OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "localhost"
)

OLLAMA_PORT = os.getenv(
    "OLLAMA_PORT",
    "11434"
)

OLLAMA_BASE_URL = (
    f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
)


embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=OLLAMA_BASE_URL
)


llm = OllamaLLM(
    model="qwen2.5:7b",
    base_url=OLLAMA_BASE_URL,
    num_predict=250
)


def ask_rag(question: str):

    # --------------------------------------------------------
    # 1. Transformation de la question en vecteur
    # --------------------------------------------------------

    query_vector = embeddings.embed_query(
        question
    )

    # --------------------------------------------------------
    # 2. Recherche des chunks les plus proches
    # --------------------------------------------------------

    results = search_chunks(
        query_vector,
        n_results=5
    )

    documents = results.get(
        "documents",
        [[]]
    )

    metadatas = results.get(
        "metadatas",
        [[]]
    )

    chunks = (
        documents[0]
        if documents and documents[0]
        else []
    )

    chunk_metadatas = (
        metadatas[0]
        if metadatas and metadatas[0]
        else []
    )

    # --------------------------------------------------------
    # 3. Vérification qu'il existe bien du contenu
    # --------------------------------------------------------

    if not chunks:

        return {
            "answer": (
                "Je ne peux pas répondre à cette question "
                "à partir des documents fournis."
            ),
            "sources": []
        }

    # --------------------------------------------------------
    # 4. Construction du contexte
    # --------------------------------------------------------

    context = "\n\n".join(
        chunks
    )

    # --------------------------------------------------------
    # 5. Prompt RAG
    # --------------------------------------------------------

    prompt = f"""
Tu es un assistant spécialisé en cybersécurité.

Tu dois répondre à la question UNIQUEMENT à partir
du contenu des documents fourni dans CONTEXTE.

CONTEXTE :
{context}

QUESTION :
{question}

RÈGLES ABSOLUES :

1. Utilise uniquement les informations présentes dans CONTEXTE.

2. Si CONTEXTE contient suffisamment d'informations
   pour répondre à la question, réponds normalement.

3. Si CONTEXTE ne contient pas la réponse, ou si les
   informations sont insuffisantes pour répondre de
   manière fiable, réponds exactement :

Je ne peux pas répondre à cette question à partir des documents fournis.

4. Dans ce dernier cas, n'invente aucune information.

5. Ne déduis pas une réponse qui n'est pas justifiable
   par CONTEXTE.

6. Ne donne pas de connaissances générales extérieures
   aux documents.

Réponds uniquement avec la réponse finale destinée à
l'utilisateur.
"""

    # --------------------------------------------------------
    # 6. Génération de la réponse
    # --------------------------------------------------------

    response = llm.invoke(
        prompt
    )

    answer = str(
        response
    ).strip()

    # --------------------------------------------------------
    # 7. Détection d'une absence de réponse dans les documents
    # --------------------------------------------------------

    no_answer_message = (
        "Je ne peux pas répondre à cette question "
        "à partir des documents fournis."
    )

    normalized_answer = (
        " ".join(
            answer.lower().split()
        )
    )

    normalized_no_answer = (
        " ".join(
            no_answer_message.lower().split()
        )
    )

    if (
        normalized_answer
        == normalized_no_answer
    ):

        return {
            "answer": no_answer_message,
            "sources": []
        }

    # --------------------------------------------------------
    # 8. Les sources ne sont retournées que si une réponse
    #    a réellement été trouvée dans les documents
    # --------------------------------------------------------

    sources = []

    for metadata in chunk_metadatas:

        if not metadata:
            continue

        sources.append(
            {
                "file": metadata.get(
                    "source"
                ),
                "page": metadata.get(
                    "page"
                )
            }
        )

    # --------------------------------------------------------
    # 9. Réponse finale
    # --------------------------------------------------------

    return {
        "answer": answer,
        "sources": sources
    }