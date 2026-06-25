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
    '(ti:"data-driven" OR abs:"data-driven" OR ti:"data driven" OR abs:"data driven") AND (ti:dynamics OR abs:dynamics OR ti:dynamical OR abs:dynamical)',
    '(ti:learning OR abs:learning OR ti:neural OR abs:neural OR ti:"machine learning" OR abs:"machine learning") AND (ti:dynamics OR abs:dynamics OR ti:dynamical OR abs:dynamical)',
    '(ti:stochastic OR abs:stochastic) AND (ti:dynamics OR abs:dynamics OR ti:dynamical OR abs:dynamical)',
    '(ti:"stochastic differential" OR abs:"stochastic differential" OR ti:"neural sde" OR abs:"neural sde" OR ti:sde OR abs:sde)',
    '(ti:koopman OR abs:koopman OR ti:"transfer operator" OR abs:"transfer operator") AND (ti:learning OR abs:learning OR ti:"data-driven" OR abs:"data-driven")',
    '(ti:"operator learning" OR abs:"operator learning" OR ti:"neural operator" OR abs:"neural operator") AND (ti:dynamics OR abs:dynamics OR ti:dynamical OR abs:dynamical)',
    '(ti:"latent dynamics" OR abs:"latent dynamics" OR ti:"reduced order" OR abs:"reduced order") AND (ti:model OR abs:model OR ti:learning OR abs:learning)',
    '(ti:"fokker-planck" OR abs:"fokker-planck" OR ti:langevin OR abs:langevin OR ti:"markov process" OR abs:"markov process")',
    '(ti:"diffusion process" OR abs:"diffusion process" OR ti:"diffusion processes" OR abs:"diffusion processes") AND (ti:learning OR abs:learning OR ti:inference OR abs:inference OR ti:estimation OR abs:estimation)',
    '(ti:"rare event" OR abs:"rare event" OR ti:"first passage" OR abs:"first passage" OR ti:"mean exit" OR abs:"mean exit")',
    '(ti:"tipping point" OR abs:"tipping point" OR ti:"early warning" OR abs:"early warning" OR ti:"critical transition" OR abs:"critical transition")',
    '(ti:sindy OR abs:sindy OR ti:"sparse identification" OR abs:"sparse identification") AND (ti:dynamics OR abs:dynamics OR ti:stochastic OR abs:stochastic)',
    '(ti:"physics-informed" OR abs:"physics-informed" OR ti:pinn OR abs:pinn) AND (ti:stochastic OR abs:stochastic OR ti:dynamics OR abs:dynamics)',
    'cat:math.DS AND (abs:"data-driven" OR abs:learning OR abs:stochastic OR abs:koopman)',
    'cat:math.PR AND (abs:dynamics OR abs:dynamical OR abs:learning OR abs:inference)',
    'cat:cs.LG AND (abs:dynamics OR abs:dynamical OR abs:"stochastic differential" OR abs:koopman)',
    'cat:stat.ML AND (abs:dynamics OR abs:dynamical OR abs:stochastic OR abs:"state space")',
    'cat:physics.data-an AND (abs:dynamics OR abs:dynamical OR abs:stochastic OR abs:"time series")',
    'cat:nlin.CD AND (abs:data OR abs:learning OR abs:stochastic OR abs:inference)',
    'cat:physics.comp-ph AND (abs:"neural operator" OR abs:"operator learning" OR abs:surrogate OR abs:"reduced order")',
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
