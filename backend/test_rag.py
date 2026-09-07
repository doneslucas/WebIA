import time

from langchain_ollama import OllamaEmbeddings, OllamaLLM
from app.services.chroma import search_chunks


embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)

llm = OllamaLLM(
    model="llama3.2:1b",
    num_predict=150
)

question = "Comment reconnaître une attaque de phishing ?"


# --------------------------------------------------
# 1. Embedding de la question
# --------------------------------------------------

start = time.time()

query_vector = embeddings.embed_query(question)

print(f"Embedding : {time.time() - start:.2f} secondes")


# --------------------------------------------------
# 2. Recherche ChromaDB
# --------------------------------------------------

start = time.time()

results = search_chunks(
    query_vector,
    n_results=3
)

print(f"Recherche ChromaDB : {time.time() - start:.2f} secondes")


# --------------------------------------------------
# 3. Construction du contexte
# --------------------------------------------------

start = time.time()

chunks = results["documents"][0]
metadatas = results["metadatas"][0]

context = "\n\n".join(chunks)

print(f"Construction contexte : {time.time() - start:.2f} secondes")


# --------------------------------------------------
# 4. Génération avec le LLM
# --------------------------------------------------

prompt = f"""
Tu es un assistant spécialisé en cybersécurité.

Réponds uniquement à partir du contexte fourni.

Réponds de manière concise mais complète.
Va directement à l'essentiel.
N'ajoute aucune information qui n'est pas présente dans le contexte.
Ne répète pas les informations.

Contexte :
{context}

Question :
{question}

Réponse :
"""


start = time.time()

response = llm.invoke(prompt)

print(f"Génération LLM : {time.time() - start:.2f} secondes")


# --------------------------------------------------
# Résultat
# --------------------------------------------------

print("\n" + "=" * 50)
print("QUESTION")
print("=" * 50)

print(question)

print("\n" + "=" * 50)
print("RÉPONSE")
print("=" * 50)

print(response)

print("\n" + "=" * 50)
print("SOURCES UTILISÉES")
print("=" * 50)

for i, metadata in enumerate(metadatas):

    print(f"\nSource {i + 1}")

    print(f"Fichier : {metadata.get('source')}")
    print(f"Page : {metadata.get('page', 'inconnue')}")