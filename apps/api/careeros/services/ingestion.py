import logging
import time

from careeros.models import SourceRun
from careeros.services.locking import job_lock
from careeros.services.repository import upsert_job
from careeros.services.sources import ADAPTERS
from sqlalchemy import select

logger = logging.getLogger("careeros.ingestion")


async def ingest_source(db, source):
    if not source.enabled:
        return {"status": "DISABLED", "fetched": 0, "added": 0, "updated": 0, "parse_errors": 0}
    with job_lock(db.bind, f"ingest-user:{source.user_id}") as acquired:
        if not acquired:
            return {"status": "RUNNING", "fetched": 0, "added": 0, "updated": 0, "parse_errors": 0}
        start = time.monotonic()
        run = SourceRun(
            source_id=source.id, status="HEALTHY", fetched=0, added=0, updated=0, parse_errors=0
        )
        db.add(run)
        db.flush()
        try:
            adapter = ADAPTERS[source.kind](source.config)
            records = await adapter.fetch_jobs()
            if not isinstance(records, list):
                raise ValueError("Source response must contain a job list")
            run.fetched = len(records)
            for raw in records:
                try:
                    with db.begin_nested():
                        normalized = adapter.normalize_job(raw)
                        _, created = upsert_job(db, source.user_id, normalized, source, raw)
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
        except Exception as exc:
            run.status = "FAILED"
            run.error = f"{type(exc).__name__}: source request or normalization failed; check configured board/feed and worker logs"
            logger.warning(
                "ingestion_failed", extra={"source_id": source.id, "error_type": type(exc).__name__}
            )
        run.runtime_ms = round((time.monotonic() - start) * 1000)
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
