"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, engine
from app.api import feeds, articles, stats

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RSS Reader",
    description="Self-hosted RSS/Atom news aggregator",
    version="0.1.0",
)

app.include_router(feeds.router)
app.include_router(articles.router)
app.include_router(stats.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")
# Disable Jinja2 template cache: the environment cache key uses
# weakref.ref(loader), and FileSystemLoader is unhashable (defines __eq__),
# which raises TypeError: unhashable type: 'dict' on lookup.
templates.env.cache = None  # type: ignore[assignment]


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")
