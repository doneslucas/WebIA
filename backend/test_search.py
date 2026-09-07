from langchain_ollama import OllamaEmbeddings

from app.services.chroma import search_chunks


# Modèle d'embedding
embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)


# Question utilisateur
question = "Comment reconnaître une attaque de phishing ?"


# Transformer la question en vecteur
query_vector = embeddings.embed_query(question)


# Rechercher les chunks les plus proches
results = search_chunks(
    query_vector,
    n_results=3
)


# Afficher les résultats
for i, document in enumerate(results["documents"][0]):

    distance = results["distances"][0][i]

    print("\n" + "=" * 50)
    print(f"RESULTAT {i + 1}")
    print("=" * 50)

    print(f"Distance : {distance}")
    print("\nTexte :")
    print(document)