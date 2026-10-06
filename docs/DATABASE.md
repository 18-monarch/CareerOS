# Database and migrations

The production database is PostgreSQL, compatible with Neon. SQLite runs the same models for quick local work. All timestamps are normalized to naive UTC at the database boundary; the UI converts them for display. API clients should supply explicit ISO timezones. A missing date remains null.

## Entity map

| Group | Tables | Purpose |
|---|---|---|
| Identity | users, auth_sessions, rate_buckets, audit_logs | Account, hashed tokens, shared throttling, mutation audit |
| Candidate | profiles, user_preferences, skills, user_skills | Editable facts, rules, self-assessment |
| Projects | projects, project_mastery | Technology/evidence lists and topic understanding |
| Opportunities | companies, jobs, job_requirements, job_skills | Canonical job, flexible hard requirements and skill joins |
| Provenance | job_sources, job_source_occurrences, source_health | Configuration, raw source evidence, run outcomes |
| Ranking | job_matches | Worker-generated explainable result snapshots |
| Tracking | applications, application_events, resume_versions | Unique user/job application, append-only milestones, resume metadata |
| Learning | learning_progress, dsa_logs | Topic plans and practice evidence |
| Intelligence | notifications, market_reports, visa_rules | Durable alerts and sourced notes |

## Constraints

- User email, session token hashes, normalized company/skill names are unique.
- Jobs are unique by `(user_id, canonical_key)`; occurrences by `(source_id, external_id)`.
- Applications are unique by `(user_id, job_id)`; a bookmark and an application share one CRM record.
- User skills are unique by `(user_id, skill_id)`; mastery topics by `(project_id, topic)`.
- Notifications are unique by `(user_id, dedupe_key)`.
- Every private row is owned directly or through a parent. Tenant checks happen in every resource route, not in browser code.
- Foreign keys enforce identity; SQLite connections explicitly enable foreign keys.
- Job owner/active/deadline, source-run source IDs, owner IDs and title fields are indexed.
- Application events cannot be updated or deleted after migration `8f22a1`. Deleting an account that owns history would require an explicit, audited privacy-erasure migration/maintenance procedure; there is no account deletion endpoint in V1.

## Migrations

```bash
.venv/bin/alembic upgrade head
.venv/bin/alembic current
.venv/bin/alembic check
# After intentionally changing models:
.venv/bin/alembic revision --autogenerate -m 'Describe the schema change'
```

Review generated migrations, particularly constraints and data conversions. Never substitute `create_all()` for migrations in production. The first migration contains explicit table/column definitions; the second installs immutable-history triggers. `create_all()` is used only in isolated tests.

Use a database backup before production migration. Schema rollback: first inspect the downgrade and test on a copy. Backing up/restoring Neon branches is preferable to blindly downgrading a database after user writes.

## JSON design

Pydantic validates incoming JSON structures. JSON allows a job to retain uncertain/source-specific evidence without dozens of nullable columns. Stable indexed dimensions (owner, role title, country, active flag, deadline) remain ordinary columns. Large-scale querying of specific requirements may justify PostgreSQL JSONB and expression indexes later. V1 uses portable JSON and never constructs SQL from input strings.
