import os

from app.services.indexer import index_pdf


DOCUMENTS_DIR = "documents"


def main():
    if not os.path.exists(DOCUMENTS_DIR):
        print("Le dossier documents n'existe pas.")
        return

    pdf_files = [
        file
        for file in os.listdir(DOCUMENTS_DIR)
        if file.lower().endswith(".pdf")
    ]

    if not pdf_files:
        print("Aucun PDF trouvé.")
        return

    print(f"{len(pdf_files)} PDF trouvé(s).\n")

    for file in pdf_files:
        file_path = os.path.join(
            DOCUMENTS_DIR,
            file
        )

        try:
            result = index_pdf(file_path)

            print(
                f"✓ {result['file']} "
                f"({result['chunks']} chunks)\n"
            )

        except Exception as error:
            print(
                f"✗ Erreur avec {file} : {error}\n"
            )


if __name__ == "__main__":
    main()