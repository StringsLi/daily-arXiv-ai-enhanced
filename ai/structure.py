from pydantic import BaseModel, Field, field_validator
import re

class Structure(BaseModel):
    tldr: str = Field(description="generate a too long; didn't read summary")
    translated_summary: str = Field(description="translate the original abstract into the requested language")
    research_problem: str = Field(description="state the specific research problem addressed by this paper")
    key_innovation: str = Field(description="summarize the main novelty or contribution of this paper")
    motivation: str = Field(description="describe the motivation in this paper")
    method: str = Field(description="method of this paper")
    experiments: str = Field(description="describe experiments, evaluations, benchmarks, datasets, or theoretical validation")
    result: str = Field(description="result of this paper")
    conclusion: str = Field(description="conclusion of this paper")
    limitations: str = Field(description="state limitations or open questions; use an empty string if the abstract does not mention them")
