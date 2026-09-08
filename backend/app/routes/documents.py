from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.services.auth import verify_token
from app.services.indexer import index_pdf


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


BASE_DIR = Path(__file__).resolve().parents[2]
DOCUMENTS_DIR = BASE_DIR / "documents"

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 Mo


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    payload: dict = Depends(verify_token)
):
    # Vérification du rôle
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Accès refusé. Seuls les administrateurs peuvent importer des documents."
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Aucun fichier fourni."
        )

    filename = Path(file.filename).name

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Seuls les fichiers PDF sont acceptés."
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Le fichier est vide."
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Le fichier est trop volumineux. Taille maximale : 20 Mo."
        )

    DOCUMENTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = DOCUMENTS_DIR / filename

    try:
        with open(file_path, "wb") as destination:
            destination.write(content)

        result = index_pdf(str(file_path))

        print("RESULT =", result)

        return result

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du traitement du PDF : {error}"
        )