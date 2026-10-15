from threading import Condition


class TaskManager:
    """Synchronise les requêtes utilisateur, les opérations PDF et la génération."""

    def __init__(self):
        self._condition = Condition()
        self._active_user_requests = 0
        self._active_pdf_operations = 0
        self._active_background_operations = 0
        self._waiting_pdf_operations = 0
        self._pdf_indexing_active = False

    # Priorité 1 : requêtes interactives
    def start_user_request(self):
        with self._condition:
            self._active_user_requests += 1
            self._condition.notify_all()

    def end_user_request(self):
        with self._condition:
            if self._active_user_requests > 0:
                self._active_user_requests -= 1
            self._condition.notify_all()

    # Priorité 2 : indexation exclusive
    def start_pdf_indexing(self) -> bool:
        """Réserve un créneau exclusif pour l'indexation d'un PDF."""
        with self._condition:
            if self._pdf_indexing_active:
                return False

            # Réserve immédiatement le créneau pour refuser un second upload
            # simultané, même si cette indexation doit attendre une autre tâche.
            self._pdf_indexing_active = True
            self._waiting_pdf_operations += 1
            try:
                while (
                    self._active_user_requests > 0
                    or self._active_pdf_operations > 0
                    or self._active_background_operations > 0
                ):
                    self._condition.wait()

                self._active_pdf_operations += 1
                return True
            except BaseException:
                self._pdf_indexing_active = False
                self._condition.notify_all()
                raise
            finally:
                self._waiting_pdf_operations -= 1
                self._condition.notify_all()

    def end_pdf_indexing(self):
        with self._condition:
            if self._pdf_indexing_active:
                self._pdf_indexing_active = False
                if self._active_pdf_operations > 0:
                    self._active_pdf_operations -= 1
            self._condition.notify_all()

    # Priorité 2 : suppressions et opérations PDF non-indexation
    def start_pdf_operation(self):
        """Réserve une opération PDF exclusive, sans chevauchement avec génération."""
        with self._condition:
            self._waiting_pdf_operations += 1
            try:
                while (
                    self._active_user_requests > 0
                    or self._active_pdf_operations > 0
                    or self._active_background_operations > 0
                    or self._pdf_indexing_active
                ):
                    self._condition.wait()
                self._active_pdf_operations += 1
            finally:
                self._waiting_pdf_operations -= 1
                self._condition.notify_all()

    def end_pdf_operation(self):
        with self._condition:
            if self._active_pdf_operations > 0:
                self._active_pdf_operations -= 1
            self._condition.notify_all()

    def wait_for_pdf_permission(self):
        """Point de contrôle coopératif utilisé pendant l'indexation."""
        with self._condition:
            while self._active_user_requests > 0:
                self._condition.wait()

    # Priorité 3 : génération en arrière-plan
    def start_background_operation(self):
        """Démarre une tâche de fond uniquement si les priorités supérieures sont libres."""
        with self._condition:
            while (
                self._active_user_requests > 0
                or self._active_pdf_operations > 0
                or self._waiting_pdf_operations > 0
            ):
                self._condition.wait()
            self._active_background_operations += 1
            self._condition.notify_all()

    def end_background_operation(self):
        with self._condition:
            if self._active_background_operations > 0:
                self._active_background_operations -= 1
            self._condition.notify_all()

    def wait_for_background_permission(self):
        """Point de contrôle coopératif pour laisser passer les requêtes et opérations PDF."""
        with self._condition:
            while self._active_user_requests > 0:
                self._condition.wait()

            # À la frontière entre deux lots, libère temporairement le créneau
            # de fond si une opération PDF attend. Cela évite à la fois les
            # accès concurrents à PostgreSQL/Chroma et un blocage mutuel.
            released_background_slot = False
            if self._waiting_pdf_operations > 0 and self._active_background_operations > 0:
                self._active_background_operations -= 1
                released_background_slot = True
                self._condition.notify_all()

            while (
                self._active_user_requests > 0
                or self._active_pdf_operations > 0
                or self._waiting_pdf_operations > 0
            ):
                self._condition.wait()

            if released_background_slot:
                self._active_background_operations += 1
                self._condition.notify_all()

    # État
    def has_active_user_request(self):
        with self._condition:
            return self._active_user_requests > 0

    def has_active_pdf_operation(self):
        with self._condition:
            return self._active_pdf_operations > 0

    def has_active_pdf_indexing(self):
        with self._condition:
            return self._pdf_indexing_active

    def get_status(self):
        with self._condition:
            return {
                "active_user_requests": self._active_user_requests,
                "active_pdf_operations": self._active_pdf_operations,
                "active_pdf_indexing": self._pdf_indexing_active,
                "active_background_operations": self._active_background_operations,
                "waiting_pdf_operations": self._waiting_pdf_operations,
                "background_generation_paused": (
                    self._active_user_requests > 0
                    or self._active_pdf_operations > 0
                    or self._waiting_pdf_operations > 0
                ),
            }


task_manager = TaskManager()
