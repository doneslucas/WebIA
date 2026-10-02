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

from starlette.concurrency import run_in_threadpool

from app.services.auth import verify_token

from app.services.indexer import (
    index_pdf,
    get_all_documents,
    delete_document,
    generate_document_question_banks,
    get_generation_progress
)

from app.services.task_manager import task_manager


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


BASE_DIR = Path(__file__).resolve().parents[2]

DOCUMENTS_DIR = (
    BASE_DIR / "documents"
)

MAX_FILE_SIZE = (
    20 * 1024 * 1024
)


generation_in_progress = set()

generation_lock = Lock()


def verify_admin(
    payload: dict
):
    if payload.get("role") != "admin":

        raise HTTPException(
            status_code=403,
            detail=(
                "Accès refusé. "
                "Seuls les administrateurs "
                "peuvent gérer les documents."
            )
        )


def generate_banks_in_background(
    filename: str
):

    with generation_lock:

        if filename in generation_in_progress:

            print(
                "[Documents] "
                f"Génération déjà en cours "
                f"pour {filename}. "
                "Nouvelle génération ignorée."
            )

            return

        generation_in_progress.add(
            filename
        )

    try:

        print(
            "[Documents] "
            f"Démarrage de la génération "
            f"des banques pour {filename}"
        )

        generate_document_question_banks(
            filename
        )

    except Exception as error:

        print(
            "[Documents] "
            f"Erreur génération des banques "
            f"pour {filename} : {error}"
        )

    finally:

        with generation_lock:

            generation_in_progress.discard(
                filename
            )

        print(
            "[Documents] "
            f"Génération libérée pour "
            f"{filename}"
        )


@router.get("")
def list_documents(
    payload: dict = Depends(verify_token)
):

    """
    Liste des documents disponibles.

    Tous les utilisateurs authentifiés
    peuvent consulter cette liste afin
    de pouvoir sélectionner un document
    pour générer un quiz.

    Cette route ne permet aucune modification
    des documents.

    En plus des informations générales du document,
    la route retourne maintenant son état réel de
    traitement afin que le frontend puisse distinguer
    un document terminé d'un document encore en cours
    d'indexation ou de génération.
    """

    try:

        documents = get_all_documents()

        enriched_documents = []

        for document in documents:

            filename = document.get(
                "file"
            )

            if not filename:

                enriched_documents.append(
                    document
                )

                continue

            try:

                progress = get_generation_progress(
                    filename
                )

                if isinstance(
                    progress,
                    dict
                ):

                    document = {
                        **document,
                        "processing_status":
                            progress.get(
                                "status",
                                "not_started"
                            ),
                        "global_progress":
                            progress.get(
                                "global_progress",
                                0
                            )
                    }

            except Exception as progress_error:

                print(
                    "[Documents] "
                    f"Impossible de récupérer "
                    f"la progression de {filename} : "
                    f"{progress_error}"
                )

                document = {
                    **document,
                    "processing_status":
                        "not_started",
                    "global_progress":
                        0
                }

            enriched_documents.append(
                document
            )

        return {
            "documents":
                enriched_documents
        }

    except Exception as error:

        print(
            "[Documents] "
            "Erreur lors de la récupération "
            f"des documents : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Impossible de récupérer "
                "les documents."
            )
        )


@router.get(
    "/{filename}/progress"
)
def document_progress(
    filename: str,
    payload: dict = Depends(verify_token)
):

    """
    Progression de génération des questions.

    Cette information peut être consultée
    par tout utilisateur authentifié.
    """

    filename = Path(
        filename
    ).name

    if not filename.lower().endswith(
        ".pdf"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Seuls les fichiers PDF "
                "sont acceptés."
            )
        )

    try:

        return get_generation_progress(
            filename
        )

    except Exception as error:

        print(
            "[Documents] "
            "Erreur lors de la récupération "
            f"de la progression pour "
            f"{filename} : {error}"
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

    """
    Upload d'un document.

    Réservé aux administrateurs.
    """

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
                "Seuls les fichiers PDF "
                "sont acceptés."
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

        result = await run_in_threadpool(
            index_pdf,
            str(file_path)
        )

        print(
            "RESULT =",
            result
        )

        with generation_lock:

            generation_already_running = (
                filename
                in generation_in_progress
            )

        if generation_already_running:

            print(
                "[Documents] "
                f"Une génération est déjà "
                f"en cours pour {filename}. "
                "Aucune nouvelle tâche ajoutée."
            )

        else:

            background_tasks.add_task(
                generate_banks_in_background,
                filename
            )

            print(
                "[Documents] "
                f"Génération des banques "
                f"planifiée pour {filename}"
            )

        return {
            **result,
            "question_banks": {
                "status":
                    "generation_started",

                "difficulties": [
                    "easy",
                    "medium",
                    "hard"
                ],

                "target_per_difficulty":
                    50
            }
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Erreur lors du traitement "
                f"du PDF : {error}"
            )
        )


@router.delete(
    "/{filename}"
)
def remove_document(
    filename: str,
    payload: dict = Depends(verify_token)
):

    """
    Suppression d'un document.

    Réservée aux administrateurs.
    """

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
                "Seuls les fichiers PDF "
                "peuvent être supprimés."
            )
        )

    task_manager.start_pdf_operation()

    try:

        result = delete_document(
            file_name=filename,
            documents_dir=str(
                DOCUMENTS_DIR
            )
        )

        with generation_lock:

            generation_was_running = (
                filename
                in generation_in_progress
            )

            generation_in_progress.discard(
                filename
            )

        if generation_was_running:

            print(
                "[Documents] "
                f"Document {filename} supprimé "
                "alors qu'une génération était "
                "encore enregistrée comme active."
            )

            print(
                "[Documents] "
                "Les insertions sur d'anciens "
                "chunks seront ignorées."
            )

        return {
            "message":
                f"{filename} supprimé avec succès.",

            **result
        }

    except ValueError as error:

        raise HTTPException(
            status_code=404,
            detail=str(error)
        )

    except Exception as error:

        print(
            "[Documents] "
            f"Erreur lors de la suppression "
            f"de {filename}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Erreur lors de la "
                "suppression du document."
            )
        )

    finally:

        task_manager.end_pdf_operation()