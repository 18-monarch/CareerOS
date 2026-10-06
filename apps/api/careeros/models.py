"""Relational ownership and identity; JSON is reserved for variable evidence/configuration."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from careeros.db import Base, utcnow


def uid():
    return str(uuid.uuid4())


class Entity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class User(Entity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(120))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)


class AuthSession(Entity, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    access_hash: Mapped[str] = mapped_column(String(64), unique=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    access_expires: Mapped[datetime] = mapped_column(DateTime)
    expires: Mapped[datetime] = mapped_column(DateTime)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[datetime] = mapped_column(DateTime)


class Profile(Entity, Base):
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    university: Mapped[str] = mapped_column(String(200), default="")
    degree: Mapped[str] = mapped_column(String(120), default="")
    branch: Mapped[str] = mapped_column(String(120), default="")
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    cgpa: Mapped[float | None] = mapped_column(Float)
    semester: Mapped[int | None] = mapped_column(Integer)
    experience_years: Mapped[float] = mapped_column(Float, default=0)
    work_authorizations: Mapped[list] = mapped_column(JSON, default=list)
    external_profiles: Mapped[dict] = mapped_column(JSON, default=dict)


class Preferences(Entity, Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Skill(Entity, Base):
    __tablename__ = "skills"
    name: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(80), default="Programming")


class UserSkill(Entity, Base):
    __tablename__ = "user_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"))
    skill: Mapped[Skill] = relationship(lazy="joined")
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Project(Entity, Base):
    __tablename__ = "projects"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class ProjectMastery(Entity, Base):
    __tablename__ = "project_mastery"
    __table_args__ = (UniqueConstraint("project_id", "topic"),)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    topic: Mapped[str] = mapped_column(String(120))
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Company(Entity, Base):
    __tablename__ = "companies"
    name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str] = mapped_column(String(160), unique=True)
    domain: Mapped[str | None] = mapped_column(String(255))


class Source(Entity, Base):
    __tablename__ = "job_sources"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Job(Entity, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "canonical_key"),
        Index("ix_jobs_owner_active_deadline", "user_id", "is_active", "application_deadline"),
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    company: Mapped[Company] = relationship(lazy="joined")
    canonical_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(240), index=True)
    normalized_role: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    employment_type: Mapped[str] = mapped_column(String(30), default="internship")
    country: Mapped[str] = mapped_column(String(80), default="Unknown")
    locations: Mapped[list] = mapped_column(JSON, default=list)
    remote_status: Mapped[str] = mapped_column(String(30), default="unknown")
    application_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str | None] = mapped_column(String(200))
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    requirements: Mapped["JobRequirement"] = relationship(
        cascade="all, delete-orphan", lazy="joined", uselist=False
    )
    skills: Mapped[list["JobSkill"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class JobRequirement(Entity, Base):
    __tablename__ = "job_requirements"
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class JobSkill(Base):
    __tablename__ = "job_skills"
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    skill: Mapped[Skill] = relationship(lazy="joined")
    required: Mapped[bool] = mapped_column(Boolean, default=True)


class Occurrence(Entity, Base):
    __tablename__ = "job_source_occurrences"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("job_sources.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    missing_runs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class MatchResult(Entity, Base):
    __tablename__ = "job_matches"
    __table_args__ = (UniqueConstraint("user_id", "job_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    data: Mapped[dict] = mapped_column(JSON)


class Application(Entity, Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "job_id"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    job: Mapped[Job] = relationship(lazy="joined")
    status: Mapped[str] = mapped_column(String(40), default="SAVED")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    events: Mapped[list["ApplicationEvent"]] = relationship(
        lazy="selectin", order_by="ApplicationEvent.created_at", cascade="all, delete-orphan"
    )


class ApplicationEvent(Entity, Base):
    __tablename__ = "application_events"
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(Text, default="")


class LearningProgress(Entity, Base):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("user_id", "topic"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(120))
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class DSALog(Entity, Base):
    __tablename__ = "dsa_logs"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(80))
    problem: Mapped[str] = mapped_column(String(200))
    independent: Mapped[bool] = mapped_column(Boolean)
    hint_required: Mapped[bool] = mapped_column(Boolean)
    could_explain: Mapped[bool] = mapped_column(Boolean)
    complexity_understood: Mapped[bool] = mapped_column(Boolean)


class Notification(Entity, Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(240))
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime)
    delivery_error: Mapped[str | None] = mapped_column(String(200))


class SourceRun(Entity, Base):
    __tablename__ = "source_health"
    source_id: Mapped[str] = mapped_column(
        ForeignKey("job_sources.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    added: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    closed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    parse_errors: Mapped[int] = mapped_column(Integer, default=0)
    runtime_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(200))


class MarketReport(Entity, Base):
    __tablename__ = "market_reports"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    market: Mapped[str] = mapped_column(String(80))
    period: Mapped[str] = mapped_column(String(7))
    data: Mapped[dict] = mapped_column(JSON)


class VisaRule(Entity, Base):
    __tablename__ = "visa_rules"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    country: Mapped[str] = mapped_column(String(80))
    last_verified: Mapped[datetime] = mapped_column(DateTime)
    data: Mapped[dict] = mapped_column(JSON)


class ResumeVersion(Entity, Base):
    __tablename__ = "resume_versions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    data: Mapped[dict] = mapped_column(JSON)


class AuditLog(Entity, Base):
    __tablename__ = "audit_logs"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str | None] = mapped_column(String(36))
