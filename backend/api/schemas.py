from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class ProfileCreate(BaseModel):
    user_id: str
    name: str
    email: str
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: dict = Field(default_factory=dict)
    fit_threshold: int = 70


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    name: str
    email: str
    phone: str | None
    location: str | None
    linkedin_url: str | None
    github_url: str | None
    skills: list[str]
    experience: dict
    fit_threshold: int


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class JobAnalyzeRequest(BaseModel):
    url: str
    profile: ProfileCreate


class JobAnalyzeResponse(BaseModel):
    title: str | None
    company: str | None
    ats_type: str | None
    keywords: list[str]
    fit_score: float
    passes_threshold: bool
    cover_letter: str
    bullets: list[str]
    raw_jd_text: str


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

class ApplicationTriggerRequest(BaseModel):
    job_url: str
    user_id: str


class ApplicationTriggerResponse(BaseModel):
    run_id: str
    status: str
    message: str


class ApplicationStatusResponse(BaseModel):
    id: str
    status: str
    job_record_id: str | None
    steps: list[dict]
    cover_letter: str | None
    bullets: list[str]
    total_cost_usd: float | None = None
    created_at: str
    submitted_at: str | None


class ApplicationListItem(BaseModel):
    id: str
    status: str
    job_url: str | None
    job_title: str | None
    company: str | None
    fit_score: float | None
    created_at: str
