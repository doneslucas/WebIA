from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)

from starlette.concurrency import run_in_threadpool

from app.services.auth import verify_token

from app.services.indexer import (
    index_pdf,
    get_all_documents,
    get_document_category_ids,
    queue_document_question_banks,
    delete_document,
    get_generation_progress,
)

from app.services.task_manager import task_manager


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

BASE_DIR = Path(__file__).resolve().parents[2]
DOCUMENTS_DIR = BASE_DIR / "documents"
MAX_FILE_SIZE = 20 * 1024 * 1024


def verify_admin(payload: dict):
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail=(
                "Accès refusé. "
                "Seuls les administrateurs "
                "peuvent gérer les documents."
            ),
        )


@router.get("")
def list_documents(payload: dict = Depends(verify_token)):
    try:
        documents = get_all_documents()
        enriched_documents = []

        for document in documents:
            filename = document.get("file")

            if not filename:
                enriched_documents.append(document)
                continue

            try:
                progress = get_generation_progress(filename)

                if isinstance(progress, dict):
                    document = {
                        **document,
                        "processing_status": progress.get(
                            "status",
                            "not_started",
                        ),
                        "global_progress": progress.get(
                            "global_progress",
                            0,
                        ),
                    }

            except Exception as progress_error:
                print(
                    "[Documents] Impossible de récupérer la progression "
                    f"de {filename} : {progress_error}"
                )

                document = {
                    **document,
                    "processing_status": "not_started",
                    "global_progress": 0,
                }

            enriched_documents.append(document)

        return {"documents": enriched_documents}

    except Exception as error:
        print(
            "[Documents] Erreur lors de la récupération "
            f"des documents : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Impossible de récupérer les documents.",
        )


@router.get("/{filename}/progress")
def document_progress(
    filename: str,
    payload: dict = Depends(verify_token),
):
    filename = Path(filename).name

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Seuls les fichiers PDF sont acceptés.",
        )

    try:
        return get_generation_progress(filename)

    except Exception as error:
        print(
            "[Documents] Erreur lors de la récupération de la progression "
            f"pour {filename} : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Impossible de récupérer la progression de génération."
            ),
        )


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    payload: dict = Depends(verify_token),
):
    verify_admin(payload)

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Aucun fichier fourni.",
        )

    filename = Path(file.filename).name

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Seuls les fichiers PDF sont acceptés.",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Le fichier est vide.",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "Le fichier est trop volumineux. "
                "Taille maximale : 20 Mo."
            ),
        )

    # Réserver l'indexation avant d'écrire le fichier ou de commencer
    # son traitement. La réservation est atomique côté backend.
    acquired = await run_in_threadpool(
        task_manager.start_pdf_indexing
    )

    if not acquired:
        raise HTTPException(
            status_code=409,
            detail=(
                "Une indexation est déjà en cours. "
                "Attendez qu'elle se termine avant d'importer "
                "un autre PDF."
            ),
        )

    try:
        DOCUMENTS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path = DOCUMENTS_DIR / filename

        with open(file_path, "wb") as destination:
            destination.write(content)

        result = await run_in_threadpool(
            index_pdf,
            str(file_path),
            operation_already_reserved=True,
        )

        print("[Documents] RESULT =", result)

        return {
            **result,
            "question_banks": {
                "status": "waiting_manual",
                "difficulties": ["easy", "medium", "hard"],
                "target_per_difficulty": 50,
                "message": (
                    "Le PDF est indexé. Les questions ne seront générées "
                    "que lorsque vous lancerez explicitement la génération."
                ),
            },
        }

    except Exception as error:
        print(
            "[Documents] Erreur lors du traitement du PDF : "
            f"{error}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du traitement du PDF : {error}",
        )

    finally:
        # Libération garantie, même si l'indexation échoue.
        await run_in_threadpool(
            task_manager.end_pdf_indexing
        )


@router.post("/{filename}/generate-questions")
def generate_document_questions(
    filename: str,
    payload: dict = Depends(verify_token),
):
    """Lance explicitement la génération pour un document indexé."""
    verify_admin(payload)
    filename = Path(filename).name

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Seuls les fichiers PDF peuvent être traités.",
        )

    documents = get_all_documents()
    document = next(
        (item for item in documents if item.get("file") == filename),
        None,
    )
    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document introuvable ou non indexé.",
        )

    category_ids = get_document_category_ids(document["id"])
    if not category_ids:
        raise HTTPException(
            status_code=409,
            detail="Aucune catégorie n'est associée à ce document.",
        )

    try:
        result = queue_document_question_banks(
            filename=filename,
            category_ids=category_ids,
            enqueue=True,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        print(
            f"[Documents] Impossible de lancer la génération pour "
            f"{filename} : {error}"
        )
        raise HTTPException(
            status_code=500,
            detail="Impossible de lancer la génération des questions.",
        )

    return {
        "message": f"Génération demandée pour {filename}.",
        "filename": filename,
        "category_ids": category_ids,
        "difficulties": ["easy", "medium", "hard"],
        "queued_tasks": len(result.get("queued", [])) if isinstance(result, dict) else 0,
        "status": "queued",
    }


@router.delete("/{filename}")
def remove_document(
    filename: str,
    payload: dict = Depends(verify_token),
):
    verify_admin(payload)

    filename = Path(filename).name

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Seuls les fichiers PDF peuvent être supprimés.",
        )

    # La suppression conserve son fonctionnement indépendant :
    # elle ne demande pas le verrou exclusif d'indexation.
    task_manager.start_pdf_operation()

    try:
        from app.services.question_bank_manager import question_bank_manager
        question_bank_manager.cancel_document_tasks(filename)

        result = delete_document(
            file_name=filename,
            documents_dir=str(DOCUMENTS_DIR),
        )

        return {
            "message": f"{filename} supprimé avec succès.",
            **result,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except Exception as error:
        print(
            f"[Documents] Erreur lors de la suppression "
            f"de {filename} : {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la suppression du document.",
        )

    finally:
        task_manager.end_pdf_operation()