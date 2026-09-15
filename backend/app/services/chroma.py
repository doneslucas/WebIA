import chromadb


client = chromadb.PersistentClient(
    path="./chroma_db"
)


collection = client.get_or_create_collection(
    name="documents"
)


def add_chunks(
    chunks,
    vectors,
    file_name: str
):
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


def search_chunks(
    query_vector,
    n_results=3
):
    return collection.query(
        query_embeddings=[query_vector],
        n_results=n_results
    )


def get_file_chroma_ids(
    file_name: str
):
    results = collection.get(
        include=["metadatas"]
    )

    ids = results.get("ids", [])
    metadatas = results.get("metadatas", [])

    matching_ids = []

    for chroma_id, metadata in zip(
        ids,
        metadatas
    ):
        if not metadata:
            continue

        source = metadata.get(
            "source",
            ""
        )

        if (
            str(source).replace(
                "\\",
                "/"
            ).endswith(
                f"/{file_name}"
            )
        ):
            matching_ids.append(
                chroma_id
            )

    return matching_ids


def is_file_indexed(
    file_name: str
):
    return bool(
        get_file_chroma_ids(
            file_name
        )
    )


def get_file_hash(
    file_name: str
):
    chroma_ids = get_file_chroma_ids(
        file_name
    )

    if not chroma_ids:
        return None

    results = collection.get(
        ids=[chroma_ids[0]],
        include=["metadatas"]
    )

    metadatas = results.get(
        "metadatas",
        []
    )

    if not metadatas:
        return None

    return metadatas[0].get(
        "file_hash"
    )


def delete_file(
    file_name: str
):
    chroma_ids = get_file_chroma_ids(
        file_name
    )

    if not chroma_ids:
        return 0

    collection.delete(
        ids=chroma_ids
    )

    return len(chroma_ids)