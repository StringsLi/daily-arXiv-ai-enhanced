# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import arxiv
from scrapy.exceptions import DropItem
import json
import os
import sys
from datetime import datetime, timedelta
from daily_arxiv.category_groups import classify_paper, is_relevant_topic
from daily_arxiv.free_fulltext import resolve_free_fulltext


class DailyArxivPipeline:
    def __init__(self):
        self.page_size = 100
        self.client = arxiv.Client(self.page_size)

    def process_item(self, item: dict, spider):
        if item.get("source_type") == "journal":
            return self.process_journal_item(item)
        return self.process_arxiv_item(item)

    def process_arxiv_item(self, item: dict):
        item["pdf"] = f"https://arxiv.org/pdf/{item['id']}"
        item["abs"] = f"https://arxiv.org/abs/{item['id']}"
        search = arxiv.Search(
            id_list=[item["id"]],
        )
        paper = next(self.client.results(search))
        item["authors"] = [a.name for a in paper.authors]
        item["title"] = paper.title
        item["comment"] = paper.comment
        item["summary"] = paper.summary
        item["raw_categories"] = paper.categories
        if not is_relevant_topic(paper.title, paper.summary, paper.categories):
            raise DropItem(f"Skipped arXiv paper outside target topic: {paper.title}")
        item["categories"] = [
            classify_paper(paper.categories, paper.title, paper.summary)
        ]
        item["source"] = item.get("source", "arxiv")
        item["source_type"] = item.get("source_type", "preprint")
        item["journal"] = item.get("journal", "")
        item["doi"] = item.get("doi", "")
        item["free_fulltext_sources"] = resolve_free_fulltext(
            title=item["title"],
            arxiv_id=item["id"],
            existing_abs=item["abs"],
            existing_pdf=item["pdf"],
            lookup_doaj=False,
        )["free_fulltext_sources"]
        return item

    def process_journal_item(self, item: dict):
        title = item.get("title", "")
        doi = item.get("doi", "")
        source_url = item.get("source_url", "")
        existing_sources = item.get("free_fulltext_sources", [])

        resolved = resolve_free_fulltext(
            title=title,
            doi=doi,
            source_url=source_url,
        )
        sources = []
        seen_urls = set()
        for source in [*existing_sources, *resolved["free_fulltext_sources"]]:
            url = source.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            sources.append(source)

        item["arxiv_id"] = resolved.get("arxiv_id", "")
        item["pdf"] = next((source["url"] for source in sources if source.get("kind") == "pdf"), resolved.get("pdf", ""))
        item["abs"] = resolved.get("abs") or source_url or (f"https://doi.org/{doi}" if doi else "")
        item["authors"] = item.get("authors") or []
        item["summary"] = item.get("summary", "")
        item["comment"] = item.get("comment", "")
        item["raw_categories"] = item.get("raw_categories", [item.get("journal", "")])
        if not is_relevant_topic(title, item["summary"], item["raw_categories"]):
            raise DropItem(f"Skipped journal paper outside target topic: {title}")
        item["categories"] = [
            classify_paper(item["raw_categories"], title, item["summary"])
        ]
        item["free_fulltext_sources"] = sources
        return item
