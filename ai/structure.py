from pydantic import BaseModel, Field


class Structure(BaseModel):
    tldr: str = Field(
        description=(
            "A very short TL;DR in the requested language. If the language is Chinese, "
            "write one Simplified Chinese sentence, ideally 20-35 Chinese characters and no more than 60 Chinese characters. "
            "It must be much shorter than translated_summary and must not copy translated_summary."
        )
    )
    translated_summary: str = Field(
        description=(
            "A faithful full translation of the original abstract into the requested language. "
            "If the language is Chinese, write Simplified Chinese, not English, and preserve the abstract's meaning."
        )
    )
    research_problem: str = Field(description="state the specific research problem addressed by this paper in the requested language")
    key_innovation: str = Field(description="summarize the main novelty or contribution of this paper in the requested language")
    motivation: str = Field(description="describe the motivation in this paper in the requested language")
    method: str = Field(description="method of this paper in the requested language")
    experiments: str = Field(description="describe experiments, evaluations, benchmarks, datasets, or theoretical validation in the requested language")
    result: str = Field(description="result of this paper in the requested language")
    conclusion: str = Field(description="conclusion of this paper in the requested language")
    limitations: str = Field(description="state limitations or open questions in the requested language; use an empty string if the abstract does not mention them")