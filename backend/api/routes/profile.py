from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db
from backend.api.schemas import ProfileCreate, ProfileResponse
from backend.db.models import UserProfile

log = structlog.get_logger()
router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("", response_model=ProfileResponse, status_code=201)
async def create_profile(
    body: ProfileCreate,
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == body.user_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        for field, value in body.model_dump(exclude={"user_id"}).items():
            setattr(existing, field, value)
        profile = existing
    else:
        profile = UserProfile(id=uuid.uuid4(), **body.model_dump())
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    log.info("profile_upserted", user_id=body.user_id)
    return _to_response(profile)


@router.get("/{user_id}", response_model=ProfileResponse)
async def get_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _to_response(profile)


def _to_response(p: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        id=str(p.id),
        user_id=p.user_id,
        name=p.name,
        email=p.email,
        phone=p.phone,
        location=p.location,
        linkedin_url=p.linkedin_url,
        github_url=p.github_url,
        skills=p.skills or [],
        experience=p.experience or {},
        fit_threshold=p.fit_threshold,
    )
