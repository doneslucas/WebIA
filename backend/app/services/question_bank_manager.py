"""Gestionnaire des banques QCM par document, catégorie et difficulté."""

import queue
import threading
from typing import Optional

from app.database.connection import get_connection
from app.services.task_manager import task_manager
from app.services.quiz import (
    TARGET_QUESTION_COUNT,
    VALID_DIFFICULTIES,
    count_questions,
    get_max_capacity,
    generate_questions_for_bank,
)


class QuestionBankManager:
    """Traite les demandes de génération ajoutées explicitement à la file."""

    def __init__(self):
        self.running = False
        self.task_queue = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Une tâche est identifiée par document + catégorie + difficulté.
        self.pending_tasks = set()
        self.pending_tasks_lock = threading.Lock()

        self.task_status = {}
        self.task_status_lock = threading.Lock()

    # --------------------------------------------------------
    # Démarrage et arrêt
    # --------------------------------------------------------

    def start(self):
        """Démarre uniquement le worker ; aucune génération n'est déclenchée."""
        if self.running:
            print("[WebIA] QuestionBankManager déjà démarré.")
            return

        self.running = True
        self.stop_event.clear()
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name="QuestionBankManagerWorker",
            daemon=True,
        )
        self.worker_thread.start()
        print("[WebIA] QuestionBankManager démarré.")

    def stop(self):
        """Arrête le worker proprement."""
        if not self.running:
            return

        self.running = False
        self.stop_event.set()
        self.task_queue.put(None)

        if self.worker_thread is not None:
            self.worker_thread.join(timeout=10)

        self.worker_thread = None
        print("[WebIA] QuestionBankManager arrêté.")

    def is_running(self):
        return self.running

    # --------------------------------------------------------
    # Worker de génération
    # --------------------------------------------------------

    def _worker_loop(self):
        print("[WebIA] Worker QuestionBankManager prêt.")

        while not self.stop_event.is_set():
            try:
                task = self.task_queue.get(timeout=1)
            except queue.Empty:
                continue

            if task is None:
                self.task_queue.task_done()
                break

            document, category_id, difficulty = task
            task_key = self._make_task_key(
                document,
                category_id,
                difficulty,
            )
            background_reserved = False

            try:
                task_manager.start_background_operation()
                background_reserved = True

                if self._get_task_status_value(task_key) == "cancelled":
                    continue

                if not self._document_exists(document):
                    self._set_task_status(
                        task_key,
                        "cancelled",
                        error="Document supprimé ou introuvable.",
                    )
                    continue

                self._set_task_status(task_key, "running")
                print(
                    "[WebIA] Traitement : "
                    f"document={document}, category_id={category_id}, "
                    f"difficulty={difficulty}"
                )

                result = self._process_task(
                    document,
                    category_id,
                    difficulty,
                )

                if result.get("cancelled"):
                    self._set_task_status(
                        task_key,
                        "cancelled",
                        error="Document supprimé pendant la génération.",
                    )
                elif result["complete"] or result["target"] == 0:
                    self._set_task_status(
                        task_key,
                        "completed",
                        result=result,
                    )
                else:
                    self._set_task_status(
                        task_key,
                        "incomplete",
                        result=result,
                    )

            except Exception as exc:
                self._set_task_status(
                    task_key,
                    "error",
                    error=str(exc),
                )

                try:
                    if self._document_exists(document):
                        from app.services.indexer import update_generation_progress

                        status = self.get_category_difficulty_status(
                            document=document,
                            category_id=category_id,
                            difficulty=difficulty,
                        )

                        update_generation_progress(
                            filename=document,
                            difficulty=difficulty,
                            current=status["current"],
                            target=status["target"],
                            status="error",
                            category_id=category_id,
                        )
                except Exception as progress_error:
                    print(
                        "[WebIA] Impossible de mettre à jour la progression : "
                        f"{progress_error}"
                    )

                print(
                    "[WebIA] Erreur de génération : "
                    f"document={document}, category_id={category_id}, "
                    f"difficulty={difficulty}, error={exc}"
                )

            finally:
                if background_reserved:
                    task_manager.end_background_operation()

                with self.pending_tasks_lock:
                    self.pending_tasks.discard(task_key)

                self.task_queue.task_done()

    def _document_exists(self, document: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1
                    FROM documents
                    WHERE file_name = %s
                    LIMIT 1
                    """,
                    (document,),
                )
                return cursor.fetchone() is not None

    def _get_task_status_value(self, task_key) -> str:
        with self.task_status_lock:
            return self.task_status.get(
                task_key,
                {},
            ).get("status", "not_queued")

    # --------------------------------------------------------
    # Annulation des demandes d'un document
    # --------------------------------------------------------

    def cancel_document_tasks(self, document: str) -> int:
        """Retire les tâches en attente d'un document."""
        document = str(document)
        cancelled = 0

        with self.pending_tasks_lock:
            keys = [
                key
                for key in self.pending_tasks
                if key[0] == document
            ]

            for key in keys:
                self.pending_tasks.discard(key)
                self._set_task_status(
                    key,
                    "cancelled",
                    error="Document supprimé.",
                )
                cancelled += 1

        with self.task_queue.mutex:
            kept = []

            for task in self.task_queue.queue:
                if task is not None and task[0] == document:
                    self.task_queue.unfinished_tasks -= 1
                    cancelled += 1
                else:
                    kept.append(task)

            self.task_queue.queue.clear()
            self.task_queue.queue.extend(kept)

            if self.task_queue.unfinished_tasks < 0:
                self.task_queue.unfinished_tasks = 0

            self.task_queue.not_full.notify_all()

            if self.task_queue.unfinished_tasks == 0:
                self.task_queue.all_tasks_done.notify_all()

        return cancelled

    # --------------------------------------------------------
    # Une banque : document + catégorie + difficulté
    # --------------------------------------------------------

    def _process_task(
        self,
        document: str,
        category_id: int,
        difficulty: str,
    ):
        status = self.get_category_difficulty_status(
            document=document,
            category_id=category_id,
            difficulty=difficulty,
        )

        print(
            "[WebIA] État banque : "
            f"category_id={category_id}, difficulty={difficulty}, "
            f"current={status['current']}, target={status['target']}, "
            f"capacity={status['capacity']}"
        )

        from app.services.indexer import update_generation_progress

        if status["complete"] or status["target"] == 0:
            update_generation_progress(
                filename=document,
                difficulty=difficulty,
                current=status["current"],
                target=status["target"],
                status="completed",
                category_id=category_id,
            )
            return status

        update_generation_progress(
            filename=document,
            difficulty=difficulty,
            current=status["current"],
            target=status["target"],
            status="running",
            category_id=category_id,
        )

        def report_progress(current: int, target: int):
            update_generation_progress(
                filename=document,
                difficulty=difficulty,
                current=current,
                target=target,
                status="running",
                category_id=category_id,
            )

        generate_questions_for_bank(
            document=document,
            difficulty=difficulty,
            target_count=status["target"],
            category_ids=[category_id],
            progress_callback=report_progress,
            continue_callback=lambda: self._document_exists(document),
        )

        if not self._document_exists(document):
            return {"cancelled": True}

        final_status = self.get_category_difficulty_status(
            document=document,
            category_id=category_id,
            difficulty=difficulty,
        )

        final_state = (
            "completed"
            if final_status["complete"] or final_status["target"] == 0
            else "incomplete"
        )

        update_generation_progress(
            filename=document,
            difficulty=difficulty,
            current=final_status["current"],
            target=final_status["target"],
            status=final_state,
            category_id=category_id,
        )

        return final_status

    # --------------------------------------------------------
    # Calcul de la capacité et de l'état réel
    # --------------------------------------------------------

    def get_category_difficulty_status(
        self,
        document: str,
        category_id: int,
        difficulty: str,
    ):
        if difficulty not in VALID_DIFFICULTIES:
            raise ValueError("Difficulté invalide.")

        current = count_questions(
            document=document,
            difficulty=difficulty,
            category_ids=[category_id],
        )

        capacity = get_max_capacity(
            document=document,
            difficulty=difficulty,
            category_ids=[category_id],
        )

        # Une catégorie ne peut pas dépasser 50 questions par difficulté.
        # La capacité dépend aussi du nombre de chunks classifiés disponibles.
        target = min(TARGET_QUESTION_COUNT, capacity)

        return {
            "category_id": category_id,
            "difficulty": difficulty,
            "current": current,
            "target": target,
            "capacity": capacity,
            "complete": current >= target,
            "remaining": max(0, target - current),
        }

    # --------------------------------------------------------
    # Ajout et déduplication des tâches
    # --------------------------------------------------------

    def enqueue(
        self,
        document: str,
        category_id: int,
        difficulty: str,
    ):
        if difficulty not in VALID_DIFFICULTIES:
            raise ValueError("Difficulté invalide.")

        task_key = self._make_task_key(
            document,
            category_id,
            difficulty,
        )

        with self.pending_tasks_lock:
            if task_key in self.pending_tasks:
                print(f"[WebIA] Tâche déjà en attente : {task_key}")
                return False

            self.pending_tasks.add(task_key)

        self._set_task_status(task_key, "queued")
        self.task_queue.put((document, category_id, difficulty))

        print(
            "[WebIA] Tâche ajoutée : "
            f"document={document}, category_id={category_id}, "
            f"difficulty={difficulty}"
        )

        return True

    def enqueue_document(
        self,
        document: str,
        category_ids: list[int],
        difficulties: Optional[list[str]] = None,
    ):
        if difficulties is None:
            difficulties = ["easy", "medium", "hard"]

        queued = []

        for category_id in sorted(set(category_ids)):
            for difficulty in difficulties:
                if difficulty not in VALID_DIFFICULTIES:
                    raise ValueError("Difficulté invalide.")

                added = self.enqueue(
                    document=document,
                    category_id=category_id,
                    difficulty=difficulty,
                )

                if added:
                    queued.append({
                        "category_id": category_id,
                        "difficulty": difficulty,
                    })

        return queued

    def ensure_category_difficulty(
        self,
        document: str,
        category_id: int,
        difficulty: str,
    ):
        """Vérifie l'état dans PostgreSQL puis met une tâche en file si nécessaire."""
        status = self.get_category_difficulty_status(
            document=document,
            category_id=category_id,
            difficulty=difficulty,
        )

        if status["complete"] or status["target"] == 0:
            return {
                **status,
                "queued": False,
            }

        queued = self.enqueue(
            document=document,
            category_id=category_id,
            difficulty=difficulty,
        )

        return {
            **status,
            "queued": queued,
        }

    def ensure_categories(
        self,
        document: str,
        category_ids: list[int],
        difficulties: Optional[list[str]] = None,
    ):
        """Programme seulement les catégories et difficultés demandées."""
        if difficulties is None:
            difficulties = ["easy", "medium", "hard"]

        results = []

        for category_id in category_ids:
            for difficulty in difficulties:
                results.append(
                    self.ensure_category_difficulty(
                        document=document,
                        category_id=category_id,
                        difficulty=difficulty,
                    )
                )

        return results

    # --------------------------------------------------------
    # État d'une tâche
    # --------------------------------------------------------

    def get_task_status(
        self,
        document: str,
        category_id: int,
        difficulty: str,
    ):
        task_key = self._make_task_key(
            document,
            category_id,
            difficulty,
        )

        with self.task_status_lock:
            return self.task_status.get(
                task_key,
                {"status": "not_queued"},
            ).copy()

    @staticmethod
    def _make_task_key(
        document: str,
        category_id: int,
        difficulty: str,
    ):
        return document, category_id, difficulty

    def _set_task_status(
        self,
        task_key,
        status: str,
        error: Optional[str] = None,
        result: Optional[dict] = None,
    ):
        with self.task_status_lock:
            data = {"status": status}

            if error is not None:
                data["error"] = error

            if result is not None:
                data["current"] = result.get("current", 0)
                data["target"] = result.get("target", 0)
                data["capacity"] = result.get("capacity", 0)
                data["remaining"] = result.get("remaining", 0)

            self.task_status[task_key] = data


question_bank_manager = QuestionBankManager()