from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/")
def home():
    """Serve the frontend SPA."""
    return FileResponse("static/index.html")