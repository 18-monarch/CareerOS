import logging
import time

from careeros.models import Job, Occurrence, SourceRun
from careeros.services.discovery_catalog import early_career, enrich_location
from careeros.services.locking import job_lock
from careeros.services.repository import identity, upsert_job
from careeros.services.sources import ADAPTERS
from sqlalchemy import select

logger = logging.getLogger("careeros.ingestion")


def reconcile_missing(db, source, seen):
    threshold = source.config.get("close_missing_after", 0)
    if not threshold or not seen:
        return 0
    affected = set()
    for occurrence in db.scalars(select(Occurrence).where(Occurrence.source_id == source.id)):
        if occurrence.external_id not in seen:
            occurrence.missing_runs += 1
            if occurrence.missing_runs >= threshold:
                occurrence.is_active = False
                affected.add(occurrence.job_id)
    db.flush()
    closed = 0
    for job_id in affected:
        active = db.scalar(
            select(Occurrence.id)
            .where(Occurrence.job_id == job_id, Occurrence.is_active.is_(True))
            .limit(1)
        )
        job = db.get(Job, job_id)
        if not active and job.is_active:
            job.is_active = False
            job.data = {**job.data, "source_closed": True}
            closed += 1
    return closed


async def ingest_source(db, source):
    if not source.enabled:
        return {"status": "DISABLED", "fetched": 0, "added": 0, "updated": 0, "parse_errors": 0}
    with job_lock(db.bind, f"ingest-user:{source.user_id}") as acquired:
        if not acquired:
            return {"status": "RUNNING", "fetched": 0, "added": 0, "updated": 0, "parse_errors": 0}
        start = time.monotonic()
        run = SourceRun(
            source_id=source.id,
            status="HEALTHY",
            fetched=0,
            added=0,
            updated=0,
            parse_errors=0,
            closed=0,
            skipped=0,
        )
        try:
            adapter = ADAPTERS[source.kind](source.config)
            records = await adapter.fetch_jobs()
            if not isinstance(records, list):
                raise ValueError("Source response must contain a job list")
            run.fetched = len(records)
            # Do not hold SQLite's write lock during slow internet requests.
            db.add(run)
            db.flush()
            seen = set()
            for raw in records:
                try:
                    with db.begin_nested():
                        normalized = adapter.normalize_job(raw)
                        seen.add(
                            normalized.external_id or identity(normalized.model_dump(mode="json"))
                        )
                        if source.config.get("discovery_managed"):
                            if not early_career(normalized):
                                run.skipped += 1
                                continue
                            normalized = enrich_location(normalized)
                        _, created = upsert_job(db, source.user_id, normalized, source, raw)
                    seen.add(normalized.external_id or identity(normalized.model_dump(mode="json")))
                    run.added += int(created)
                    run.updated += int(not created)
                except Exception as exc:
                    run.parse_errors += 1
                    logger.warning(
                        "job_parse_failed",
                        extra={"source_id": source.id, "error_type": type(exc).__name__},
                    )
            if run.parse_errors:
                run.status = "DEGRADED"
            else:
                run.closed = reconcile_missing(db, source, seen)
        except Exception as exc:
            run.status = "FAILED"
            run.error = f"{type(exc).__name__}: source request or normalization failed; check configured board/feed and worker logs"
            logger.warning(
                "ingestion_failed", extra={"source_id": source.id, "error_type": type(exc).__name__}
            )
        run.runtime_ms = round((time.monotonic() - start) * 1000)
        db.add(run)
        db.commit()
        logger.info(
            "ingestion_complete",
            extra={
                "source_id": source.id,
                "status": run.status,
                "added": run.added,
                "parse_errors": run.parse_errors,
            },
        )
        return {
            key: getattr(run, key)
            for key in (
                "id",
                "status",
                "fetched",
                "added",
                "updated",
                "closed",
                "skipped",
                "parse_errors",
                "runtime_ms",
                "error",
            )
        }


def health_summary(db, sources):
    runs = (
        list(
            db.scalars(
                select(SourceRun)
                .where(SourceRun.source_id.in_([s.id for s in sources]))
                .order_by(SourceRun.created_at.desc())
            )
        )
        if sources
        else []
    )
    result = []
    for source in sources:
        rows = [r for r in runs if r.source_id == source.id]
        latest = rows[0] if rows else None
        success = next((r.created_at for r in rows if r.status in ("HEALTHY", "DEGRADED")), None)
        failure = next((r.created_at for r in rows if r.status == "FAILED"), None)
        result.append(
            {
                "id": source.id,
                "name": source.name,
                "kind": source.kind,
                "enabled": source.enabled,
                "config": source.config,
                "status": "DISABLED"
                if not source.enabled
                else latest.status
                if latest
                else "NOT_RUN",
                "last_success": success,
                "last_failure": failure,
                "average_runtime_ms": round(
                    sum(r.runtime_ms for r in rows[:20]) / min(len(rows), 20)
                )
                if rows
                else None,
                "latest": {
                    k: getattr(latest, k)
                    for k in (
                        "fetched",
                        "added",
                        "updated",
                        "closed",
                        "skipped",
                        "parse_errors",
                        "runtime_ms",
                        "error",
                        "created_at",
                    )
                }
                if latest
                else None,
            }
        )
    return result
