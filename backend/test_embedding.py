from app.services.pdf import load_pdf, split_documents
from langchain_ollama import OllamaEmbeddings


# Charger le PDF
pdf_path = "documents/test.pdf"

documents = load_pdf(pdf_path)

# Découper en chunks
chunks = split_documents(documents)

print(f"Nombre de chunks : {len(chunks)}")


# Charger le modèle d'embedding
embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)


# Générer un embedding pour chaque chunk
vectors = embeddings.embed_documents(
    [chunk.page_content for chunk in chunks]
)


print(f"Nombre de vecteurs : {len(vectors)}")
print(f"Dimension d'un vecteur : {len(vectors[0])}")