from __future__ import annotations
from pydantic import BaseModel, Field


class JDResult(BaseModel):
    url: str
    title: str | None = None
    company: str | None = None
    raw_jd_text: str
    keywords: list[str] = Field(default_factory=list)
    ats_type: str | None = None  # "greenhouse" | "lever" | "workday" | "ashby" | "unknown"


class TailoringResult(BaseModel):
    cover_letter: str
    bullets: list[str]
