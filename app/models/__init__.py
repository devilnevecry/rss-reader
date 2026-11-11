"""SQLAlchemy ORM models for the RSS reader application."""

import datetime as _dt
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime, default=_dt.datetime.utcnow, nullable=False
    )
    last_fetched_at: Mapped[Optional[_dt.datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    articles: Mapped[list["Article"]] = relationship(
        "Article", back_populates="feed", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Feed(id={self.id}, title={self.title!r})>"


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    feed_id: Mapped[int] = mapped_column(ForeignKey("feeds.id", ondelete="CASCADE"), nullable=False, index=True)
    guid: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[_dt.datetime]] = mapped_column(DateTime, nullable=True, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[_dt.datetime] = mapped_column(DateTime, default=_dt.datetime.utcnow, nullable=False)

    feed: Mapped["Feed"] = relationship("Feed", back_populates="articles")

    @property
    def feed_title(self) -> str:
        return self.feed.title if self.feed else ""

    __table_args__ = (
        UniqueConstraint("feed_id", "guid", name="uq_feed_guid"),
        Index("ix_articles_feed_published", "feed_id", "published_at"),
        Index("ix_articles_read_favorite", "is_read", "is_favorite"),
    )

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title={self.title!r})>"
