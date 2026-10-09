"""Durable discovery schedules, driven by the local API or worker CLI."""

import asyncio
import logging
import threading
from datetime import timedelta

from careeros.config import get_settings
from careeros.db import SessionLocal, utcnow
from careeros.models import DiscoveryState, Job, Source, User
from careeros.services.discovery_catalog import CATALOG
from careeros.services.eligibility import unconfirmed
from careeros.services.ingestion import ingest_source
from careeros.services.locking import job_lock
from careeros.services.notifications import deliver, generate
from careeros.services.repository import ranked_jobs, shared_record
from sqlalchemy import select

logger = logging.getLogger("careeros.discovery")


def ensure_state(db, user_id):
    state = shared_record(db, DiscoveryState, "user_id", user_id)
    db.commit()
    return state


def ensure_catalog(db, user_id):
    sources = list(db.scalars(select(Source).where(Source.user_id == user_id)))
    for board in CATALOG:
        if any(
            s.kind == board["kind"] and s.config.get("board") == board["board"] for s in sources
        ):
            continue
        row = Source(
            user_id=user_id,
            name=f"{board['company_name']} careers",
            kind=board["kind"],
            enabled=True,
            config={
                "board": board["board"],
                "company_name": board["company_name"],
                "country": "Unknown",
                "close_missing_after": 2,
                "discovery_managed": True,
                "catalog_url": board["url"],
            },
        )
        db.add(row)
        sources.append(row)
    db.commit()
    return sources


async def run_user(db, user_id):
    with job_lock(db.bind, f"discovery:{user_id}") as acquired:
        if not acquired:
            return {"status": "RUNNING"}
        state = ensure_state(db, user_id)
        if not state.enabled or (state.next_run and state.next_run > utcnow()):
            return {"status": "SKIPPED"}
        state.status, state.last_started, state.error = "RUNNING", utcnow(), None
        db.commit()
        summary = {"sources": 0, "fetched": 0, "added": 0, "updated": 0, "skipped": 0, "errors": 0}
        try:
            with job_lock(db.bind, f"ingest-user:{user_id}") as setup_lock:
                if not setup_lock:
                    state.status, state.next_run = "PENDING", utcnow() + timedelta(minutes=1)
                    db.commit()
                    return {"status": "PENDING"}
                sources = ensure_catalog(db, user_id)
            for source in sources:
                db.refresh(state)
                if not state.enabled:
                    break
                db.refresh(source)
                if not source.enabled or source.kind in ("manual", "campus"):
                    continue
                result = await ingest_source(db, source)
                summary["sources"] += 1
                for key in ("fetched", "added", "updated", "skipped"):
                    summary[key] += result.get(key, 0)
                summary["errors"] += int(result["status"] in ("FAILED", "DEGRADED", "RUNNING"))
            user = db.get(User, user_id)
            from careeros.services.research import recheck_leads, run_research

            summary["research"] = (
                await run_research(
                    db, user, state.summary.get("research", {}).get("next_query_offset", 0)
                )
                if state.enabled
                else {"status": "PAUSED", "errors": 0}
            )
            if state.enabled:
                summary["rechecked"] = await recheck_leads(db, user)
                summary["errors"] += summary["rechecked"]["errors"]
            summary["errors"] += summary["research"]["errors"]
            with job_lock(db.bind, f"ingest-user:{user_id}") as expiry_lock:
                if expiry_lock:
                    for job in db.scalars(
                        select(Job).where(Job.user_id == user_id, Job.is_active.is_(True))
                    ):
                        if any(
                            getattr(job, key)
                            and getattr(job, key) <= utcnow()
                            and not unconfirmed(job.requirements.provenance, key)
                            for key in ("application_deadline", "expires_at")
                        ):
                            job.is_active = False
                    db.commit()
            from careeros.services.application_desk import auto_prepare

            summary["drafts_prepared"] = auto_prepare(db, user)
            live = [job for job in ranked_jobs(db, user) if not job["is_demo"] and job["is_active"]]
            summary["live_opportunities"] = len(live)
            summary["ready_to_apply"] = sum(
                job["match"]["classification"] == "APPLY_NOW" for job in live
            )
            summary["review_required"] = sum(
                job["match"]["eligibility"]["state"] == "REVIEW_REQUIRED" for job in live
            )
            with job_lock(db.bind, f"notify:{user_id}") as notify_lock:
                if notify_lock:
                    summary["notifications"] = sum(
                        generate(db, user, kind)
                        for kind in ("high-match", "deadline", "daily", "weekly")
                    )
                    from careeros.services.notifications import meaningful_updates

                    summary["research_alerts"] = meaningful_updates(db, user)
                    await deliver(db, user)
            db.refresh(state)
            state.status = "DEGRADED" if summary["errors"] else "HEALTHY"
            state.error = (
                "Some sources could not be checked. See source health below."
                if summary["errors"]
                else None
            )
            state.summary = summary
            state.last_finished = utcnow()
            state.next_run = utcnow() + timedelta(
                hours=1 if summary["errors"] else get_settings().discovery_interval_hours
            )
            db.commit()
            logger.info(
                "discovery_complete", extra={"status": state.status, "added": summary["added"]}
            )
            return {"status": state.status, **summary}
        except Exception as exc:
            db.rollback()
            state = db.scalar(select(DiscoveryState).where(DiscoveryState.user_id == user_id))
            state.status, state.last_finished = "FAILED", utcnow()
            state.error = (
                "Automatic check failed; retrying in one hour. See backend logs for the error type."
            )
            state.next_run = utcnow() + timedelta(hours=1)
            state.summary = {**summary, "errors": summary["errors"] + 1}
            db.commit()
            logger.error("discovery_failed", extra={"error_type": type(exc).__name__})
            return {"status": "FAILED", "errors": 1}


async def run_due(factory=None, stop=None):
    factory = factory or SessionLocal
    with factory() as db:
        user_ids = list(db.scalars(select(User.id)))
    results = []
    for user_id in user_ids:
        if stop and stop.is_set():
            break
        with factory() as db:
            results.append(await run_user(db, user_id))
    return {"users": len(results), "errors": sum(r.get("errors", 0) for r in results)}


class DiscoveryScheduler:
    def __init__(self):
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="careeros-discovery", daemon=True)

    def _loop(self):
        while not self.stop.is_set():
            self.wake.clear()
            try:
                asyncio.run(run_due(stop=self.stop))
            except Exception as exc:
                logger.warning(
                    "discovery_scheduler_unavailable", extra={"error_type": type(exc).__name__}
                )
            if not self.stop.is_set():
                self.wake.wait(30)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set()
        self.wake.set()
        self.thread.join(timeout=2)


scheduler = None


def wake_scheduler():
    if scheduler:
        scheduler.wake.set()


def status_data(state):
    settings = get_settings()
    return {
        **{
            key: getattr(state, key)
            for key in (
                "enabled",
                "status",
                "last_started",
                "last_finished",
                "next_run",
                "summary",
                "error",
            )
        },
        "scheduler_enabled": settings.auto_discovery_enabled or settings.external_discovery_enabled,
        "scheduler_mode": "local"
        if settings.auto_discovery_enabled
        else ("external" if settings.external_discovery_enabled else "disabled"),
        "worker_interval_minutes": settings.discovery_worker_interval_minutes,
        "interval_hours": settings.discovery_interval_hours,
        "catalog": [{"company": b["company_name"], "url": b["url"]} for b in CATALOG],
    }
