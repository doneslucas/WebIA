from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.auth import router as auth_router
from app.routes.profile import router as profile_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.progress import router as progress_router


app = FastAPI(
    title="WebIA",
    description="Plateforme de cybersécurité avec intelligence artificielle",
    version="1.0.0"
)


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


@app.get("/")
def root():
    return {
        "message": "API WebIA opérationnelle"
    }