import chromadb


client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = client.get_or_create_collection(
    name="documents"
)

def add_chunks(chunks, vectors, file_name):
    collection.add(
        ids=[
            f"{file_name}_chunk_{i}"
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

def is_file_indexed(file_name):
    results = collection.get(
        where={"source": f"documents\\{file_name}"},
        include=["metadatas"]
    )

    return len(results["metadatas"]) > 0

def get_file_hash(file_name):
    results = collection.get(
        where={"source": f"documents\\{file_name}"},
        include=["metadatas"]
    )

    if not results["metadatas"]:
        return None

    return results["metadatas"][0].get("file_hash")

def delete_file(file_name):
    collection.delete(
        where={"source": f"documents\\{file_name}"}
    )