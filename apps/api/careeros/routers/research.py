import asyncio

from careeros.config import get_settings
from careeros.db import get_db
from careeros.models import ResearchLead, User
from careeros.routers.profile import owned
from careeros.schemas import Schema, safe_url
from careeros.security import current_user, rate_limit
from careeros.services.categories import CATEGORIES
from careeros.services.repository import profile_data
from careeros.services.research import queries_for, record_lead, research_brief, verify_lead
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Research"])


class LeadIn(Schema):
    url: str = Field(max_length=2000)
    _url = field_validator("url")(safe_url)


def serialize(lead):
    return {
        "id": lead.id,
        "url": lead.url,
        "status": lead.status,
        "first_discovered": lead.created_at,
        **lead.data,
    }


@router.get("/research")
def research(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {
        "search_configured": bool(get_settings().brave_search_api_key),
        "search_provider": "Brave Search",
        "query_limit": get_settings().research_query_limit,
        "queries": queries_for(profile_data(db, user)),
        "groups": research_brief(db, user),
        "leads": [
            serialize(r)
            for r in db.scalars(
                select(ResearchLead)
                .where(ResearchLead.user_id == user.id)
                .order_by(ResearchLead.created_at.desc())
                .limit(100)
            )
        ],
        "categories": CATEGORIES,
    }


@router.post("/research/leads", status_code=201)
def add_lead(body: LeadIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"research-lead:{user.id}", 20, 3600)
    try:
        lead = record_lead(db, user.id, body.url, title="Posting supplied by you")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if lead.status == "DISMISSED":
        lead.status = "NEW"
        db.commit()
    asyncio.run(verify_lead(db, lead))
    return serialize(lead)


@router.post("/research/leads/{id}/verify")
def check_lead(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"research-lead:{user.id}", 20, 3600)
    lead = owned(db, ResearchLead, id, user)
    if lead.status == "DISMISSED":
        lead.status = "NEW"
        db.commit()
    asyncio.run(verify_lead(db, lead))
    return serialize(lead)


@router.delete("/research/leads/{id}")
def dismiss_lead(id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    lead = owned(db, ResearchLead, id, user)
    lead.status = "DISMISSED"
    db.commit()
    return {"ok": True}
