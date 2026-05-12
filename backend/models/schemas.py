import json as _json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── AI output schemas (used as format= targets for Ollama structured outputs) ─

class CvExperience(BaseModel):
    title: str
    company: str
    start_date: str
    end_date: str
    description: str
    skills_used: list[str]


class CvSkills(BaseModel):
    technical: list[str]
    tools: list[str]
    soft: list[str]


class CvEducation(BaseModel):
    degree: str
    institution: str
    year: str | None


class CvExtracted(BaseModel):
    full_name: str
    email: str | None
    location: str | None
    summary: str | None
    total_years_experience: float | None
    experiences: list[CvExperience]
    skills: CvSkills
    education: list[CvEducation]
    certifications: list[str]
    languages: list[str]


class JdExtracted(BaseModel):
    title: str
    company: str
    location: str | None
    remote_type: str
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    seniority: str
    skills_required: list[str]
    skills_preferred: list[str]
    ats_keywords: list[str]
    posted_date: str | None
    description_summary: str


class ReframeOpportunity(BaseModel):
    gap: str
    reframe: str


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    db: str
    version: str


class SettingsResponse(BaseModel):
    active_profile_id: int | None
    app_version: str


class SettingsPatch(BaseModel):
    active_profile_id: int


# ── Profiles ──────────────────────────────────────────────────────────────────

class ProfileCreateResponse(BaseModel):
    id: int
    name: str
    status: str


class ProfileStatusResponse(BaseModel):
    id: int
    status: str


class ProfileListItem(BaseModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileDetail(BaseModel):
    id: int
    name: str
    cv_parsed_json: str
    preferences: "PreferencesResponse | None"
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfilePatch(BaseModel):
    name: str


class ActivateProfileResponse(BaseModel):
    active_profile_id: int


# ── Preferences ───────────────────────────────────────────────────────────────

class PreferencesResponse(BaseModel):
    id: int
    profile_id: int
    target_roles: list[str]
    target_locations: list[str]
    remote_preference: str
    salary_min_eur: int | None
    company_size_pref: str
    industries_to_avoid: list[str]
    skills_to_grow: list[str]
    tone_preference: str
    cover_letter_length: str
    seniority_target: str
    notice_period_weeks: int
    open_to_contract: bool
    extra_context: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("target_roles", "target_locations", "industries_to_avoid", "skills_to_grow", mode="before")
    @classmethod
    def parse_json_list(cls, v: Any) -> list[str]:
        """Deserialise JSON-encoded list strings coming from the ORM layer."""
        if isinstance(v, str):
            try:
                parsed = _json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (_json.JSONDecodeError, ValueError):
                return []
        return v


class PreferencesUpdate(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    remote_preference: str = "any"
    salary_min_eur: int | None = None
    company_size_pref: str = "any"
    industries_to_avoid: list[str] = Field(default_factory=list)
    skills_to_grow: list[str] = Field(default_factory=list)
    tone_preference: str = "professional"
    cover_letter_length: str = "medium"
    seniority_target: str = "senior"
    notice_period_weeks: int = 4
    open_to_contract: bool = False
    extra_context: str | None = None


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobPasteRequest(BaseModel):
    text: str
    profile_id: int


class JobPasteResponse(BaseModel):
    job_id: str
    title: str
    company: str
    location: str | None
    remote_type: str | None
    seniority: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    skills_required: list[str]
    skills_preferred: list[str]
    ats_keywords: list[str]
    description_summary: str
    already_applied: bool
    duplicate_of: str | None


class JobListItem(BaseModel):
    id: str
    title: str
    company: str
    location: str | None
    fetched_at: datetime

    model_config = {"from_attributes": True}


class JobDetail(BaseModel):
    id: str
    title: str
    company: str
    location: str | None
    remote_type: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    description_clean: str
    skills_required: list[str]
    skills_preferred: list[str]
    ats_keywords: list[str]
    seniority: str | None
    posted_date: str | None
    fetched_at: datetime
    extraction_ok: bool

    model_config = {"from_attributes": True}


# ── Generate ──────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    job_id: str
    profile_id: int


class GenerateStartResponse(BaseModel):
    generation_id: int
    status: str


class GenerationStatusResponse(BaseModel):
    generation_id: int
    status: str
    step: str | None
    error: str | None


class GapAnalysis(BaseModel):
    match_score: int
    matched_skills: list[str]
    soft_gaps: list[str]
    hard_gaps: list[str]
    strengths_to_emphasise: list[str]
    reframe_opportunities: list[ReframeOpportunity]
    strategy: str
    red_flags: list[str]


class ResumeExperience(BaseModel):
    title: str
    company: str
    dates: str
    bullets: list[str]


class ResumeSkills(BaseModel):
    technical: list[str]
    tools: list[str]


class ResumeEducation(BaseModel):
    degree: str
    institution: str
    year: str | None


class ResumeJson(BaseModel):
    full_name: str
    contact: str
    summary: str
    experiences: list[ResumeExperience]
    skills: ResumeSkills
    education: list[ResumeEducation]


class AtsResult(BaseModel):
    score: int
    matched: list[str]
    missing: list[str]
    total_keywords: int


class GenerationDetailResponse(BaseModel):
    generation_id: int
    job_id: str
    gap_analysis: GapAnalysis
    resume: ResumeJson
    cover_letter: str
    ats: AtsResult
    created_at: datetime


class ResumeEditRequest(BaseModel):
    resume_edited_json: dict[str, Any]


class CoverLetterEditRequest(BaseModel):
    cover_letter_edited: str


class ApproveResponse(BaseModel):
    application_id: int
    resume_snapshot_id: int
    cl_snapshot_id: int
    applied_at: datetime


# ── Tracker ───────────────────────────────────────────────────────────────────

class ApplicationListItem(BaseModel):
    id: int
    company: str
    role: str
    location: str | None
    applied_at: datetime
    resume_snapshot_id: int
    cl_snapshot_id: int

    model_config = {"from_attributes": True}


class TrackerResponse(BaseModel):
    total: int
    applications: list[ApplicationListItem]


class ErrorResponse(BaseModel):
    error: str
    message: str
