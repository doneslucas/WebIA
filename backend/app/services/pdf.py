from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def load_pdf(file_path: str):

    loader = PyMuPDFLoader(file_path)

    documents = loader.load()

    if not documents:
        raise ValueError("Impossible d'extraire le contenu du PDF.")

    total_characters = sum(
        len(document.page_content)
        for document in documents
    )

    if total_characters == 0:
        raise ValueError(
            "Le PDF a été ouvert, mais aucun texte n'a pu être extrait."
        )

    return documents


def split_documents(documents):

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    chunks = splitter.split_documents(documents)

    if not chunks:
        raise ValueError("Aucun chunk n'a pu être créé.")

    return chunks