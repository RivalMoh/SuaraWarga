from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import CORS_ORIGINS
from app.db.database import init_db
from app.api import report, history, root

def create_app():
    app = FastAPI(
        title="SuaraWarga API",
        description="Voice-based disaster reporting API for Indonesian citizens.",
        version="1.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(root.router)
    app.include_router(report.router)
    app.include_router(history.router)

    app.mount("/static", StaticFiles(directory="static"), name="static")

    init_db()

    return app