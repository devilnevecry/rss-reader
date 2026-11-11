"""Feed service: business logic for feeds and articles."""

from __future__ import annotations

import asyncio
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Article, Feed
from app.services.rss_parser import FeedParserError, fetch_and_parse_feed, record_feed_error, sync_feed_to_db


def get_feed(db: Session, feed_id: int) -> Optional[Feed]:
    return db.query(Feed).filter(Feed.id == feed_id).first()


def get_feed_by_url(db: Session, url: str) -> Optional[Feed]:
    return db.query(Feed).filter(Feed.url == url).first()


def get_feeds(db: Session) -> list[Feed]:
    return db.query(Feed).order_by(Feed.created_at.desc()).all()


def create_feed(db: Session, url: str) -> Feed:
    """Add a new feed by URL. Validates and parses the feed before persisting."""
    existing = get_feed_by_url(db, url)
    if existing:
        raise ValueError("Источник с таким URL уже добавлен.")

    try:
        parsed = asyncio.run(fetch_and_parse_feed(url))
    except FeedParserError as exc:
        raise ValueError(str(exc))

    feed = Feed(
        title=parsed["title"],
        url=url,
        description=parsed["description"],
    )
    db.add(feed)
    db.flush()
    sync_feed_to_db(db, feed, parsed)
    db.commit()
    db.refresh(feed)
    return feed


def delete_feed(db: Session, feed_id: int) -> bool:
    feed = get_feed(db, feed_id)
    if not feed:
        return False
    db.delete(feed)
    db.commit()
    return True


def refresh_feed(db: Session, feed_id: int) -> Feed:
    """Refresh a single feed from its URL."""
    feed = get_feed(db, feed_id)
    if not feed:
        raise ValueError("Источник не найден.")

    try:
        parsed = asyncio.run(fetch_and_parse_feed(feed.url))
    except FeedParserError as exc:
        record_feed_error(db, feed, str(exc))
        db.refresh(feed)
        return feed

    sync_feed_to_db(db, feed, parsed)
    db.commit()
    db.refresh(feed)
    return feed


def refresh_all_feeds(db: Session) -> list[Feed]:
    feeds = get_feeds(db)
    results = []
    for feed in feeds:
        try:
            results.append(refresh_feed(db, feed.id))
        except Exception:  # noqa: BLE001
            results.append(get_feed(db, feed.id) or feed)
    return results


def get_articles(
    db: Session,
    feed_id: Optional[int] = None,
    unread_only: bool = False,
    favorites_only: bool = False,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    query = db.query(Article).join(Feed)

    if feed_id is not None:
        query = query.filter(Article.feed_id == feed_id)
    if unread_only:
        query = query.filter(Article.is_read == False)  # noqa: E712
    if favorites_only:
        query = query.filter(Article.is_favorite == True)  # noqa: E712
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Article.title.ilike(like))
            | (Article.summary.ilike(like))
            | (Feed.title.ilike(like))
        )

    total = query.count()
    query = query.order_by(Article.published_at.desc().nullslast(), Article.created_at.desc())
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()
    return items, total


def get_article(db: Session, article_id: int) -> Optional[Article]:
    return db.query(Article).filter(Article.id == article_id).first()


def mark_read(db: Session, article_id: int, is_read: bool) -> Optional[Article]:
    article = get_article(db, article_id)
    if not article:
        return None
    article.is_read = is_read
    db.commit()
    db.refresh(article)
    return article


def mark_favorite(db: Session, article_id: int, is_favorite: bool) -> Optional[Article]:
    article = get_article(db, article_id)
    if not article:
        return None
    article.is_favorite = is_favorite
    db.commit()
    db.refresh(article)
    return article


def get_stats(db: Session) -> dict:
    total_feeds = db.query(Feed).count()
    total_articles = db.query(Article).count()
    unread = db.query(Article).filter(Article.is_read == False).count()  # noqa: E712
    favorites = db.query(Article).filter(Article.is_favorite == True).count()  # noqa: E712
    last_fetched = (
        db.query(Feed.last_fetched_at)
        .filter(Feed.last_fetched_at.is_not(None))
        .order_by(Feed.last_fetched_at.desc())
        .first()
    )
    return {
        "total_feeds": total_feeds,
        "total_articles": total_articles,
        "unread": unread,
        "favorites": favorites,
        "last_fetched_at": last_fetched[0] if last_fetched and last_fetched[0] else None,
    }
