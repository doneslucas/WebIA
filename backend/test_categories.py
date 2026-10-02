from app.services.category_classifier import (
    detect_document_categories,
    classify_chunk,
)


def main():
    chunks = [
        """
        AES-256 est un algorithme de chiffrement symétrique largement utilisé.
        Il utilise une clé de 256 bits et permet de protéger la confidentialité
        des données contre les accès non autorisés.
        """,
        """
        L'authentification permet de vérifier l'identité d'un utilisateur
        avant de lui accorder l'accès à une ressource.
        """,
    ]

    print("=== Détection des catégories du document ===")

    categories = detect_document_categories(chunks)

    for category in categories:
        print(
            f"- {category['id']} : "
            f"{category['name']} "
            f"({category['family']})"
        )

    print()
    print("=== Classification des chunks ===")

    for index, chunk in enumerate(chunks, start=1):
        category = classify_chunk(chunk, categories)

        print(
            f"Chunk {index} : "
            f"{category['id']} - "
            f"{category['name']}"
        )


if __name__ == "__main__":
    main()