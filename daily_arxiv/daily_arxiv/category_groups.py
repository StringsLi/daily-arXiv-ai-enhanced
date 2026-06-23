"""Map arXiv subject codes and paper text into five stable display groups."""

from __future__ import annotations

from collections import Counter


CATEGORY_ORDER = [
    "机器学习与数据科学",
    "优化控制与系统工程",
    "概率论与随机过程",
    "动力系统与微分方程",
    "数值计算与科学计算",
]

CATEGORY_CODE_MAP = {
    "机器学习与数据科学": {
        "cs.AI",
        "cs.CL",
        "cs.CV",
        "cs.LG",
        "cs.NE",
        "stat.ML",
        "stat.ME",
        "math.ST",
    },
    "优化控制与系统工程": {
        "cs.SY",
        "eess.SY",
        "eess.SP",
        "math.OC",
    },
    "概率论与随机过程": {
        "math.PR",
        "stat.TH",
        "q-fin.CP",
        "q-fin.MF",
        "q-fin.RM",
        "q-fin.ST",
    },
    "动力系统与微分方程": {
        "math.AP",
        "math.DS",
        "math.CA",
        "nlin.AO",
        "nlin.CD",
        "nlin.SI",
    },
    "数值计算与科学计算": {
        "cs.CE",
        "cs.MS",
        "cs.NA",
        "math.NA",
        "math.NT",
        "physics.comp-ph",
    },
}

CATEGORY_KEYWORDS = {
    "机器学习与数据科学": (
        "autoencoder",
        "data-driven",
        "deep learning",
        "learning",
        "machine learning",
        "neural",
        "statistical learning",
    ),
    "优化控制与系统工程": (
        "control",
        "controller",
        "optimization",
        "optimal",
        "system",
        "systems engineering",
    ),
    "概率论与随机过程": (
        "diffusion",
        "fokker-planck",
        "langevin",
        "markov",
        "probability",
        "stochastic",
    ),
    "动力系统与微分方程": (
        "differential equation",
        "dynamical",
        "dynamics",
        "koopman",
        "ode",
        "pde",
    ),
    "数值计算与科学计算": (
        "approximation",
        "computational",
        "finite element",
        "numerical",
        "pseudospectral",
        "simulation",
    ),
}


def _clean_categories(categories: object) -> list[str]:
    if isinstance(categories, str):
        return [categories]
    if isinstance(categories, (list, tuple, set)):
        return [str(category).strip() for category in categories if str(category).strip()]
    return []


def classify_paper(categories: object, title: str = "", summary: str = "") -> str:
    """Return one of the five configured display groups for a paper."""

    raw_categories = _clean_categories(categories)
    for category in raw_categories:
        if category in CATEGORY_ORDER:
            return category

    scores: Counter[str] = Counter()
    for category in raw_categories:
        for group, codes in CATEGORY_CODE_MAP.items():
            if category in codes:
                scores[group] += 3

    text = f"{title} {summary}".lower()
    for group, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[group] += 1

    if not scores:
        return CATEGORY_ORDER[-1]

    return max(CATEGORY_ORDER, key=lambda group: (scores[group], -CATEGORY_ORDER.index(group)))
