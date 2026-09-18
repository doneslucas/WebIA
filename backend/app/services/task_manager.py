from threading import Condition


class TaskManager:
    """
    Gestionnaire central des priorités du site.

    Priorités :
    1. Chatbot et quiz utilisateur
    2. Import / indexation des PDF
    3. Génération automatique des banques de questions

    Les tâches de priorité 2 et 3 sont coopératives :
    elles peuvent attendre lorsqu'une tâche de priorité
    supérieure est active.
    """

    def __init__(self):
        self._condition = Condition()

        self._active_user_requests = 0
        self._active_pdf_operations = 0

    # ============================================================
    # PRIORITÉ 1
    # ============================================================

    def start_user_request(self):
        """
        Signale le début d'une requête utilisateur prioritaire.

        Les tâches de priorité 2 et 3 doivent attendre.
        """

        with self._condition:

            self._active_user_requests += 1

            self._condition.notify_all()

            print(
                "[TaskManager] "
                f"Priorité 1 démarrée. "
                f"Requêtes utilisateur actives : "
                f"{self._active_user_requests}"
            )

    def end_user_request(self):
        """
        Signale la fin d'une requête utilisateur prioritaire.
        """

        with self._condition:

            if self._active_user_requests > 0:
                self._active_user_requests -= 1

            self._condition.notify_all()

            print(
                "[TaskManager] "
                f"Priorité 1 terminée. "
                f"Requêtes utilisateur actives : "
                f"{self._active_user_requests}"
            )

    # ============================================================
    # PRIORITÉ 2
    # ============================================================

    def start_pdf_operation(self):
        """
        Démarre une opération PDF de priorité 2.

        Elle attend qu'aucune requête utilisateur de priorité 1
        ne soit active.
        """

        with self._condition:

            while self._active_user_requests > 0:

                print(
                    "[TaskManager] "
                    "Import PDF en attente : "
                    "une requête utilisateur prioritaire est active."
                )

                self._condition.wait()

            self._active_pdf_operations += 1

            self._condition.notify_all()

            print(
                "[TaskManager] "
                f"Priorité 2 démarrée. "
                f"Opérations PDF actives : "
                f"{self._active_pdf_operations}"
            )

    def end_pdf_operation(self):
        """
        Termine une opération PDF de priorité 2.
        """

        with self._condition:

            if self._active_pdf_operations > 0:
                self._active_pdf_operations -= 1

            self._condition.notify_all()

            print(
                "[TaskManager] "
                f"Priorité 2 terminée. "
                f"Opérations PDF actives : "
                f"{self._active_pdf_operations}"
            )

    def wait_for_pdf_permission(self):
        """
        Utilisé par une opération PDF de priorité 2.

        L'indexation peut continuer uniquement lorsqu'aucune
        requête utilisateur de priorité 1 n'est active.

        Cette méthode permet donc à une requête utilisateur
        d'interrompre coopérativement l'indexation entre
        deux opérations coûteuses.
        """

        with self._condition:

            while self._active_user_requests > 0:

                print(
                    "[TaskManager] "
                    "Indexation PDF en pause : "
                    "priorité 1 active."
                )

                self._condition.wait()

    # ============================================================
    # PRIORITÉ 3
    # ============================================================

    def wait_for_background_permission(self):
        """
        Autorise une opération de priorité 3 uniquement lorsqu'il
        n'y a ni requête utilisateur ni opération PDF active.

        Cette méthode est utilisée entre deux opérations coûteuses.
        """

        with self._condition:

            while (
                self._active_user_requests > 0
                or self._active_pdf_operations > 0
            ):

                if self._active_user_requests > 0:

                    print(
                        "[TaskManager] "
                        "Génération automatique en pause : "
                        "priorité 1 active."
                    )

                elif self._active_pdf_operations > 0:

                    print(
                        "[TaskManager] "
                        "Génération automatique en pause : "
                        "priorité 2 active."
                    )

                self._condition.wait()

    # ============================================================
    # INFORMATIONS
    # ============================================================

    def has_active_user_request(self):
        """
        Retourne True si une requête utilisateur est active.
        """

        with self._condition:

            return (
                self._active_user_requests > 0
            )

    def has_active_pdf_operation(self):
        """
        Retourne True si une opération PDF est active.
        """

        with self._condition:

            return (
                self._active_pdf_operations > 0
            )

    def get_status(self):
        """
        Retourne l'état actuel du gestionnaire.
        """

        with self._condition:

            return {
                "active_user_requests": (
                    self._active_user_requests
                ),
                "active_pdf_operations": (
                    self._active_pdf_operations
                ),
                "background_generation_paused": (
                    self._active_user_requests > 0
                    or self._active_pdf_operations > 0
                )
            }


task_manager = TaskManager()