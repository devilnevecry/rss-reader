"""Stats API endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import StatsOut
from app.services import feed_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsOut, summary="Статистика ридера")
def get_stats(db: Session = Depends(get_db)):
    return feed_service.get_stats(db)
