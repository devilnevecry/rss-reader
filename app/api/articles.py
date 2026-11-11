"""Article API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ArticleOut, ArticleUpdate, PaginatedArticles, ErrorOut
from app.services import feed_service

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=PaginatedArticles, summary="Лента публикаций")
def list_articles(
    db: Session = Depends(get_db),
    feed_id: int | None = Query(default=None, description="Фильтр по источнику"),
    unread_only: bool = Query(default=False, description="Только непрочитанные"),
    favorites_only: bool = Query(default=False, description="Только избранное"),
    search: str | None = Query(default=None, description="Поиск по названию, описанию, источнику"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    items, total = feed_service.get_articles(
        db,
        feed_id=feed_id,
        unread_only=unread_only,
        favorites_only=favorites_only,
        search=search,
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedArticles(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{article_id}", response_model=ArticleOut, summary="Публикация по ID")
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = feed_service.get_article(db, article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Публикация не найдена")
    return article


@router.post("/{article_id}/read", response_model=ArticleOut, summary="Пометить прочитанной / непрочитанной")
def set_read(article_id: int, payload: ArticleUpdate, db: Session = Depends(get_db)):
    if payload.is_read is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Поле is_read обязательно")
    article = feed_service.mark_read(db, article_id, payload.is_read)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Публикация не найдена")
    return article


@router.post("/{article_id}/favorite", response_model=ArticleOut, summary="Добавить / убрать из избранного")
def set_favorite(article_id: int, payload: ArticleUpdate, db: Session = Depends(get_db)):
    if payload.is_favorite is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Поле is_favorite обязательно")
    article = feed_service.mark_favorite(db, article_id, payload.is_favorite)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Публикация не найдена")
    return article
