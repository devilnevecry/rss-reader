"""Tests for the RSS reader application."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Article, Feed
from app.services.rss_parser import (
    _validate_url,
    _is_blocked_host,
    parse_feed_xml,
    FeedParserError,
)
import app.services.feed_service as feed_service_mod


# --- Test database setup ---

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/test_rss_reader.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- RSS sample data ---

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Example RSS</title>
  <description>Test RSS feed</description>
  <item>
    <title>First Item</title>
    <link>https://example.com/item1</link>
    <guid>https://example.com/item1</guid>
    <description>Summary of first item</description>
    <pubDate>Wed, 02 Oct 2024 08:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Second Item</title>
    <link>https://example.com/item2</link>
    <guid>item2-guid</guid>
    <description>Summary of second item</description>
  </item>
</channel>
</rss>"""

ATOM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Atom</title>
  <subtitle>Test Atom feed</subtitle>
  <entry>
    <title>Atom Entry</title>
    <id>urn:uuid:60a76c80-d399-11d9-b93C-0003939e0af6</id>
    <link href="https://example.com/atom1"/>
    <summary>Atom summary</summary>
    <updated>2024-10-02T08:00:00Z</updated>
  </entry>
</feed>"""

INVALID_XML = "this is not xml at all"


async def _fake_fetch_success(url):
    return {
        "title": "Test Feed",
        "description": "desc",
        "entries": [
            {
                "guid": "guid-1",
                "title": "Article 1",
                "url": "https://example.com/a1",
                "summary": "summary 1",
                "published_at": datetime(2024, 10, 2, 8, 0, tzinfo=timezone.utc),
            }
        ],
    }


async def _fake_fetch_empty(url):
    return {"title": "Test Feed", "description": "desc", "entries": []}


async def _fake_fetch_raise(url):
    raise FeedParserError("Некорректный XML ленты")


# --- RSS parser tests ---

def test_validate_url_http_allowed():
    assert _validate_url("https://example.com/feed") == "https://example.com/feed"
    assert _validate_url("http://example.com/feed") == "http://example.com/feed"


def test_validate_url_blocked_schemes():
    with pytest.raises(FeedParserError):
        _validate_url("ftp://example.com/feed")
    with pytest.raises(FeedParserError):
        _validate_url("file:///etc/passwd")


def test_is_blocked_host_localhost():
    assert _is_blocked_host("localhost") is True
    assert _is_blocked_host("127.0.0.1") is True


def test_parse_rss_feed():
    parsed = parse_feed_xml(RSS_SAMPLE, "https://example.com/feed")
    assert parsed["title"] == "Example RSS"
    assert len(parsed["entries"]) == 2
    assert parsed["entries"][0]["title"] == "First Item"
    assert parsed["entries"][0]["url"] == "https://example.com/item1"
    assert parsed["entries"][0]["guid"] == "https://example.com/item1"


def test_parse_atom_feed():
    parsed = parse_feed_xml(ATOM_SAMPLE, "https://example.com/atom")
    assert parsed["title"] == "Example Atom"
    assert len(parsed["entries"]) == 1
    assert parsed["entries"][0]["title"] == "Atom Entry"


def test_parse_invalid_xml():
    with pytest.raises(FeedParserError):
        parse_feed_xml(INVALID_XML, "https://example.com/feed")


# --- Service tests ---

def test_create_feed_parses_and_saves(db, monkeypatch):
    monkeypatch.setattr(feed_service_mod, "fetch_and_parse_feed", _fake_fetch_success)
    feed = feed_service_mod.create_feed(db, "https://example.com/feed")
    assert feed.id is not None
    assert feed.title == "Test Feed"
    articles = db.query(Article).filter(Article.feed_id == feed.id).all()
    assert len(articles) == 1
    assert articles[0].title == "Article 1"


def test_create_feed_duplicate_url(db, monkeypatch):
    monkeypatch.setattr(feed_service_mod, "fetch_and_parse_feed", _fake_fetch_empty)
    feed_service_mod.create_feed(db, "https://example.com/feed")
    with pytest.raises(ValueError, match="уже добавлен"):
        feed_service_mod.create_feed(db, "https://example.com/feed")


def test_prevents_duplicates_on_refresh(db, monkeypatch):
    monkeypatch.setattr(feed_service_mod, "fetch_and_parse_feed", _fake_fetch_success)
    feed = feed_service_mod.create_feed(db, "https://example.com/feed")
    assert db.query(Article).count() == 1
    feed_service_mod.refresh_feed(db, feed.id)
    assert db.query(Article).count() == 1


def test_read_status_persistence(db, monkeypatch):
    monkeypatch.setattr(feed_service_mod, "fetch_and_parse_feed", _fake_fetch_success)
    feed = feed_service_mod.create_feed(db, "https://example.com/feed")
    article = db.query(Article).first()
    assert article.is_read is False
    updated = feed_service_mod.mark_read(db, article.id, True)
    assert updated.is_read is True
    article2 = db.query(Article).get(article.id)
    assert article2.is_read is True


def test_filters_and_search(db, monkeypatch):
    async def fake_fetch_multi(url):
        return {
            "title": "Test Feed",
            "description": "desc",
            "entries": [
                {
                    "guid": "guid-1",
                    "title": "Python News",
                    "url": "https://example.com/1",
                    "summary": "About python",
                    "published_at": None,
                },
                {
                    "guid": "guid-2",
                    "title": "Rust News",
                    "url": "https://example.com/2",
                    "summary": "About rust",
                    "published_at": None,
                },
            ],
        }

    monkeypatch.setattr(feed_service_mod, "fetch_and_parse_feed", fake_fetch_multi)
    feed = feed_service_mod.create_feed(db, "https://example.com/feed")
    items, total = feed_service_mod.get_articles(db, search="python")
    assert total == 1
    assert items[0].title == "Python News"


# --- API tests ---

def test_api_list_feeds_empty(client):
    response = client.get("/api/feeds")
    assert response.status_code == 200
    assert response.json() == []


def test_api_add_and_list_feed(client, monkeypatch):
    monkeypatch.setattr(feed_service_mod, "fetch_and_parse_feed", _fake_fetch_empty)
    response = client.post("/api/feeds", json={"url": "https://example.com/feed"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Feed"

    response = client.get("/api/feeds")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_api_add_feed_invalid_xml(client, monkeypatch):
    monkeypatch.setattr(feed_service_mod, "fetch_and_parse_feed", _fake_fetch_raise)
    response = client.post("/api/feeds", json={"url": "https://example.com/bad"})
    assert response.status_code == 400


def test_api_list_articles(client, monkeypatch, db):
    monkeypatch.setattr(feed_service_mod, "fetch_and_parse_feed", _fake_fetch_success)
    client.post("/api/feeds", json={"url": "https://example.com/feed"})

    response = client.get("/api/articles")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Article 1"


def test_api_mark_read(client, monkeypatch, db):
    monkeypatch.setattr(feed_service_mod, "fetch_and_parse_feed", _fake_fetch_success)
    client.post("/api/feeds", json={"url": "https://example.com/feed"})
    article_id = db.query(Article).first().id

    response = client.post(f"/api/articles/{article_id}/read", json={"is_read": True})
    assert response.status_code == 200
    assert response.json()["is_read"] is True

    response = client.post(f"/api/articles/{article_id}/read", json={"is_read": False})
    assert response.json()["is_read"] is False


def test_api_stats(client):
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_feeds" in data
    assert "total_articles" in data
    assert "unread" in data
    assert "favorites" in data
