from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

OpportunityKind = Literal[
    "grant",
    "fellowship",
    "award",
    "prize",
    "scholarship",
    "tender",
    "accelerator",
    "eoi",
    "cfp",
]


class OpportunityCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    official_source_url: HttpUrl
    opportunity_type: OpportunityKind
    funder_name: str = Field(default="", max_length=200)
    programme_name: str = Field(default="", max_length=200)
    source_description: str = Field(default="", max_length=4000)
    deadline_text: str = Field(default="", max_length=200)
    rolling: bool = False
