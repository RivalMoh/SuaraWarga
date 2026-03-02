from fastapi import APIRouter
from app.db.models import get_reports

router = APIRouter()

@router.get("/api/reports")
def list_reports(page: int = 1, limit: int = 5):
    return get_reports(page=page, limit=limit)