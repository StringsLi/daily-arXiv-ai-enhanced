"""Resolve free full-text candidates from arXiv, DOAJ, and Scholar search."""

from __future__ import annotations

from difflib import SequenceMatcher
import json
import sys
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from daily_arxiv.journal_sources import clean_text, normalize_title


def google_scholar_url(title: str, doi: str = "") -> str:
    query = f"{title} {doi} free full text pdf".strip()
    return f"https://scholar.google.com/scholar?{urlencode({'q': query})}"


def doi_url(doi: str) -> str:
    return f"https://doi.org/{doi}" if doi else ""


def _json_get(url: str, timeout: int = 10) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "daily-arxiv-ai-enhanced/1.0 (free-fulltext-resolver)",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _append_source(sources: list[dict], source: dict) -> None:
    url = source.get("url")
    if not url:
        return
    if any(existing.get("url") == url for existing in sources):
        return
    sources.append(source)


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def find_arxiv_preprint(title: str) -> dict | None:
    if not title:
        return None
    try:
        import arxiv

        search = arxiv.Search(
            query=f'ti:"{title}"',
            max_results=3,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        client = arxiv.Client(page_size=3, delay_seconds=3, num_retries=1)
        for result in client.results(search):
            if _title_similarity(title, result.title) >= 0.82:
                arxiv_id = result.entry_id.rsplit("/", 1)[-1]
                return {
                    "id": arxiv_id,
                    "abs": f"https://arxiv.org/abs/{arxiv_id}",
                    "pdf": f"https://arxiv.org/pdf/{arxiv_id}",
                    "title": result.title,
                }
    except Exception as exc:
        print(f"arXiv title lookup failed for '{title}': {exc}", file=sys.stderr)
    return None


def find_doaj_fulltext(title: str, doi: str = "") -> list[dict]:
    if not title and not doi:
        return []
    query = quote_plus(doi or title)
    url = f"https://doaj.org/api/search/articles/{query}?page=1&pageSize=3"
    sources: list[dict] = []
    try:
        payload = _json_get(url)
    except Exception as exc:
        print(f"DOAJ lookup failed for '{title or doi}': {exc}", file=sys.stderr)
        return sources

    for result in payload.get("results", []):
        bibjson = result.get("bibjson", {})
        result_title = clean_text(bibjson.get("title", ""))
        result_doi = ""
        for identifier in bibjson.get("identifier", []):
            if identifier.get("type", "").lower() == "doi":
                result_doi = identifier.get("id", "")

        if doi and result_doi and result_doi.lower() != doi.lower():
            continue
        if title and result_title and _title_similarity(title, result_title) < 0.75:
            continue

        for link in bibjson.get("link", []):
            link_url = link.get("url")
            if not link_url:
                continue
            link_type = (link.get("type") or "").lower()
            _append_source(
                sources,
                {
                    "provider": "DOAJ",
                    "kind": "pdf" if "pdf" in link_type or link_url.lower().endswith(".pdf") else "fulltext",
                    "url": link_url,
                },
            )
    return sources


def resolve_free_fulltext(
    title: str,
    doi: str = "",
    arxiv_id: str = "",
    existing_abs: str = "",
    existing_pdf: str = "",
    source_url: str = "",
    lookup_doaj: bool = True,
) -> dict:
    sources: list[dict] = []

    if arxiv_id:
        _append_source(sources, {"provider": "arXiv", "kind": "abstract", "url": existing_abs or f"https://arxiv.org/abs/{arxiv_id}"})
        _append_source(sources, {"provider": "arXiv", "kind": "pdf", "url": existing_pdf or f"https://arxiv.org/pdf/{arxiv_id}"})
    else:
        preprint = find_arxiv_preprint(title)
        if preprint:
            arxiv_id = preprint["id"]
            _append_source(sources, {"provider": "arXiv", "kind": "abstract", "url": preprint["abs"]})
            _append_source(sources, {"provider": "arXiv", "kind": "pdf", "url": preprint["pdf"]})

    if lookup_doaj:
        for source in find_doaj_fulltext(title, doi):
            _append_source(sources, source)

    if doi:
        _append_source(sources, {"provider": "Publisher", "kind": "doi", "url": doi_url(doi)})
    elif source_url:
        _append_source(sources, {"provider": "Publisher", "kind": "landing", "url": source_url})

    _append_source(
        sources,
        {
            "provider": "Google Scholar",
            "kind": "search",
            "url": google_scholar_url(title, doi),
        },
    )

    pdf = next((source["url"] for source in sources if source.get("kind") == "pdf"), existing_pdf or "")
    landing = next((source["url"] for source in sources if source.get("kind") in {"abstract", "fulltext", "doi", "landing"}), existing_abs or source_url or "")

    return {
        "arxiv_id": arxiv_id,
        "pdf": pdf,
        "abs": landing,
        "free_fulltext_sources": sources,
    }
