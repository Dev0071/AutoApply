from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ApplicationStatus(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    running = "running"
    review = "review"
    submitted = "submitted"
    failed = "failed"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String)
    location: Mapped[Optional[str]] = mapped_column(String)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String)
    github_url: Mapped[Optional[str]] = mapped_column(String)
    skills: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    experience: Mapped[Optional[Dict]] = mapped_column(JSONB)
    fit_threshold: Mapped[int] = mapped_column(Integer, default=70)


class JobRecord(Base):
    __tablename__ = "job_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String)
    company: Mapped[Optional[str]] = mapped_column(String)
    raw_jd_text: Mapped[Optional[str]] = mapped_column(Text)
    keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    fit_score: Mapped[Optional[float]] = mapped_column(Float)
    ats_type: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ApplicationRun(Base):
    __tablename__ = "application_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_records.id"))
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.pending
    )
    steps: Mapped[Optional[List[Dict]]] = mapped_column(JSONB)
    cover_letter: Mapped[Optional[str]] = mapped_column(Text)
    bullets: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
