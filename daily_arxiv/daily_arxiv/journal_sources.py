"""Target journal source configuration and metadata helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import unescape
import re
from urllib.parse import quote, urlencode


TARGET_JOURNALS = [
    {
        "name": "Chaos: An Interdisciplinary Journal of Nonlinear Science",
        "aliases": ["Chaos"],
        "publisher": "AIP Publishing",
    },
    {
        "name": "Physica D: Nonlinear Phenomena",
        "aliases": ["Physica D"],
        "publisher": "Elsevier",
    },
    {
        "name": "SIAM Journal on Applied Dynamical Systems",
        "aliases": ["SIADS"],
        "publisher": "SIAM",
    },
    {
        "name": "Nonlinear Dynamics",
        "aliases": [],
        "publisher": "Springer Nature",
    },
    {
        "name": "Machine Learning: Science and Technology",
        "aliases": ["MLST"],
        "publisher": "IOP Publishing",
    },
    {
        "name": "Communications Physics",
        "aliases": [],
        "publisher": "Springer Nature",
    },
    {
        "name": "Entropy",
        "aliases": [],
        "publisher": "MDPI",
    },
    {
        "name": "Frontiers in Applied Mathematics and Statistics",
        "aliases": [],
        "publisher": "Frontiers",
    },
]

TARGET_JOURNAL_NAMES = [journal["name"] for journal in TARGET_JOURNALS]


def clean_text(value: object) -> str:
    if not value:
        return ""
    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(value).lower()).strip()


def is_target_journal(container_title: str) -> bool:
    normalized = normalize_title(container_title)
    if not normalized:
        return False
    for journal in TARGET_JOURNALS:
        names = [journal["name"], *journal.get("aliases", [])]
        for name in names:
            candidate = normalize_title(name)
            if normalized == candidate or candidate in normalized:
                return True
    return False


def journal_lookup(container_title: str) -> dict | None:
    normalized = normalize_title(container_title)
    for journal in TARGET_JOURNALS:
        names = [journal["name"], *journal.get("aliases", [])]
        for name in names:
            candidate = normalize_title(name)
            if normalized == candidate or candidate in normalized:
                return journal
    return None


def published_date_from_crossref(item: dict) -> str:
    for key in ("published-print", "published-online", "published", "created"):
        parts = item.get(key, {}).get("date-parts")
        if parts and parts[0]:
            date_parts = [str(part) for part in parts[0]]
            return "-".join(date_parts)
    return ""


def build_crossref_urls(limit_per_journal: int, lookback_days: int) -> list[tuple[str, str]]:
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date().isoformat()
    urls = []
    for journal in TARGET_JOURNALS:
        query = {
            "filter": f"from-pub-date:{since},type:journal-article",
            "query.container-title": journal["name"],
            "sort": "published",
            "order": "desc",
            "rows": str(limit_per_journal),
            "select": "DOI,title,author,container-title,abstract,URL,published,published-print,published-online,created",
        }
        urls.append((journal["name"], f"https://api.crossref.org/works?{urlencode(query)}"))
    return urls


def build_doaj_urls(limit_per_journal: int) -> list[tuple[str, str]]:
    urls = []
    for journal in TARGET_JOURNALS:
        query = quote(f'bibjson.journal.title:"{journal["name"]}"')
        urls.append((journal["name"], f"https://doaj.org/api/search/articles/{query}?page=1&pageSize={limit_per_journal}"))
    return urls

