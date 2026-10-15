from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.auth import router as auth_router
from app.routes.profile import router as profile_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.progress import router as progress_router
from app.routes.quiz import router as quiz_router

from app.services.question_bank_manager import question_bank_manager
from app.services.task_manager import task_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[WebIA] Démarrage de l'application.")

    question_bank_manager.start()

    print("[WebIA] QuestionBankManager démarré.")

    yield

    print("[WebIA] Arrêt de l'application.")

    question_bank_manager.stop()

    print("[WebIA] QuestionBankManager arrêté.")


app = FastAPI(
    title="WebIA",
    description="Plateforme de cybersécurité avec intelligence artificielle",
    version="1.0.0",
    lifespan=lifespan
)


@app.middleware("http")
async def prioritize_interactive_requests(request, call_next):
    """Les requêtes chatbot et quiz sont prioritaires sur les tâches de fond."""
    path = request.url.path
    is_priority_request = (
        path == "/chat"
        or path.startswith("/chat/")
        or path == "/quiz"
        or path.startswith("/quiz/")
    )
    if is_priority_request:
        task_manager.start_user_request()
    try:
        return await call_next(request)
    finally:
        if is_priority_request:
            task_manager.end_user_request()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(progress_router)
app.include_router(quiz_router)


@app.get("/")
def root():
    return {
        "message": "API WebIA opérationnelle"
    }