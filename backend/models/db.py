from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    cv_raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    cv_parsed_json: Mapped[str] = mapped_column(Text, nullable=False)
    cv_filename: Mapped[str] = mapped_column(Text, nullable=False)
    cv_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parse_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    chunks: Mapped[list["CvChunk"]] = relationship(
        "CvChunk", back_populates="profile", cascade="all, delete-orphan"
    )
    preferences: Mapped["ProfilePreferences | None"] = relationship(
        "ProfilePreferences", back_populates="profile", uselist=False, cascade="all, delete-orphan"
    )
    embedding_runs: Mapped[list["EmbeddingRun"]] = relationship(
        "EmbeddingRun", back_populates="profile"
    )
    generation_results: Mapped[list["GenerationResult"]] = relationship(
        "GenerationResult", back_populates="profile"
    )
    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="profile"
    )


class CvChunk(Base):
    __tablename__ = "cv_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # stored as BLOB via bytes
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    profile: Mapped["Profile"] = relationship("Profile", back_populates="chunks")


class ProfilePreferences(Base):
    __tablename__ = "profile_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    target_roles: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    target_locations: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    remote_preference: Mapped[str] = mapped_column(Text, nullable=False, default="any")
    salary_min_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company_size_pref: Mapped[str] = mapped_column(Text, nullable=False, default="any")
    industries_to_avoid: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    skills_to_grow: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    tone_preference: Mapped[str] = mapped_column(Text, nullable=False, default="professional")
    cover_letter_length: Mapped[str] = mapped_column(Text, nullable=False, default="medium")
    seniority_target: Mapped[str] = mapped_column(Text, nullable=False, default="senior")
    notice_period_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    open_to_contract: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    profile: Mapped["Profile"] = relationship("Profile", back_populates="preferences")


class EmbeddingRun(Base):
    __tablename__ = "embedding_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False
    )
    chunks_created: Mapped[int] = mapped_column(Integer, nullable=False)
    model_used: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    profile: Mapped["Profile"] = relationship("Profile", back_populates="embedding_runs")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    remote_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_clean: Mapped[str] = mapped_column(Text, nullable=False)
    skills_required: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    skills_preferred: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ats_keywords: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    seniority: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    extraction_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    hashes: Mapped[list["JobHash"]] = relationship("JobHash", back_populates="job")
    generation_results: Mapped[list["GenerationResult"]] = relationship(
        "GenerationResult", back_populates="job"
    )
    applications: Mapped[list["Application"]] = relationship("Application", back_populates="job")


class JobHash(Base):
    __tablename__ = "job_hashes"

    hash: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str] = mapped_column(Text, ForeignKey("jobs.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    job: Mapped["Job"] = relationship("Job", back_populates="hashes")


class GenerationResult(Base):
    __tablename__ = "generation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(Text, ForeignKey("jobs.id"), nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), nullable=False)
    gap_analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    resume_json: Mapped[str] = mapped_column(Text, nullable=False)
    cover_letter_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunks_used: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ats_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ats_matched: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ats_missing: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    total_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    resume_edited_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_edited: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    job: Mapped["Job"] = relationship("Job", back_populates="generation_results")
    profile: Mapped["Profile"] = relationship("Profile", back_populates="generation_results")
    document_snapshots: Mapped[list["DocumentSnapshot"]] = relationship(
        "DocumentSnapshot", back_populates="generation_result"
    )
    applications: Mapped[list["Application"]] = relationship(
        "Application", back_populates="generation_result"
    )
    generation_logs: Mapped[list["GenerationLog"]] = relationship(
        "GenerationLog", back_populates="generation_result"
    )
    review_logs: Mapped[list["ReviewLog"]] = relationship(
        "ReviewLog", back_populates="generation_result"
    )


class DocumentSnapshot(Base):
    __tablename__ = "document_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generation_results.id"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    generation_result: Mapped["GenerationResult"] = relationship(
        "GenerationResult", back_populates="document_snapshots"
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(Text, ForeignKey("jobs.id"), nullable=False)
    generation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generation_results.id"), nullable=False
    )
    company: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    resume_snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_snapshots.id"), nullable=False
    )
    cl_snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("document_snapshots.id"), nullable=False
    )

    profile: Mapped["Profile"] = relationship("Profile", back_populates="applications")
    job: Mapped["Job"] = relationship("Job", back_populates="applications")
    generation_result: Mapped["GenerationResult"] = relationship(
        "GenerationResult", back_populates="applications"
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class StartupLog(Base):
    __tablename__ = "startup_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    db_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    vec_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    api_key_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    app_version: Mapped[str] = mapped_column(Text, nullable=False)


class ParseLog(Base):
    __tablename__ = "parse_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str | None] = mapped_column(Text, ForeignKey("jobs.id"), nullable=True)
    raw_length_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    clean_length_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    extraction_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    was_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class GenerationLog(Base):
    __tablename__ = "generation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generation_results.id"), nullable=False
    )
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[str] = mapped_column(Text, nullable=False)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hard_gap_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunks_retrieved: Mapped[int] = mapped_column(Integer, nullable=False)
    rag_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    gap_analysis_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    resume_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cover_letter_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    total_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    resume_was_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cover_letter_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    generation_result: Mapped["GenerationResult"] = relationship(
        "GenerationResult", back_populates="generation_logs"
    )


class ReviewLog(Base):
    __tablename__ = "review_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generation_results.id"), nullable=False
    )
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    time_to_approve_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resume_edit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cl_edit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downloaded_resume: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    downloaded_cl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    generation_result: Mapped["GenerationResult"] = relationship(
        "GenerationResult", back_populates="review_logs"
    )
