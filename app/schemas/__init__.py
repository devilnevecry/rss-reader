"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


class FeedCreate(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def url_must_be_http_or_https(cls, v: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(v.strip())
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError("Разрешены только схемы HTTP и HTTPS")
        if not parsed.hostname:
            raise ValueError("URL должен содержать хост")
        return v.strip()


class FeedOut(BaseModel):
    id: int
    title: str
    url: str
    description: Optional[str] = None
    created_at: datetime
    last_fetched_at: Optional[datetime] = None
    last_error: Optional[str] = None

    model_config = {"from_attributes": True}


class ArticleOut(BaseModel):
    id: int
    feed_id: int
    feed_title: str
    guid: str
    title: str
    url: str
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    is_read: bool
    is_favorite: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ArticleUpdate(BaseModel):
    is_read: Optional[bool] = None
    is_favorite: Optional[bool] = None


class PaginatedArticles(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int
    pages: int


class StatsOut(BaseModel):
    total_feeds: int
    total_articles: int
    unread: int
    favorites: int
    last_fetched_at: Optional[datetime] = None


class ErrorOut(BaseModel):
    detail: str
