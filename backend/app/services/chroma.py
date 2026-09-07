import chromadb


client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = client.get_or_create_collection(
    name="documents"
)

def add_chunks(chunks, vectors):

    collection.add(
        ids=[
            f"chunk_{i}"
            for i in range(len(chunks))
        ],

        documents=[
            chunk.page_content
            for chunk in chunks
        ],

        embeddings=vectors,

        metadatas=[
            chunk.metadata
            for chunk in chunks
        ]
    )

def search_chunks(query_vector, n_results=3):

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results
    )

    return results