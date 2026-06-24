import json
import os
import re

import scrapy

from daily_arxiv.category_groups import is_relevant_topic
from daily_arxiv.journal_sources import (
    TARGET_JOURNAL_NAMES,
    build_crossref_urls,
    build_doaj_urls,
    clean_text,
    is_target_journal,
    journal_lookup,
    published_date_from_crossref,
)
from daily_arxiv.research_focus import (
    DEFAULT_ARXIV_CATEGORIES,
    DEFAULT_SUPPLEMENTAL_ARXIV_QUERIES,
    build_arxiv_api_urls,
    split_env_list,
)


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.lower() not in {"0", "false", "no"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


class ArxivSpider(scrapy.Spider):
    name = "arxiv"
    allowed_domains = ["arxiv.org", "export.arxiv.org", "api.crossref.org", "doaj.org"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configured_categories = split_env_list(os.environ.get("CATEGORIES"))
        additional_categories = split_env_list(os.environ.get("ADDITIONAL_ARXIV_CATEGORIES"))
        categories = [
            *DEFAULT_ARXIV_CATEGORIES,
            *configured_categories,
            *additional_categories,
        ]
        self.target_categories = {category.strip() for category in categories if category.strip()}
        self.start_urls = [f"https://arxiv.org/list/{cat}/new" for cat in self.target_categories]

        self.enable_journal_sources = _env_bool("ENABLE_JOURNAL_SOURCES", True)
        self.journal_limit = _env_int("JOURNAL_SOURCE_LIMIT", 20)
        self.journal_lookback_days = _env_int("JOURNAL_LOOKBACK_DAYS", 365)
        self.enable_supplemental_arxiv_queries = _env_bool("ENABLE_SUPPLEMENTAL_ARXIV_QUERIES", True)
        self.supplemental_query_limit = _env_int("SUPPLEMENTAL_ARXIV_QUERY_LIMIT", 10)
        self.supplemental_queries = (
            split_env_list(os.environ.get("SUPPLEMENTAL_ARXIV_QUERIES"))
            or DEFAULT_SUPPLEMENTAL_ARXIV_QUERIES
        )
        self.max_papers = _env_int("MAX_PAPERS", 0)
        self.yielded_papers = 0
        self.seen_arxiv_ids = set()

    def should_yield_paper(self) -> bool:
        if self.max_papers <= 0:
            return True
        if self.yielded_papers >= self.max_papers:
            return False
        self.yielded_papers += 1
        return True

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)

        if self.enable_supplemental_arxiv_queries:
            self.logger.info(
                "Supplemental arXiv queries enabled: %s queries; per-query limit=%s",
                len(self.supplemental_queries),
                self.supplemental_query_limit,
            )
            for query, url in build_arxiv_api_urls(self.supplemental_queries, self.supplemental_query_limit):
                yield scrapy.Request(
                    url,
                    callback=self.parse_arxiv_api,
                    cb_kwargs={"query": query},
                    dont_filter=True,
                )

        if not self.enable_journal_sources:
            return

        self.logger.info(
            "Journal sources enabled: %s; lookback=%s days; per-journal limit=%s",
            ", ".join(TARGET_JOURNAL_NAMES),
            self.journal_lookback_days,
            self.journal_limit,
        )
        for journal, url in build_crossref_urls(self.journal_limit, self.journal_lookback_days):
            yield scrapy.Request(
                url,
                callback=self.parse_crossref,
                cb_kwargs={"expected_journal": journal},
                dont_filter=True,
            )
        for journal, url in build_doaj_urls(self.journal_limit):
            yield scrapy.Request(
                url,
                callback=self.parse_doaj,
                cb_kwargs={"expected_journal": journal},
                dont_filter=True,
            )

    def parse(self, response):
        anchors = []
        for li in response.css("div[id=dlpage] ul li"):
            href = li.css("a::attr(href)").get()
            if href and "item" in href:
                anchors.append(int(href.split("item")[-1]))

        for paper in response.css("dl dt"):
            paper_anchor = paper.css("a[name^='item']::attr(name)").get()
            if not paper_anchor:
                continue

            paper_id = int(paper_anchor.split("item")[-1])
            if anchors and paper_id >= anchors[-1]:
                continue

            abstract_link = paper.css("a[title='Abstract']::attr(href)").get()
            if not abstract_link:
                continue

            arxiv_id = abstract_link.split("/")[-1]
            paper_dd = paper.xpath("following-sibling::dd[1]")
            if not paper_dd:
                continue

            subjects_text = paper_dd.css(".list-subjects .primary-subject::text").get()
            if not subjects_text:
                subjects_text = paper_dd.css(".list-subjects::text").get()

            if subjects_text:
                categories_in_paper = re.findall(r"\(([^)]+)\)", subjects_text)
                paper_categories = set(categories_in_paper)
                if paper_categories.intersection(self.target_categories):
                    item = self.build_arxiv_item(arxiv_id, list(paper_categories), "category list")
                    if item:
                        yield item
                        self.logger.info("Found arXiv paper %s with categories %s", arxiv_id, paper_categories)
                else:
                    self.logger.debug(
                        "Skipped arXiv paper %s with categories %s (target %s)",
                        arxiv_id,
                        paper_categories,
                        self.target_categories,
                    )
            else:
                self.logger.warning("Could not extract categories for arXiv paper %s; including anyway", arxiv_id)
                item = self.build_arxiv_item(arxiv_id, [], "category list")
                if item:
                    yield item

    def parse_arxiv_api(self, response, query: str):
        for entry in response.xpath("//*[local-name()='entry']"):
            id_url = entry.xpath("*[local-name()='id']/text()").get()
            if not id_url:
                continue
            arxiv_id = id_url.rstrip("/").split("/abs/")[-1]
            categories = entry.xpath("*[local-name()='category']/@term").getall()
            title = clean_text(entry.xpath("*[local-name()='title']/text()").get())
            summary = clean_text(entry.xpath("*[local-name()='summary']/text()").get())
            if not is_relevant_topic(title, summary, categories):
                self.logger.debug("Skipped arXiv API paper outside target topic: %s", title)
                continue
            item = self.build_arxiv_item(arxiv_id, categories, f"supplemental query: {query}")
            if item:
                yield item

    def build_arxiv_item(self, arxiv_id: str, categories: list[str], reason: str):
        arxiv_id = arxiv_id.strip()
        if not arxiv_id or arxiv_id in self.seen_arxiv_ids:
            return None
        if not self.should_yield_paper():
            return None
        self.seen_arxiv_ids.add(arxiv_id)
        return {
            "id": arxiv_id,
            "source": "arxiv",
            "source_type": "preprint",
            "categories": categories,
            "collection_reason": reason,
        }

    def parse_crossref(self, response, expected_journal: str):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            self.logger.warning("Failed to parse Crossref response for %s: %s", expected_journal, exc)
            return

        for entry in payload.get("message", {}).get("items", []):
            title = clean_text((entry.get("title") or [""])[0])
            journal = clean_text((entry.get("container-title") or [expected_journal])[0])
            if not title or not is_target_journal(journal):
                continue

            doi = clean_text(entry.get("DOI", ""))
            authors = []
            for author in entry.get("author", []):
                name = " ".join(
                    part for part in [author.get("given", ""), author.get("family", "")] if part
                ).strip()
                if name:
                    authors.append(name)

            journal_info = journal_lookup(journal) or {"name": journal}
            abstract = clean_text(entry.get("abstract", ""))
            if not is_relevant_topic(title, abstract, [journal_info["name"]]):
                self.logger.debug("Skipped Crossref article outside target topic: %s", title)
                continue
            if not abstract:
                abstract = f"{title}. Published in {journal_info['name']}."

            if not self.should_yield_paper():
                return
            yield {
                "id": f"doi:{doi.lower()}" if doi else f"journal:{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80]}",
                "source": "crossref",
                "source_type": "journal",
                "journal": journal_info["name"],
                "doi": doi,
                "source_url": entry.get("URL", ""),
                "title": title,
                "authors": authors,
                "summary": abstract,
                "comment": f"Journal source: {journal_info['name']}",
                "published_date": published_date_from_crossref(entry),
                "raw_categories": [journal_info["name"]],
            }

    def parse_doaj(self, response, expected_journal: str):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            self.logger.warning("Failed to parse DOAJ response for %s: %s", expected_journal, exc)
            return

        for result in payload.get("results", []):
            bibjson = result.get("bibjson", {})
            title = clean_text(bibjson.get("title", ""))
            journal = clean_text(bibjson.get("journal", {}).get("title", expected_journal))
            if not title or not is_target_journal(journal):
                continue

            doi = ""
            for identifier in bibjson.get("identifier", []):
                if identifier.get("type", "").lower() == "doi":
                    doi = identifier.get("id", "")
                    break

            authors = [clean_text(author.get("name", "")) for author in bibjson.get("author", [])]
            authors = [author for author in authors if author]
            abstracts = bibjson.get("abstract", [])
            abstract = clean_text(abstracts[0] if isinstance(abstracts, list) and abstracts else abstracts)
            journal_info = journal_lookup(journal) or {"name": journal}
            if not is_relevant_topic(title, abstract, [journal_info["name"]]):
                self.logger.debug("Skipped DOAJ article outside target topic: %s", title)
                continue
            if not abstract:
                abstract = f"{title}. Published in {journal}."

            fulltext_sources = []
            for link in bibjson.get("link", []):
                url = link.get("url", "")
                if not url:
                    continue
                kind = "pdf" if "pdf" in (link.get("type") or "").lower() or url.lower().endswith(".pdf") else "fulltext"
                fulltext_sources.append({"provider": "DOAJ", "kind": kind, "url": url})

            if not self.should_yield_paper():
                return
            yield {
                "id": f"doi:{doi.lower()}" if doi else f"doaj:{result.get('id', title)}",
                "source": "doaj",
                "source_type": "journal",
                "journal": journal_info["name"],
                "doi": doi,
                "source_url": result.get("id", ""),
                "title": title,
                "authors": authors,
                "summary": abstract,
                "comment": f"DOAJ source: {journal_info['name']}",
                "published_date": clean_text(bibjson.get("year", "")),
                "raw_categories": [journal_info["name"]],
                "free_fulltext_sources": fulltext_sources,
            }
