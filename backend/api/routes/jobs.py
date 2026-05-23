from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from anthropic import AsyncAnthropic

from backend.agents.fit_scorer import score_fit
from backend.agents.jd_miner import JDMiner
from backend.agents.tailoring_engine import TailoringEngine, TailoringError
from backend.api.dependencies import get_anthropic
from backend.api.schemas import JobAnalyzeRequest, JobAnalyzeResponse

log = structlog.get_logger()
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/analyze", response_model=JobAnalyzeResponse)
async def analyze_job(
    body: JobAnalyzeRequest,
    client: AsyncAnthropic = Depends(get_anthropic),
) -> JobAnalyzeResponse:
    """
    Stateless endpoint — fetches and analyzes a job URL.
    Returns fit score, tailored cover letter, and rewritten bullets.
    No database write; safe to call before committing to an application.
    """
    profile_dict = body.profile.model_dump()

    try:
        jd = await JDMiner(client).fetch(body.url)
    except Exception as exc:
        log.error("jd_fetch_failed", url=body.url, error=str(exc))
        raise HTTPException(status_code=422, detail=f"Failed to fetch job page: {exc}")

    fit_score = score_fit(profile_dict, jd.model_dump())
    passes = fit_score >= body.profile.fit_threshold

    cover_letter = ""
    bullets: list[str] = []

    if passes:
        try:
            engine = TailoringEngine(client)
            cl_result = await engine.generate_cover_letter(profile_dict, jd)
            b_result = await engine.rewrite_bullets(profile_dict, jd)
            cover_letter = cl_result.cover_letter
            bullets = b_result.bullets
        except TailoringError as exc:
            log.warning("tailoring_failed", error=str(exc))

    log.info(
        "job_analyzed",
        url=body.url,
        title=jd.title,
        fit_score=fit_score,
        passes=passes,
    )

    return JobAnalyzeResponse(
        title=jd.title,
        company=jd.company,
        ats_type=jd.ats_type,
        keywords=jd.keywords,
        fit_score=fit_score,
        passes_threshold=passes,
        cover_letter=cover_letter,
        bullets=bullets,
        raw_jd_text=jd.raw_jd_text[:2000],  # truncate for API response
    )
