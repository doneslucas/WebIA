from pathlib import Path
from threading import Lock

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile
)

from app.services.auth import verify_token

from app.services.indexer import (
    index_pdf,
    get_all_documents,
    delete_document,
    generate_document_question_banks,
    get_generation_progress
)


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


BASE_DIR = Path(__file__).resolve().parents[2]

DOCUMENTS_DIR = BASE_DIR / "documents"

MAX_FILE_SIZE = 20 * 1024 * 1024


# ============================================================
# GESTION DES GÉNÉRATIONS EN COURS
# ============================================================

generation_in_progress = set()

generation_lock = Lock()


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


def generate_banks_in_background(
    filename: str
):

    # --------------------------------------------------------
    # Vérification atomique :
    # une seule génération à la fois pour un même fichier.
    # --------------------------------------------------------

    with generation_lock:

        if filename in generation_in_progress:

            print(
                f"[Documents] "
                f"Génération déjà en cours pour {filename}. "
                f"Nouvelle génération ignorée."
            )

            return

        generation_in_progress.add(
            filename
        )

    try:

        print(
            f"[Documents] "
            f"Démarrage de la génération des banques "
            f"pour {filename}"
        )

        generate_document_question_banks(
            filename
        )

    except Exception as error:

        print(
            f"[Documents] "
            f"Erreur génération des banques "
            f"pour {filename} : {error}"
        )

    finally:

        with generation_lock:

            generation_in_progress.discard(
                filename
            )

        print(
            f"[Documents] "
            f"Génération libérée pour {filename}"
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
            detail=(
                "Impossible de récupérer les documents."
            )
        )


@router.get("/{filename}/progress")
def document_progress(
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
            detail=(
                "Seuls les fichiers PDF sont acceptés."
            )
        )

    try:

        return get_generation_progress(
            filename
        )

    except Exception as error:

        print(
            f"Erreur lors de la récupération "
            f"de la progression pour {filename} : "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Impossible de récupérer "
                "la progression de génération."
            )
        )


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
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
            detail=(
                "Seuls les fichiers PDF sont acceptés."
            )
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

        # ----------------------------------------------------
        # Lancement de la génération des banques
        # ----------------------------------------------------

        with generation_lock:

            generation_already_running = (
                filename
                in generation_in_progress
            )

        if generation_already_running:

            print(
                f"[Documents] "
                f"Une génération est déjà en cours "
                f"pour {filename}. "
                f"Aucune nouvelle tâche ajoutée."
            )

        else:

            background_tasks.add_task(
                generate_banks_in_background,
                filename
            )

            print(
                f"[Documents] "
                f"Génération des banques planifiée "
                f"pour {filename}"
            )

        return {
            **result,
            "question_banks": {
                "status": "generation_started",
                "difficulties": [
                    "easy",
                    "medium",
                    "hard"
                ],
                "target_per_difficulty": 50
            }
        }

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
            detail=(
                "Seuls les fichiers PDF peuvent "
                "être supprimés."
            )
        )

    try:

        result = delete_document(
            file_name=filename,
            documents_dir=str(
                DOCUMENTS_DIR
            )
        )

        # ----------------------------------------------------
        # Sécurité supplémentaire :
        # si le document est supprimé alors qu'une génération
        # est encore enregistrée comme active, on libère son
        # verrou.
        # ----------------------------------------------------

        with generation_lock:

            generation_in_progress.discard(
                filename
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
                "Erreur lors de la suppression "
                "du document."
            )
        )