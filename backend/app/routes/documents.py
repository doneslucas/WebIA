from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile
)

from app.services.auth import verify_token

from app.services.indexer import (
    index_pdf,
    get_all_documents,
    delete_document
)


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


BASE_DIR = Path(__file__).resolve().parents[2]

DOCUMENTS_DIR = BASE_DIR / "documents"

MAX_FILE_SIZE = 20 * 1024 * 1024


def verify_admin(
    payload: dict
):
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail=(
                "Accès refusé. Seuls les administrateurs "
                "peuvent gérer les documents."
            )
        )


@router.get("")
def list_documents(
    payload: dict = Depends(verify_token)
):

    verify_admin(
        payload
    )

    try:

        return {
            "documents": get_all_documents()
        }

    except Exception as error:

        print(
            f"Erreur lors de la récupération "
            f"des documents : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Impossible de récupérer les documents."
        )


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    payload: dict = Depends(verify_token)
):

    verify_admin(
        payload
    )

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="Aucun fichier fourni."
        )

    filename = Path(
        file.filename
    ).name

    if not filename.lower().endswith(
        ".pdf"
    ):

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
            detail=(
                "Le fichier est trop volumineux. "
                "Taille maximale : 20 Mo."
            )
        )

    DOCUMENTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = (
        DOCUMENTS_DIR / filename
    )

    try:

        with open(
            file_path,
            "wb"
        ) as destination:

            destination.write(
                content
            )

        result = index_pdf(
            str(file_path)
        )

        print(
            "RESULT =",
            result
        )

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Erreur lors du traitement du PDF : "
                f"{error}"
            )
        )


@router.delete("/{filename}")
def remove_document(
    filename: str,
    payload: dict = Depends(verify_token)
):

    verify_admin(
        payload
    )

    filename = Path(
        filename
    ).name

    if not filename.lower().endswith(
        ".pdf"
    ):

        raise HTTPException(
            status_code=400,
            detail="Seuls les fichiers PDF peuvent être supprimés."
        )

    try:

        result = delete_document(
            file_name=filename,
            documents_dir=str(
                DOCUMENTS_DIR
            )
        )

        return {
            "message": (
                f"{filename} supprimé avec succès."
            ),
            **result
        }

    except ValueError as error:

        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except Exception as error:

        print(
            f"Erreur lors de la suppression "
            f"de {filename} : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Erreur lors de la suppression du document."
            )
        )