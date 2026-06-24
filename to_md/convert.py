import json
import argparse
import os
import re
from itertools import count

CATEGORY_ORDER = [
    "机器学习与数据科学",
    "优化控制与系统工程",
    "概率论与随机过程",
    "动力系统与微分方程",
    "数值计算与科学计算",
]

CATEGORY_ALIASES = {
    "cs.AI": "机器学习与数据科学",
    "cs.CL": "机器学习与数据科学",
    "cs.CV": "机器学习与数据科学",
    "cs.LG": "机器学习与数据科学",
    "cs.NE": "机器学习与数据科学",
    "stat.ML": "机器学习与数据科学",
    "stat.ME": "机器学习与数据科学",
    "math.ST": "机器学习与数据科学",
    "Machine Learning: Science and Technology": "机器学习与数据科学",
    "cs.SY": "优化控制与系统工程",
    "eess.SY": "优化控制与系统工程",
    "eess.SP": "优化控制与系统工程",
    "math.OC": "优化控制与系统工程",
    "math.PR": "概率论与随机过程",
    "stat.TH": "概率论与随机过程",
    "Entropy": "概率论与随机过程",
    "Frontiers in Applied Mathematics and Statistics": "概率论与随机过程",
    "math.AP": "动力系统与微分方程",
    "math.DS": "动力系统与微分方程",
    "nlin.AO": "动力系统与微分方程",
    "nlin.CD": "动力系统与微分方程",
    "nlin.SI": "动力系统与微分方程",
    "Chaos: An Interdisciplinary Journal of Nonlinear Science": "动力系统与微分方程",
    "Physica D: Nonlinear Phenomena": "动力系统与微分方程",
    "SIAM Journal on Applied Dynamical Systems": "动力系统与微分方程",
    "Nonlinear Dynamics": "动力系统与微分方程",
    "Communications Physics": "动力系统与微分方程",
    "cs.CE": "数值计算与科学计算",
    "cs.MS": "数值计算与科学计算",
    "cs.NA": "数值计算与科学计算",
    "math.NA": "数值计算与科学计算",
    "physics.comp-ph": "数值计算与科学计算",
}


def first_text(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def normalize_category(categories):
    if isinstance(categories, str):
        categories = [categories]
    if not categories:
        return CATEGORY_ORDER[-1]
    for category in categories:
        category = str(category).strip()
        if category in CATEGORY_ORDER:
            return category
        if category in CATEGORY_ALIASES:
            return CATEGORY_ALIASES[category]
    return CATEGORY_ORDER[-1]


def same_text(left, right):
    normalize = lambda value: " ".join(str(value or "").strip().lower().split())
    return bool(normalize(left)) and normalize(left) == normalize(right)


def compact_sentence(text, max_chars=60):
    text = " ".join(str(text or "").strip().split())
    if not text:
        return ""
    for part in re.split(r"(?<=[。！？!?\.])\s*", text):
        part = part.strip()
        if part and len(part) <= max_chars:
            return part
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


def display_tldr(ai_data, translated_summary, original_summary):
    tldr = first_text(ai_data.get("tldr"))
    if not tldr or same_text(tldr, translated_summary) or same_text(tldr, original_summary) or len(tldr) > 90:
        tldr = first_text(
            ai_data.get("conclusion"),
            ai_data.get("result"),
            ai_data.get("key_innovation"),
            ai_data.get("research_problem"),
        )
    return compact_sentence(tldr)

def format_free_fulltext(sources):
    if not isinstance(sources, list) or not sources:
        return ""
    parts = []
    for source in sources:
        provider = source.get("provider", "source")
        kind = source.get("kind", "link")
        url = source.get("url", "")
        if url:
            parts.append(f"[{provider} {kind}]({url})")
    return ", ".join(parts)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, help="Path to the jsonline file")
    args = parser.parse_args()
    data = []
    def rank(cate):
        if cate in CATEGORY_ORDER:
            return CATEGORY_ORDER.index(cate)
        else:
            return len(CATEGORY_ORDER)

    with open(args.data, "r", encoding="utf-8-sig") as f:
        for line in f:
            data.append(json.loads(line))

    for item in data:
        item["display_category"] = normalize_category(item.get("categories", []))

    categories = set([item["display_category"] for item in data])
    template = open("paper_template.md", "r", encoding="utf-8").read()
    categories = sorted(categories, key=rank)
    cnt = {cate: 0 for cate in categories}
    for item in data:
        if item["display_category"] not in cnt.keys():
            continue
        cnt[item["display_category"]] += 1

    markdown = f"<div id=toc></div>\n\n# Table of Contents\n\n"
    for idx, cate in enumerate(categories):
        markdown += f"- [{cate}](#{cate}) [Total: {cnt[cate]}]\n"

    idx = count(1)
    for cate in categories:
        markdown += f"\n\n<div id='{cate}'></div>\n\n"
        markdown += f"# {cate} [[Back]](#toc)\n\n"
        papers = []
        for item in data:
            if item["display_category"] == cate:
                ai_data = item.get('AI', {})
                if not isinstance(ai_data, dict):
                    ai_data = {}

                papers.append(
                    template.format(
                        title=item["title"],
                        authors=",".join(item["authors"]),
                        summary=item["summary"],
                        translated_summary=first_text(ai_data.get('translated_summary')),
                        url=item['abs'],
                        source=first_text(item.get('source'), item.get('source_type')),
                        journal=first_text(item.get('journal')),
                        doi=first_text(item.get('doi')),
                        free_fulltext=format_free_fulltext(item.get('free_fulltext_sources')),
                        tldr=display_tldr(ai_data, first_text(ai_data.get('translated_summary')), item.get('summary')),
                        research_problem=first_text(ai_data.get('research_problem')),
                        key_innovation=first_text(ai_data.get('key_innovation')),
                        motivation=first_text(ai_data.get('motivation')),
                        method=first_text(ai_data.get('method')),
                        experiments=first_text(ai_data.get('experiments')),
                        result=first_text(ai_data.get('result')),
                        conclusion=first_text(ai_data.get('conclusion')),
                        limitations=first_text(ai_data.get('limitations')),
                        cate=item['display_category'],
                        idx=next(idx)
                    )
                )
        markdown += "\n\n".join(papers)
    with open(args.data.split('_')[0] + '.md', "w", encoding="utf-8") as f:
        f.write(markdown)
