from langchain_ollama import OllamaEmbeddings, OllamaLLM

from app.services.chroma import search_chunks


# Modèle utilisé pour transformer les questions en vecteurs
embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)


# Modèle utilisé pour générer les réponses
llm = OllamaLLM(
    model="qwen2.5:7b",
    num_predict=250
)


def ask_rag(question: str):

    # ---------------------------------------------
    # 1. Transformer la question en vecteur
    # ---------------------------------------------

    query_vector = embeddings.embed_query(question)


    # ---------------------------------------------
    # 2. Rechercher les chunks pertinents
    # ---------------------------------------------

    results = search_chunks(
        query_vector,
        n_results=3
    )


    # ---------------------------------------------
    # 3. Récupérer les documents et leurs sources
    # ---------------------------------------------

    chunks = results["documents"][0]
    metadatas = results["metadatas"][0]


    # ---------------------------------------------
    # 4. Construire le contexte
    # ---------------------------------------------

    context = "\n\n".join(chunks)


    # ---------------------------------------------
    # 5. Construire le prompt
    # ---------------------------------------------

    prompt = f"""
Tu es un assistant spécialisé en cybersécurité.

Réponds uniquement à partir du contexte fourni.

Consignes :
- Réponds en français.
- Sois précis et concis.
- Réponds directement à la question.
- Donne uniquement les informations nécessaires.
- Ne fais pas d'introduction inutile.
- Ne répète pas les informations.
- Termine toujours ton explication avant la fin de ta réponse.
- N'invente aucune information absente du contexte.
- Si le contexte ne permet pas de répondre, dis-le clairement.

Contexte :
{context}

Question :
{question}

Réponse :
"""


    # ---------------------------------------------
    # 6. Générer la réponse
    # ---------------------------------------------

    response = llm.invoke(prompt)


    # ---------------------------------------------
    # 7. Préparer les sources
    # ---------------------------------------------

    sources = []

    for metadata in metadatas:

        source = {
            "file": metadata.get("source"),
            "page": metadata.get("page")
        }

        sources.append(source)


    # ---------------------------------------------
    # 8. Retourner réponse + sources
    # ---------------------------------------------

    return {
        "answer": response,
        "sources": sources
    }