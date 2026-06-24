"""Topic filtering and display groups for data-driven stochastic dynamics papers."""

from __future__ import annotations

from collections import Counter
import re


SDE_IDENTIFICATION = "\u968f\u673a\u5fae\u5206\u65b9\u7a0b\u8bc6\u522b"
EFFECTIVE_MODELING = "\u6570\u636e\u9a71\u52a8\u6709\u6548\u52a8\u529b\u5b66/\u964d\u9636\u5efa\u6a21"
PREDICTION_WARNING = "\u968f\u673a\u7cfb\u7edf\u9884\u6d4b\u4e0e\u7a81\u53d8\u9884\u8b66"
APPLICATIONS = "\u5de5\u7a0b/\u91d1\u878d/\u751f\u7269/\u7535\u529b\u5e94\u7528"

CATEGORY_ORDER = [
    SDE_IDENTIFICATION,
    EFFECTIVE_MODELING,
    PREDICTION_WARNING,
    APPLICATIONS,
]

CATEGORY_CODE_MAP = {
    SDE_IDENTIFICATION: {
        "math.PR",
        "stat.ML",
        "math.ST",
        "cs.LG",
        "physics.data-an",
        "nlin.CD",
    },
    EFFECTIVE_MODELING: {
        "math.DS",
        "math.NA",
        "math.AP",
        "cs.LG",
        "stat.ML",
        "physics.comp-ph",
        "nlin.CD",
        "nlin.AO",
        "nlin.SI",
    },
    PREDICTION_WARNING: {
        "math.PR",
        "math.DS",
        "q-fin.RM",
        "q-fin.ST",
        "physics.ao-ph",
        "physics.soc-ph",
        "nlin.CD",
    },
    APPLICATIONS: {
        "cs.SY",
        "eess.SY",
        "q-fin.CP",
        "q-fin.MF",
        "q-fin.RM",
        "q-fin.ST",
        "q-bio.QM",
        "physics.app-ph",
        "physics.bio-ph",
        "physics.med-ph",
    },
}

CATEGORY_KEYWORDS = {
    SDE_IDENTIFICATION: (
        "data-driven discovery of stochastic differential equations",
        "stochastic differential equation discovery",
        "sparse identification stochastic",
        "sindy stochastic",
        "stochastic equation discovery",
        "sde discovery",
        "sde identification",
        "identify sde",
        "identified sde",
    ),
    EFFECTIVE_MODELING: (
        "data-driven effective modeling",
        "effective modeling multiscale stochastic",
        "reduced-order stochastic",
        "reduced order stochastic",
        "stochastic model reduction",
        "multiscale stochastic",
        "koopman operator stochastic",
        "koopman stochastic",
        "operator learning stochastic",
        "physics-informed neural networks stochastic",
        "physics-informed stochastic",
        "neural sde",
        "neural stochastic differential",
        "stochastic surrogate model",
        "stochastic surrogate modeling",
    ),
    PREDICTION_WARNING: (
        "data-driven tipping point",
        "stochastic tipping point",
        "tipping point stochastic",
        "early warning stochastic",
        "critical transition stochastic",
        "escape probability",
        "mean exit time",
        "first passage time",
        "rare event",
        "transition path stochastic",
        "stochastic stability",
        "stochastic systems prediction",
        "forecasting stochastic",
        "predicting stochastic",
    ),
    APPLICATIONS: (
        "power systems stochastic",
        "power system stochastic",
        "electric power stochastic",
        "smart grid stochastic",
        "financial stochastic",
        "finance stochastic",
        "biological stochastic",
        "biochemical stochastic",
        "climate stochastic",
        "fault diagnosis stochastic",
        "engineering stochastic",
        "energy system stochastic",
        "epidemic stochastic",
        "neuroscience stochastic",
    ),
}

DATA_KEYWORDS = (
    "data-driven",
    "data driven",
    "machine learning",
    "deep learning",
    "learning-based",
    "neural network",
    "neural networks",
    "deep neural",
    "physics-informed",
    "operator learning",
    "koopman",
    "sindy",
    "sparse identification",
    "discovery",
    "identification",
)

STOCHASTIC_KEYWORDS = (
    "stochastic",
    "random dynamical",
    "stochastic differential",
    " sde",
    "sdes",
    "diffusion process",
    "diffusion model",
    "langevin",
    "fokker-planck",
    "markov",
    "noise-induced",
    "uncertainty quantification",
    "escape probability",
    "mean exit time",
    "first passage time",
    "rare event",
    "tipping point",
)

DYNAMICS_KEYWORDS = (
    "dynamical",
    "dynamics",
    "differential equation",
    "differential equations",
    " sde",
    "sdes",
    "bsde",
    "bsdes",
    "stochastic differential",
    "diffusion process",
    "langevin",
    "fokker-planck",
    "markov process",
    "multiscale stochastic",
    "tipping point",
    "escape probability",
    "mean exit time",
)

APPLICATION_KEYWORDS = (
    "power systems",
    "power system",
    "electric power",
    "smart grid",
    "financial",
    "finance",
    "biological",
    "biochemical",
    "climate",
    "fault diagnosis",
    "engineering",
    "energy system",
    "epidemic",
    "neuroscience",
)

STRONG_TOPIC_PHRASES = tuple(
    sorted(
        {
            phrase
            for group, phrases in CATEGORY_KEYWORDS.items()
            for phrase in phrases
            if group != APPLICATIONS
        }
        | {
            "data-driven stochastic dynamical systems",
            "data-driven stochastic dynamics",
            "stochastic dynamical systems data-driven",
            "data driven stochastic dynamical systems",
            "data-driven discovery of stochastic differential equations",
            "sparse identification stochastic dynamical systems",
            "koopman operator stochastic dynamics",
            "physics-informed neural networks stochastic dynamical systems",
            "neural sde dynamical systems",
        },
        key=len,
        reverse=True,
    )
)


def _clean_categories(categories: object) -> list[str]:
    if isinstance(categories, str):
        return [categories]
    if isinstance(categories, (list, tuple, set)):
        return [str(category).strip() for category in categories if str(category).strip()]
    return []


def _normalize_text(*parts: object) -> str:
    text = " ".join(str(part or "") for part in parts)
    for dash in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"):
        text = text.replace(dash, "-")
    text = re.sub(r"[^a-z0-9+./-]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _contains(text: str, phrase: str) -> bool:
    phrase = _normalize_text(phrase)
    if len(phrase) <= 4 and phrase.isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text))
    return phrase in text


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains(text, phrase) for phrase in phrases)


def is_relevant_topic(title: str = "", summary: str = "", categories: object = None) -> bool:
    """Return True for papers in the requested data-driven stochastic dynamics scope."""

    text = _normalize_text(title, summary, " ".join(_clean_categories(categories)))
    if not text:
        return False

    if _has_any(text, STRONG_TOPIC_PHRASES):
        return True

    has_data_signal = _has_any(text, DATA_KEYWORDS)
    has_stochastic_signal = _has_any(text, STOCHASTIC_KEYWORDS)
    has_dynamics_signal = _has_any(text, DYNAMICS_KEYWORDS)
    has_application_signal = _has_any(text, APPLICATION_KEYWORDS)

    if has_data_signal and has_stochastic_signal and has_dynamics_signal:
        return True

    return has_application_signal and has_data_signal and has_stochastic_signal and has_dynamics_signal


def classify_paper(categories: object, title: str = "", summary: str = "") -> str:
    """Return one of the four configured display groups for a paper."""

    raw_categories = _clean_categories(categories)
    for category in raw_categories:
        if category in CATEGORY_ORDER:
            return category

    scores: Counter[str] = Counter()
    for category in raw_categories:
        for group, codes in CATEGORY_CODE_MAP.items():
            if category in codes:
                scores[group] += 1

    text = _normalize_text(title, summary)
    for group, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if _contains(text, keyword):
                scores[group] += 3

    for application_keyword in APPLICATION_KEYWORDS:
        if _contains(text, application_keyword):
            scores[APPLICATIONS] += 2

    for group, codes in CATEGORY_CODE_MAP.items():
        if any(category in codes for category in raw_categories):
            scores[group] += 1

    if not scores:
        return CATEGORY_ORDER[0]

    return max(CATEGORY_ORDER, key=lambda group: (scores[group], -CATEGORY_ORDER.index(group)))
