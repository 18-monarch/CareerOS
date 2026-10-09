import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from careeros.config import get_settings
from careeros.db import engine
from careeros.logging_config import configure_logging
from careeros.middleware import RequestSizeLimit
from careeros.routers import (
    application_desk,
    applications,
    auth,
    insights,
    jobs,
    profile,
    research,
    sources,
)

logger = configure_logging()


@asynccontextmanager
async def lifespan(app):
    import asyncio

    from careeros.services import discovery
    from careeros.services.startup import migrate_local

    await asyncio.to_thread(migrate_local, engine)

    if get_settings().auto_discovery_enabled:
        discovery.scheduler = discovery.DiscoveryScheduler()
        discovery.scheduler.start()
    try:
        yield
    finally:
        if discovery.scheduler:
            discovery.scheduler.close()
            discovery.scheduler = None


app = FastAPI(
    lifespan=lifespan,
    title="CareerOS API",
    version="1.0.0",
    description="Private career profiles, evidence-based eligibility and opportunity tracking. Cookie auth; mutations require X-CSRF-Token.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
)


app.add_middleware(RequestSizeLimit)


@app.middleware("http")
async def observation(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.monotonic()
    response = await call_next(request)
    response.headers.update(
        {
            "X-Request-ID": request_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Cache-Control": "no-store",
        }
    )
    if get_settings().environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        {
            "error": {
                "message": exc.detail,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    errors = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(
        {
            "error": {
                "message": "Validation failed",
                "fields": errors,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        status_code=422,
    )


@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(
        {
            "error": {
                "message": "This record conflicts with an existing record. Refresh and retry.",
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        status_code=409,
    )


@app.exception_handler(Exception)
async def internal_error(request, exc):
    if isinstance(exc, SQLAlchemyError):
        from careeros.services.startup import SCHEMA_HEAD, schema_revision

        if schema_revision(engine) != SCHEMA_HEAD:
            return JSONResponse(
                {
                    "error": {
                        "message": "Database upgrade required. Stop CareerOS and run python -m alembic upgrade head from the project folder, then restart.",
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
                status_code=503,
            )
    logger.error(
        "unhandled_error",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "error_type": type(exc).__name__,
        },
    )
    return JSONResponse(
        {
            "error": {
                "message": "Unexpected server error. Use the request ID when reporting this issue.",
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        status_code=500,
    )


@app.get("/health", tags=["Operations"])
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/ready", tags=["Operations"])
def ready():
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            connection.execute(text("SELECT 1 FROM users LIMIT 1"))
        if revision != "e91a05":
            return JSONResponse(
                {
                    "status": "not_ready",
                    "reason": "database_migration_required",
                    "schema_revision": revision,
                },
                status_code=503,
            )
        return {"status": "ready", "schema_revision": revision}
    except SQLAlchemyError:
        return JSONResponse({"status": "not_ready"}, status_code=503)


for router in (
    auth.router,
    profile.router,
    jobs.router,
    applications.router,
    insights.router,
    sources.router,
    research.router,
    application_desk.router,
):
    app.include_router(router)
