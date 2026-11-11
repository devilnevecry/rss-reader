"""Feed API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import FeedCreate, FeedOut, ErrorOut
from app.services import feed_service

router = APIRouter(prefix="/api/feeds", tags=["feeds"])


@router.get("", response_model=list[FeedOut], summary="Список всех источников")
def list_feeds(db: Session = Depends(get_db)):
    return feed_service.get_feeds(db)


@router.post(
    "",
    response_model=FeedOut,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить новый RSS-источник",
    responses={400: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
def add_feed(payload: FeedCreate, db: Session = Depends(get_db)):
    try:
        feed = feed_service.create_feed(db, payload.url)
    except ValueError as exc:
        msg = str(exc)
        if "уже добавлен" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return feed


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить источник")
def remove_feed(feed_id: int, db: Session = Depends(get_db)):
    if not feed_service.delete_feed(db, feed_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Источник не найден")


@router.post("/{feed_id}/refresh", response_model=FeedOut, summary="Обновить один источник")
def refresh_one_feed(feed_id: int, db: Session = Depends(get_db)):
    try:
        return feed_service.refresh_feed(db, feed_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/refresh-all", response_model=list[FeedOut], summary="Обновить все источники")
def refresh_all(db: Session = Depends(get_db)):
    return feed_service.refresh_all_feeds(db)
