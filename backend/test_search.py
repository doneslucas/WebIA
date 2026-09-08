from app.services.chroma import is_file_indexed

print(
    "test.pdf :",
    is_file_indexed("test.pdf")
)

print(
    "Le_Phishing.pdf :",
    is_file_indexed("Le_Phishing.pdf")
)

print(
    "inconnu.pdf :",
    is_file_indexed("inconnu.pdf")
)