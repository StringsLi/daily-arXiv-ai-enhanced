import json
import argparse
import os
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
    "cs.SY": "优化控制与系统工程",
    "eess.SY": "优化控制与系统工程",
    "eess.SP": "优化控制与系统工程",
    "math.OC": "优化控制与系统工程",
    "math.PR": "概率论与随机过程",
    "stat.TH": "概率论与随机过程",
    "math.AP": "动力系统与微分方程",
    "math.DS": "动力系统与微分方程",
    "nlin.AO": "动力系统与微分方程",
    "nlin.CD": "动力系统与微分方程",
    "nlin.SI": "动力系统与微分方程",
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
                        translated_summary=first_text(ai_data.get('translated_summary'), item.get('summary')),
                        url=item['abs'],
                        tldr=first_text(ai_data.get('tldr'), ai_data.get('translated_summary'), item.get('summary')),
                        motivation=first_text(ai_data.get('motivation')),
                        method=first_text(ai_data.get('method')),
                        result=first_text(ai_data.get('result')),
                        conclusion=first_text(ai_data.get('conclusion')),
                        cate=item['display_category'],
                        idx=next(idx)
                    )
                )
        markdown += "\n\n".join(papers)
    with open(args.data.split('_')[0] + '.md', "w", encoding="utf-8") as f:
        f.write(markdown)
