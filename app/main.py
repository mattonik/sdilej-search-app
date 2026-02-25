from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .models import Category, LanguageScope, SortMode
from .sdilej_client import SdilejClient, SdilejClientError

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Sdilej Search Proxy", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

client = SdilejClient()

DEFAULT_CATEGORY: Category = "all"
DEFAULT_SORT: SortMode = "relevance"
DEFAULT_LANGUAGE_SCOPE: LanguageScope = "any"

CATEGORY_OPTIONS: list[tuple[str, Category]] = [
    ("All", "all"),
    ("Video", "video"),
    ("Audio", "audio"),
    ("Archive", "archive"),
    ("Image", "image"),
]

SORT_OPTIONS: list[tuple[str, SortMode]] = [
    ("Relevance", "relevance"),
    ("Most downloaded", "downloads"),
    ("Newest", "newest"),
    ("Largest", "size_desc"),
    ("Smallest", "size_asc"),
]

LANGUAGE_SCOPE_OPTIONS: list[tuple[str, LanguageScope]] = [
    ("Any language hint", "any"),
    ("Audio / dubbing focus", "audio"),
    ("Subtitles only", "subtitles"),
]


def _parse_optional_year(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None

    text = raw_value.strip()
    if not text:
        return None

    if not text.isdigit():
        raise SdilejClientError("release_year must be an integer between 1900 and 2099.")

    year = int(text)
    if year < 1900 or year > 2099:
        raise SdilejClientError("release_year must be an integer between 1900 and 2099.")

    return year


@app.get("/")
def index(
    request: Request,
    query: str = Query(default="", max_length=200),
    category: Category = Query(default=DEFAULT_CATEGORY),
    sort: SortMode = Query(default=DEFAULT_SORT),
    language: str = Query(default="", max_length=32),
    language_scope: LanguageScope = Query(default=DEFAULT_LANGUAGE_SCOPE),
    release_year: str = Query(default="", max_length=8),
    max_results: int = Query(default=120, ge=1, le=500),
):
    error: str | None = None
    search_response = None
    parsed_release_year: int | None = None

    if query.strip() or language.strip() or release_year.strip():
        try:
            parsed_release_year = _parse_optional_year(release_year)
            search_response = client.search(
                query=query,
                category=category,
                sort=sort,
                language=language,
                language_scope=language_scope,
                release_year=parsed_release_year,
                max_results=max_results,
            )
        except SdilejClientError as exc:
            error = str(exc)
        except Exception as exc:  # noqa: BLE001
            error = f"Unexpected search failure: {exc}"

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "query": query,
            "category": category,
            "sort": sort,
            "language": language,
            "language_scope": language_scope,
            "release_year": release_year,
            "parsed_release_year": parsed_release_year,
            "max_results": max_results,
            "error": error,
            "search": search_response,
            "category_options": CATEGORY_OPTIONS,
            "sort_options": SORT_OPTIONS,
            "language_scope_options": LANGUAGE_SCOPE_OPTIONS,
        },
    )


@app.get("/api/search")
def api_search(
    query: str = Query(default="", max_length=200),
    category: Category = Query(default=DEFAULT_CATEGORY),
    sort: SortMode = Query(default=DEFAULT_SORT),
    language: str = Query(default="", max_length=32),
    language_scope: LanguageScope = Query(default=DEFAULT_LANGUAGE_SCOPE),
    release_year: str = Query(default="", max_length=8),
    max_results: int = Query(default=120, ge=1, le=500),
):
    try:
        parsed_release_year = _parse_optional_year(release_year)
        result = client.search(
            query=query,
            category=category,
            sort=sort,
            language=language,
            language_scope=language_scope,
            release_year=parsed_release_year,
            max_results=max_results,
        )
        return JSONResponse(result.to_dict())
    except SdilejClientError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/autocomplete")
def api_autocomplete(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=30),
):
    try:
        suggestions = client.autocomplete(term=q, limit=limit)
        return JSONResponse({"q": q, "suggestions": suggestions})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/healthz")
def healthcheck():
    return {"status": "ok"}
