"""
Router: /api/governance/incidents
Incident and compliance case management.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from governance.database import get_db
from governance.auth import get_current_user, CurrentUser
from governance.models.incident import GovernanceIncident
from governance.models.event import GovernanceEvent

router = APIRouter(prefix="/api/governance/incidents", tags=["Incidents"])


class CreateIncidentRequest(BaseModel):
    severity: str = "medium"    # critical | high | medium | low
    summary: str
    trigger_event_id: Optional[str] = None
    linked_targets: Optional[dict] = None
    workspace_id: Optional[str] = "default"


class UpdateIncidentRequest(BaseModel):
    status: Optional[str] = None
    owner_id: Optional[str] = None
    notes: Optional[str] = None
    closure_reason: Optional[str] = None


@router.post("", status_code=201)
def create_incident(
    body: CreateIncidentRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Create an incident or compliance case."""
    incident = GovernanceIncident(
        workspace_id=user.workspace_id,
        severity=body.severity,
        status="open",
        trigger_event_id=body.trigger_event_id,
        summary=body.summary,
        linked_targets=body.linked_targets,
    )
    db.add(incident)
    db.flush()

    db.add(GovernanceEvent(
        workspace_id=user.workspace_id,
        source_service="incident-service",
        target_type="incident",
        target_id=incident.id,
        actor_id=user.user_id,
        actor_type="user",
        action="incident_created",
        reason=body.summary,
        reason_code="INCIDENT_OPENED",
        event_payload={"severity": body.severity},
        occurred_at=datetime.now(timezone.utc),
    ))
    db.commit()
    db.refresh(incident)

    return {
        "incident_id": incident.id,
        "status": incident.status,
        "severity": incident.severity,
        "summary": incident.summary,
        "created_at": incident.created_at,
    }


@router.get("")
def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """List incidents with optional filters."""
    q = db.query(GovernanceIncident).filter(GovernanceIncident.workspace_id == user.workspace_id)
    if status:
        q = q.filter(GovernanceIncident.status == status)
    if severity:
        q = q.filter(GovernanceIncident.severity == severity)
    total = q.count()
    incidents = q.order_by(GovernanceIncident.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "incidents": [
            {
                "id": i.id,
                "severity": i.severity,
                "status": i.status,
                "summary": i.summary,
                "trigger_event_id": i.trigger_event_id,
                "owner_id": i.owner_id,
                "linked_targets": i.linked_targets,
                "notes": i.notes,
                "created_at": i.created_at,
                "updated_at": i.updated_at,
                "closed_at": i.closed_at,
            }
            for i in incidents
        ],
    }


@router.get("/{incident_id}")
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get a single incident by ID."""
    incident = db.query(GovernanceIncident).filter(
        GovernanceIncident.id == incident_id,
        GovernanceIncident.workspace_id == user.workspace_id,
    ).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return {
        "id": incident.id,
        "severity": incident.severity,
        "status": incident.status,
        "summary": incident.summary,
        "trigger_event_id": incident.trigger_event_id,
        "owner_id": incident.owner_id,
        "linked_targets": incident.linked_targets,
        "notes": incident.notes,
        "closure_reason": incident.closure_reason,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
        "closed_at": incident.closed_at,
    }


@router.patch("/{incident_id}")
def update_incident(
    incident_id: str,
    body: UpdateIncidentRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Update incident status, owner, notes, or close it."""
    incident = db.query(GovernanceIncident).filter(
        GovernanceIncident.id == incident_id,
        GovernanceIncident.workspace_id == user.workspace_id,
    ).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    if body.status:
        incident.status = body.status
        if body.status == "closed":
            incident.closed_at = datetime.now(timezone.utc)
    if body.owner_id:
        incident.owner_id = body.owner_id
    if body.notes:
        incident.notes = body.notes
    if body.closure_reason:
        incident.closure_reason = body.closure_reason

    db.add(GovernanceEvent(
        workspace_id=user.workspace_id,
        source_service="incident-service",
        target_type="incident",
        target_id=incident.id,
        actor_id=user.user_id,
        actor_type="user",
        action="incident_updated",
        reason=body.notes or body.closure_reason,
        event_payload={"new_status": body.status},
        occurred_at=datetime.now(timezone.utc),
    ))
    db.commit()
    db.refresh(incident)
    return {"id": incident.id, "status": incident.status, "updated_at": incident.updated_at}
