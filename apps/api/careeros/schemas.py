from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


def safe_url(value):
    if value in (None, ""):
        return None
    u = urlsplit(value)
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        raise ValueError("Use an http(s) URL without embedded credentials")
    return value


class Credentials(Schema):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(default="CareerOS user", min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()


class PasswordChange(Schema):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


DEFAULT_WEIGHTS = {
    "skill_fit": 30,
    "role_preference": 20,
    "project_evidence": 15,
    "graduation_fit": 10,
    "location_preference": 10,
    "experience_fit": 5,
    "company_preference": 5,
    "urgency": 5,
}


class PreferenceIn(Schema):
    target_roles: list[str] = Field(
        default_factory=lambda: ["Software Engineer", "Backend Engineer", "Full-Stack Engineer"],
        max_length=20,
    )
    countries: list[str] = Field(
        default_factory=lambda: ["India", "Germany", "Netherlands", "Ireland", "Singapore", "UAE"],
        max_length=30,
    )
    watchlist: list[str] = Field(default_factory=lambda: ["UK", "Australia", "USA"], max_length=30)
    preferred_companies: list[str] = Field(default_factory=list, max_length=100)
    deadline_days: list[int] = Field(default_factory=lambda: [7, 3, 1], max_length=10)
    email_enabled: bool = False
    weights: dict[str, float] = Field(default_factory=lambda: DEFAULT_WEIGHTS.copy())
    weekly_plan: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def validate_configuration(self):
        if (
            set(self.weights) != set(DEFAULT_WEIGHTS)
            or any(v < 0 or v > 100 for v in self.weights.values())
            or abs(sum(self.weights.values()) - 100) > 0.001
        ):
            raise ValueError("Weights must contain all eight factors and sum to 100")
        if any(d < 0 or d > 60 for d in self.deadline_days):
            raise ValueError("Deadline warning days must be between 0 and 60")
        return self


class ProfileIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    university: str = Field(default="", max_length=200)
    degree: str = Field(default="", max_length=120)
    branch: str = Field(default="", max_length=120)
    graduation_year: int | None = Field(default=None, ge=1980, le=2100)
    cgpa: float | None = Field(default=None, ge=0, le=10)
    semester: int | None = Field(default=None, ge=1, le=20)
    experience_years: float = Field(default=0, ge=0, le=60)
    work_authorizations: list[str] = Field(default_factory=list, max_length=50)
    external_profiles: dict[str, str] = Field(default_factory=dict, max_length=10)
    preferences: PreferenceIn = Field(default_factory=PreferenceIn)

    @field_validator("external_profiles")
    @classmethod
    def check_links(cls, value):
        for url in value.values():
            safe_url(url)
        return value


class SkillIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="Programming", max_length=80)
    proficiency: int = Field(default=1, ge=0, le=5)
    confidence: int = Field(default=1, ge=0, le=5)
    evidence: str = Field(default="", max_length=3000)
    last_used: str | None = Field(default=None, max_length=40)
    learning_status: Literal["NOT_STARTED", "LEARNING", "COMFORTABLE", "STRONG"] = "LEARNING"


class ProjectIn(Schema):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    repository_url: str | None = None
    live_url: str | None = None
    technologies: list[str] = Field(default_factory=list, max_length=50)
    verified_skills: list[str] = Field(default_factory=list, max_length=50)
    interview_readiness: str = Field(default="NOT_STARTED", max_length=80)
    _urls = field_validator("repository_url", "live_url")(safe_url)


class MasteryIn(Schema):
    topic: str = Field(min_length=1, max_length=120)
    status: Literal["NOT_STARTED", "LEARNING", "COMFORTABLE", "STRONG"]
    confidence: int = Field(default=1, ge=0, le=5)
    notes: str = Field(default="", max_length=5000)
    linked_skills: list[str] = Field(default_factory=list, max_length=30)


class Requirements(Schema):
    minimum_experience: float | None = Field(default=None, ge=0, le=60)
    maximum_experience: float | None = Field(default=None, ge=0, le=60)
    graduation_year_min: int | None = Field(default=None, ge=1980, le=2100)
    graduation_year_max: int | None = Field(default=None, ge=1980, le=2100)
    allowed_graduation_years: list[int] = Field(default_factory=list, max_length=30)
    degree_requirements: list[str] = Field(default_factory=list, max_length=30)
    branch_requirements: list[str] = Field(default_factory=list, max_length=30)
    minimum_cgpa: float | None = Field(default=None, ge=0, le=10)
    visa_sponsorship: bool | None = None
    work_authorization: str | None = Field(default=None, max_length=120)
    international_candidates_allowed: bool | None = None
    language_requirement: str | None = Field(default=None, max_length=120)
    graduate_eligibility: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def ranges(self):
        for lo, hi in [
            (self.minimum_experience, self.maximum_experience),
            (self.graduation_year_min, self.graduation_year_max),
        ]:
            if lo is not None and hi is not None and lo > hi:
                raise ValueError("Minimum cannot exceed maximum")
        return self


class JobIn(Schema):
    company_name: str = Field(min_length=1, max_length=160)
    company_domain: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=240)
    normalized_role: str = Field(default="Software Engineer", max_length=120)
    description: str = Field(default="", max_length=100000)
    source: str = Field(default="manual", max_length=40)
    external_id: str | None = Field(default=None, max_length=200)
    requisition_id: str | None = Field(default=None, max_length=200)
    source_url: str | None = None
    application_url: str | None = None
    employment_type: Literal["internship", "full-time", "part-time", "contract", "unknown"] = (
        "internship"
    )
    locations: list[str] = Field(default_factory=list, max_length=50)
    country: str = Field(default="Unknown", max_length=80)
    remote_status: Literal["onsite", "hybrid", "remote", "unknown"] = "unknown"
    requirements: Requirements = Field(default_factory=Requirements)
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_skills: list[str] = Field(default_factory=list, max_length=100)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, max_length=10)
    salary_period: str | None = Field(default=None, max_length=30)
    stipend: str | None = Field(default=None, max_length=200)
    selection_stages: list[str] = Field(default_factory=list, max_length=20)
    application_deadline: datetime | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool = True
    is_demo: bool = False
    provenance: dict = Field(default_factory=dict)
    _urls = field_validator("source_url", "application_url")(safe_url)

    @field_validator("application_deadline", "posted_at", "expires_at")
    @classmethod
    def utc_dates(cls, value):
        return value.astimezone(UTC).replace(tzinfo=None) if value and value.tzinfo else value


STATUSES = [
    "DISCOVERED",
    "SAVED",
    "PLANNING_TO_APPLY",
    "APPLIED",
    "OA_RECEIVED",
    "OA_COMPLETED",
    "INTERVIEW",
    "FINAL_ROUND",
    "OFFER",
    "REJECTED",
    "WITHDRAWN",
    "EXPIRED",
]


class ApplicationIn(Schema):
    job_id: str
    status: str = "SAVED"
    notes: str = Field(default="", max_length=10000)
    resume_id: str | None = None
    referral: str = Field(default="", max_length=500)
    recruiter: str = Field(default="", max_length=500)
    oa_deadline: datetime | None = None
    interview_dates: list[datetime] = Field(default_factory=list, max_length=20)
    result: str = Field(default="", max_length=1000)
    rejection_stage: str = Field(default="", max_length=100)
    rejection_reason: str = Field(default="", max_length=3000)

    @field_validator("oa_deadline")
    @classmethod
    def normalize_oa(cls, value):
        return value.astimezone(UTC).replace(tzinfo=None) if value and value.tzinfo else value

    @field_validator("interview_dates")
    @classmethod
    def normalize_interviews(cls, values):
        return [v.astimezone(UTC).replace(tzinfo=None) if v.tzinfo else v for v in values]

    @field_validator("status")
    @classmethod
    def check_status(cls, value):
        if value not in STATUSES:
            raise ValueError("Unknown application status")
        return value


class SourceIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["greenhouse", "lever", "ashby", "official", "manual", "campus"]
    board: str = Field(default="", pattern=r"^[a-zA-Z0-9_-]*$", max_length=100)
    feed_url: str | None = None
    company_name: str = Field(default="", max_length=160)
    country: str = Field(default="Unknown", max_length=80)
    enabled: bool = True
    close_missing_after: int = Field(default=0, ge=0, le=10)
    _url = field_validator("feed_url")(safe_url)

    @model_validator(mode="after")
    def valid_source(self):
        if self.kind in ("greenhouse", "lever", "ashby") and not self.board:
            raise ValueError("Board token required")
        if self.kind == "official" and not self.feed_url:
            raise ValueError("Approved feed URL required")
        if self.close_missing_after == 1:
            raise ValueError("Use at least two complete missing snapshots, or 0 to disable")
        return self


class NoticeIn(Schema):
    text: str = Field(min_length=10, max_length=100000)


class DSALogIn(Schema):
    topic: str = Field(min_length=1, max_length=80)
    problem: str = Field(min_length=1, max_length=200)
    independent: bool = False
    hint_required: bool = False
    could_explain: bool = False
    complexity_understood: bool = False


class LearningIn(Schema):
    topic: str = Field(min_length=1, max_length=120)
    status: Literal["NOT_STARTED", "LEARNING", "COMFORTABLE", "STRONG"] = "LEARNING"
    notes: str = Field(default="", max_length=5000)


class MarketIn(Schema):
    market: str = Field(min_length=1, max_length=80)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    software_hiring_trend: str = Field(default="", max_length=3000)
    backend_trend: str = Field(default="", max_length=3000)
    ai_trend: str = Field(default="", max_length=3000)
    data_trend: str = Field(default="", max_length=3000)
    cloud_platform_trend: str = Field(default="", max_length=3000)
    cybersecurity_trend: str = Field(default="", max_length=3000)
    fresher_trend: str = Field(default="", max_length=3000)
    salary_observations: str = Field(default="", max_length=3000)
    visa_changes: str = Field(default="", max_length=3000)
    major_hiring_expansions: str = Field(default="", max_length=3000)
    major_layoffs: str = Field(default="", max_length=3000)
    important_skills: list[str] = Field(default_factory=list, max_length=100)
    source_references: list[str] = Field(min_length=1, max_length=30)

    @field_validator("source_references")
    @classmethod
    def references(cls, value):
        if any(not safe_url(url) for url in value):
            raise ValueError("Source URL required")
        return value


class VisaIn(Schema):
    country: str = Field(min_length=1, max_length=80)
    last_verified: datetime
    source_url: str
    visa_sponsorship_available: bool | None = None
    work_authorization_required: bool | None = None
    minimum_salary_threshold: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, max_length=10)
    experience_requirement: str = Field(default="", max_length=1000)
    graduate_eligibility: str = Field(default="", max_length=1000)
    language_requirement: str = Field(default="", max_length=1000)
    recognized_employer_requirement: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=5000)
    _url = field_validator("source_url")(safe_url)


class ResumeIn(Schema):
    name: str = Field(min_length=1, max_length=160)
    is_master: bool = False
    file_name: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=5000)
    version: str = Field(default="1", max_length=30)
