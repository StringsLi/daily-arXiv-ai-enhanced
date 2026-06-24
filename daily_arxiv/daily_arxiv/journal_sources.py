"""Target journal source configuration and metadata helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import unescape
import re
from urllib.parse import quote, urlencode


TARGET_JOURNALS = [
    {
        "name": "SIAM Journal on Applied Dynamical Systems",
        "aliases": ["SIADS"],
        "publisher": "SIAM",
    },
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
        "name": "Nonlinear Dynamics",
        "aliases": [],
        "publisher": "Springer Nature",
    },
    {
        "name": "Proceedings of the Royal Society A: Mathematical, Physical and Engineering Sciences",
        "aliases": ["Proceedings of the Royal Society A", "Proc. R. Soc. A"],
        "publisher": "The Royal Society",
    },
    {
        "name": "Philosophical Transactions of the Royal Society A: Mathematical, Physical and Engineering Sciences",
        "aliases": ["Philosophical Transactions A", "Phil. Trans. R. Soc. A"],
        "publisher": "The Royal Society",
    },
    {
        "name": "Physical Review E",
        "aliases": ["Phys. Rev. E", "PRE"],
        "publisher": "American Physical Society",
    },
    {
        "name": "Journal of Computational Physics",
        "aliases": ["J. Comput. Phys."],
        "publisher": "Elsevier",
    },
    {
        "name": "Applied Mathematics and Computation",
        "aliases": [],
        "publisher": "Elsevier",
    },
    {
        "name": "Communications in Nonlinear Science and Numerical Simulation",
        "aliases": ["CNSNS"],
        "publisher": "Elsevier",
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
        "aliases": ["Entropy (Basel)"],
        "publisher": "MDPI",
    },
    {
        "name": "Mathematics",
        "aliases": ["Mathematics (Basel)"],
        "publisher": "MDPI",
    },
    {
        "name": "Frontiers in Applied Mathematics and Statistics",
        "aliases": [],
        "publisher": "Frontiers",
    },
    {
        "name": "Journal of Computational Dynamics",
        "aliases": [],
        "publisher": "AIMS Press",
    },
    {
        "name": "AIMS Mathematics",
        "aliases": [],
        "publisher": "AIMS Press",
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


def _journal_name_matches(normalized: str, candidate: str) -> bool:
    if normalized == candidate:
        return True
    return len(candidate) >= 12 and candidate in normalized


def is_target_journal(container_title: str) -> bool:
    normalized = normalize_title(container_title)
    if not normalized:
        return False
    for journal in TARGET_JOURNALS:
        names = [journal["name"], *journal.get("aliases", [])]
        for name in names:
            candidate = normalize_title(name)
            if _journal_name_matches(normalized, candidate):
                return True
    return False


def journal_lookup(container_title: str) -> dict | None:
    normalized = normalize_title(container_title)
    for journal in TARGET_JOURNALS:
        names = [journal["name"], *journal.get("aliases", [])]
        for name in names:
            candidate = normalize_title(name)
            if _journal_name_matches(normalized, candidate):
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

