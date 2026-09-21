import threading

from app.services.indexer import (
    get_all_documents,
    QUIZ_DIFFICULTIES,
)

from app.services.quiz import (
    GENERATION_THRESHOLD,
    TARGET_QUESTION_COUNT,
    count_questions,
    get_max_capacity,
    generate_questions_for_bank,
    generation_lock,
    active_generations,
)

from app.services.task_manager import task_manager


class QuestionBankManager:
    """
    Gestionnaire automatique des banques de questions.

    Fonctionnement :
    - Vérifie régulièrement toutes les banques de questions.
    - Si une banque contient moins de GENERATION_THRESHOLD questions,
      une génération automatique est lancée.
    - La génération vise TARGET_QUESTION_COUNT questions.
    - La génération respecte la priorité 3 du TaskManager.
    - Une seule génération peut être active pour un couple
      (document, difficulté).
    """

    CHECK_INTERVAL = 60

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            print(
                "[QuestionBankManager] "
                "Le manager est déjà démarré."
            )
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="QuestionBankManager",
            daemon=True
        )

        self._thread.start()

        print(
            "[QuestionBankManager] "
            "Manager démarré."
        )

    def stop(self):
        print(
            "[QuestionBankManager] "
            "Arrêt du manager demandé."
        )

        self._stop_event.set()

        if self._thread is not None:
            self._thread.join(
                timeout=self.CHECK_INTERVAL + 5
            )

        self._thread = None

        print(
            "[QuestionBankManager] "
            "Manager arrêté."
        )

    def _monitor_loop(self):
        print(
            "[QuestionBankManager] "
            "Boucle de surveillance démarrée."
        )

        while not self._stop_event.is_set():

            try:
                self.check_all_banks()

            except Exception as error:
                print(
                    "[QuestionBankManager] "
                    f"Erreur pendant la surveillance : {error}"
                )

            self._stop_event.wait(
                self.CHECK_INTERVAL
            )

        print(
            "[QuestionBankManager] "
            "Boucle de surveillance terminée."
        )

    def check_all_banks(self):
        documents = get_all_documents()

        if not documents:
            print(
                "[QuestionBankManager] "
                "Aucun document à surveiller."
            )
            return

        for document_info in documents:

            if self._stop_event.is_set():
                return

            # get_all_documents() retourne la clé "file"
            document = document_info.get(
                "file"
            )

            if not document:
                continue

            for difficulty in QUIZ_DIFFICULTIES:

                if self._stop_event.is_set():
                    return

                self._check_bank(
                    document=document,
                    difficulty=difficulty
                )

    def _check_bank(
        self,
        document: str,
        difficulty: str
    ):
        current_count = count_questions(
            document=document,
            difficulty=difficulty
        )

        max_capacity = get_max_capacity(
            document
        )

        if max_capacity <= 0:
            return

        target_count = min(
            TARGET_QUESTION_COUNT,
            max_capacity
        )

        print(
            "[QuestionBankManager] "
            f"{document} / {difficulty} : "
            f"{current_count}/{target_count}"
        )

        if current_count >= GENERATION_THRESHOLD:
            return

        if current_count >= target_count:
            return

        generation_key = (
            document,
            difficulty
        )

        with generation_lock:

            if generation_key in active_generations:
                print(
                    "[QuestionBankManager] "
                    f"Génération déjà active pour "
                    f"{document} / {difficulty}."
                )
                return

            active_generations.add(
                generation_key
            )

        print(
            "[QuestionBankManager] "
            f"Seuil atteint pour "
            f"{document} / {difficulty} : "
            f"{current_count} < {GENERATION_THRESHOLD}."
        )

        thread = threading.Thread(
            target=self._generate_bank,
            args=(
                document,
                difficulty,
                target_count,
                generation_key
            ),
            name=(
                f"QuestionGeneration-"
                f"{document}-"
                f"{difficulty}"
            ),
            daemon=True
        )

        thread.start()

    def _generate_bank(
        self,
        document: str,
        difficulty: str,
        target_count: int,
        generation_key
    ):
        try:

            print(
                "[QuestionBankManager] "
                f"Génération démarrée : "
                f"{document} / {difficulty} "
                f"→ objectif {target_count}."
            )

            task_manager.wait_for_background_permission()

            generate_questions_for_bank(
                document=document,
                difficulty=difficulty,
                target_count=target_count,
                background=True
            )

            final_count = count_questions(
                document=document,
                difficulty=difficulty
            )

            print(
                "[QuestionBankManager] "
                f"Génération terminée : "
                f"{document} / {difficulty} "
                f"= {final_count} questions."
            )

        except Exception as error:

            print(
                "[QuestionBankManager] "
                f"Erreur de génération pour "
                f"{document} / {difficulty} : "
                f"{error}"
            )

        finally:

            with generation_lock:
                active_generations.discard(
                    generation_key
                )

            print(
                "[QuestionBankManager] "
                f"Génération libérée : "
                f"{document} / {difficulty}."
            )


question_bank_manager = QuestionBankManager()