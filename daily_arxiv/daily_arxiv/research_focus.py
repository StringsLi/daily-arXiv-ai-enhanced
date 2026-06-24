"""Research focus defaults for data-driven and stochastic dynamics monitoring."""

from __future__ import annotations

from urllib.parse import urlencode


DEFAULT_ARXIV_CATEGORIES = [
    "math.DS",
    "math.PR",
    "math.OC",
    "math.NA",
    "math.AP",
    "cs.SY",
    "cs.LG",
    "stat.ML",
    "stat.ME",
    "physics.data-an",
    "physics.comp-ph",
    "nlin.AO",
    "nlin.CD",
    "nlin.SI",
    "q-bio.QM",
]

DEFAULT_SUPPLEMENTAL_ARXIV_QUERIES = [
    'all:"data-driven dynamics"',
    'all:"data driven dynamics"',
    'all:"data-driven dynamical systems"',
    'all:"stochastic dynamical systems"',
    'all:"stochastic dynamics"',
    'all:"stochastic differential equation"',
    'all:"stochastic differential equations"',
    'all:"learning stochastic dynamics"',
    'all:"neural SDE"',
    'all:"Koopman" AND all:"learning"',
    'all:"operator learning" AND all:"dynamics"',
    'all:"transfer operator" AND all:"dynamics"',
    'all:"latent dynamics"',
    'all:"reduced order model" AND all:"dynamics"',
    'all:"Fokker-Planck"',
    'all:"Langevin" AND all:"learning"',
]


def split_env_list(value: str | None) -> list[str]:
    if not value:
        return []
    separators = ["\n", ";"]
    normalized = value
    for separator in separators:
        normalized = normalized.replace(separator, ",")
    return [part.strip() for part in normalized.split(",") if part.strip()]


def build_arxiv_api_urls(
    queries: list[str],
    max_results: int,
) -> list[tuple[str, str]]:
    urls = []
    for query in queries:
        params = {
            "search_query": query,
            "start": "0",
            "max_results": str(max_results),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        urls.append((query, f"https://export.arxiv.org/api/query?{urlencode(params)}"))
    return urls
