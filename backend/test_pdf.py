from app.services.pdf import load_pdf, split_documents


pdf_path = "documents/test.pdf"

documents = load_pdf(pdf_path)

print(f"Nombre de pages : {len(documents)}")

chunks = split_documents(documents)

print(f"Nombre de chunks : {len(chunks)}")

for i, chunk in enumerate(chunks[:5]):
    print("\n" + "=" * 50)
    print(f"CHUNK {i + 1}")
    print("=" * 50)
    print(chunk.page_content)
    print("\nMETADATA :")
    print(chunk.metadata)