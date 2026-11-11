"""RSS/Atom feed parser service with SSRF protection."""

from __future__ import annotations

import asyncio
import ipaddress
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import feedparser
import httpx

from app.database import SessionLocal
from app.models import Article, Feed


# Maximum number of bytes to download from a feed URL.
MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024  # 2 MB

# HTTP timeout for feed requests in seconds.
REQUEST_TIMEOUT = 15.0

# Allowed schemes only.
ALLOWED_SCHEMES = {"http", "https"}

# Maximum number of redirects to follow.
MAX_REDIRECTS = 5


class FeedParserError(Exception):
    """Raised when a feed cannot be fetched or parsed."""


def _is_blocked_host(hostname: str) -> bool:
    """Return True if the hostname points to a forbidden/private address."""
    if not hostname:
        return True
    try:
        infos = __import__("socket").getaddrinfo(hostname, None)
    except OSError:
        return True

    for _family, _type, _proto, _canonname, sockaddr in infos:
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_loopback or ip.is_private or ip.is_reserved or ip.is_unspecified or ip.is_multicast:
            return True
    return False


def _validate_url(url: str) -> str:
    """Validate the scheme and host of a feed URL. Returns the normalized URL."""
    try:
        parsed = urlparse(url.strip())
    except Exception as exc:  # noqa: BLE001
        raise FeedParserError(f"Некорректный URL: {url}") from exc

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise FeedParserError(f"Неподдерживаемая схема URL: {parsed.scheme}. Разрешены только HTTP и HTTPS.")

    if not parsed.hostname:
        raise FeedParserError(f"URL не содержит хоста: {url}")

    if _is_blocked_host(parsed.hostname):
        raise FeedParserError(f"Доступ к хосту запрещен по соображениям безопасности: {parsed.hostname}")

    return url.strip()


async def _fetch_feed_content(url: str) -> str:
    """Download feed content with size and redirect limits."""
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT),
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
        headers={"User-Agent": "RSS-Reader/0.1 (+https://example.com)"},
    )
    try:
        response = await client.get(url)
        response.raise_for_status()

        content = response.content
        if len(content) > MAX_DOWNLOAD_BYTES:
            raise FeedParserError("Превышен максимальный размер загружаемой ленты (2 МБ).")

        content_type = response.headers.get("content-type", "")
        if not any(token in content_type.lower() for token in ("xml", "rss", "atom", "feed")):
            # Still try to parse; some servers misreport content-type.
            pass

        return content.decode(response.encoding or "utf-8", errors="replace")
    except httpx.HTTPStatusError as exc:
        raise FeedParserError(f"Сервер вернул ошибку {exc.response.status_code} при загрузке ленты.") from exc
    except httpx.TooManyRedirects as exc:
        raise FeedParserError("Слишком много перенаправлений.") from exc
    except httpx.ConnectError as exc:
        raise FeedParserError(f"Не удалось подключиться к источнику: {url}") from exc
    except httpx.TimeoutException as exc:
        raise FeedParserError(f"Таймаут при загрузке ленты: {url}") from exc
    except httpx.RequestError as exc:
        raise FeedParserError(f"Ошибка загрузки ленты: {exc}") from exc
    finally:
        await client.aclose()


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    """Parse an RFC 2822 / ISO 8601 date string into a timezone-aware UTC datetime."""
    if not value:
        return None
    try:
        parsed = feedparser._parse_date(value)  # type: ignore[attr-defined]
    except Exception:
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_guid(entry: dict, fallback_url: str) -> str:
    """Extract a stable identifier for an entry, falling back to its URL."""
    for key in ("id", "guid", "link"):
        value = entry.get(key)
        if value:
            return str(value)
    return fallback_url


def parse_feed_xml(xml_content: str, source_url: str) -> dict:
    """Parse raw feed XML into a normalized dict."""
    bozo_exception = None
    try:
        parsed = feedparser.parse(xml_content)
    except Exception as exc:  # noqa: BLE001
        bozo_exception = exc
        parsed = None

    if parsed is None or (getattr(parsed, "bozo", False) and not parsed.entries):
        detail = getattr(bozo_exception, "message", str(bozo_exception)) if bozo_exception else "неизвестная ошибка"
        raise FeedParserError(f"Невозможно разобрать XML ленты: {detail}")

    feed_meta = parsed.feed or {}
    title = feed_meta.get("title") or feed_meta.get("subtitle") or "Без названия"
    description = feed_meta.get("description") or feed_meta.get("subtitle") or ""

    entries = []
    for entry in parsed.entries:
        guid = _extract_guid(entry, entry.get("link", ""))
        title_entry = entry.get("title") or "Без названия"
        link = entry.get("link") or ""
        summary = entry.get("summary") or entry.get("description") or ""
        published = _parse_date(entry.get("published") or entry.get("updated") or entry.get("created"))

        entries.append(
            {
                "guid": guid,
                "title": title_entry,
                "url": link,
                "summary": summary,
                "published_at": published,
            }
        )

    return {"title": title, "description": description, "entries": entries}


async def fetch_and_parse_feed(url: str) -> dict:
    """Validate, fetch, and parse a feed URL. Returns normalized feed data."""
    validated_url = _validate_url(url)
    xml_content = await _fetch_feed_content(validated_url)
    return parse_feed_xml(xml_content, validated_url)


def sync_feed_to_db(db, feed: Feed, parsed: dict) -> int:
    """Merge parsed feed entries into the database, preserving read/favorite status.
    Returns the number of newly added articles."""
    feed.title = parsed["title"]
    feed.description = parsed["description"]
    feed.last_fetched_at = datetime.now(timezone.utc)
    feed.last_error = None
    db.add(feed)
    db.flush()

    existing_guids = {
        row.guid for row in db.query(Article.guid).filter(Article.feed_id == feed.id).all()
    }

    new_count = 0
    for entry in parsed["entries"]:
        guid = entry["guid"]
        if guid in existing_guids:
            continue
        article = Article(
            feed_id=feed.id,
            guid=guid,
            title=entry["title"],
            url=entry["url"],
            summary=entry["summary"],
            published_at=entry["published_at"],
            is_read=False,
            is_favorite=False,
        )
        db.add(article)
        existing_guids.add(guid)
        new_count += 1

    return new_count


def record_feed_error(db, feed: Feed, error_message: str) -> None:
    """Record a fetch/parse error on a feed without crashing."""
    feed.last_error = error_message
    db.add(feed)
    db.commit()
