export interface Match {
  score: number;
  classification: string;
  eligibility: { state: string; reasons: string[]; checks: string[] };
  strong_matches: string[];
  missing_required: string[];
  missing_preferred: string[];
  project_evidence: string[];
  preparation: string[];
  breakdown: Record<string, { weight: number; fit: number; points: number }>;
  score_suppressed: boolean;
}
export interface Job {
  categories?: string[];
  id: string;
  title: string;
  company_name: string;
  normalized_role: string;
  description: string;
  country: string;
  locations: string[];
  remote_status: string;
  employment_type: string;
  source: string;
  application_url: string | null;
  application_deadline: string | null;
  is_demo: boolean;
  is_active: boolean;
  manually_archived?: boolean;
  required_skills: string[];
  preferred_skills: string[];
  requirements: Record<string, unknown>;
  provenance: Record<string, unknown>;
  match: Match;
  stipend: string | null;
  application?: { id: string; status: string };
  occurrences?: {
    source_id: string;
    source_url: string;
    external_id: string;
    last_seen_at: string;
    is_active: boolean;
    missing_runs: number;
  }[];
}
export interface Preferences {
  career_categories?: string[];
  target_roles: string[];
  countries: string[];
  watchlist: string[];
  preferred_companies: string[];
  deadline_days: number[];
  email_enabled: boolean;
  weights: Record<string, number>;
  weekly_plan: string;
}
export interface Profile {
  name: string;
  email?: string;
  university: string;
  degree: string;
  branch: string;
  graduation_year: number | null;
  cgpa: number | null;
  semester: number | null;
  experience_years: number;
  work_authorizations: string[];
  external_profiles: Record<string, string>;
  preferences: Preferences;
}
export interface Skill {
  id: string;
  name: string;
  category: string;
  proficiency: number;
  confidence: number;
  evidence: string;
  last_used: string | null;
  learning_status: string;
}
export interface Project {
  id: string;
  name: string;
  description: string;
  repository_url: string | null;
  live_url: string | null;
  technologies: string[];
  verified_skills: string[];
  interview_readiness: string;
  mastery: {
    id: string;
    topic: string;
    status: string;
    confidence: number;
    notes: string;
    linked_skills: string[];
  }[];
}
export interface Application {
  id: string;
  job_id: string;
  title: string;
  company_name: string;
  status: string;
  is_demo: boolean;
  notes: string;
  resume_id: string | null;
  referral: string;
  recruiter: string;
  oa_deadline: string | null;
  interview_dates: string[];
  result: string;
  rejection_stage: string;
  rejection_reason: string;
  applied_at: string | null;
  deadline: string | null;
  events: { id: string; status: string; note: string; created_at: string }[];
}
export interface Gap {
  skill: string;
  jobs: number;
  required_count: number;
  estimated_hours: number;
  priority: number;
  explanation: string;
}
export interface Pipeline {
  counts: Record<string, number>;
  rates: Record<string, number | null>;
  sample_size: number;
  recommendation: string;
  note: string;
}
export interface Dashboard {
  new_today: number;
  active_jobs: number;
  classifications: Record<string, number>;
  not_eligible: number;
  top_jobs: Job[];
  next_deadline: Job | null;
  learning: Gap[];
  pipeline: Pipeline;
  planned: number;
  weekly_plan: string;
  demo_jobs: number;
}
export interface Source {
  id: string;
  name: string;
  kind: string;
  enabled: boolean;
  status: string;
  config: {
    board?: string;
    company_name?: string;
    country?: string;
    feed_url?: string | null;
    close_missing_after?: number;
  };
  last_success: string | null;
  last_failure: string | null;
  average_runtime_ms: number | null;
  latest: {
    fetched: number;
    added: number;
    updated: number;
    closed: number;
    skipped?: number;
    parse_errors: number;
    error: string | null;
    created_at: string;
  } | null;
}
