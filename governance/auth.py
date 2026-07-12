from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

SECRET_KEY = "mock_secret_key_for_alpha"
ALGORITHM = "HS256"

security = HTTPBearer()

class CurrentUser:
    def __init__(self, user_id: str, role: str, workspace_id: str):
        self.id = user_id
        self.user_id = user_id
        self.role = role
        self.workspace_id = workspace_id


MOCK_USERS_DB = {
    "admin_01": {"password": "admin_password", "role": "admin", "workspace_id": "default"},
    "reviewer_01": {"password": "reviewer_password", "role": "reviewer", "workspace_id": "default"},
    "reviewer_02": {"password": "reviewer_password", "role": "reviewer", "workspace_id": "default"},
    "viewer_01": {"password": "viewer_password", "role": "viewer", "workspace_id": "default"},
    "admin_ws2": {"password": "admin_password", "role": "admin", "workspace_id": "workspace_2"},
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=60 * 24) # 24 hours
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> CurrentUser:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        workspace_id: str = payload.get("workspace_id")
        
        if user_id is None or role is None or workspace_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials - missing claims",
            )
            
        ALLOWED_ROLES = {"admin", "reviewer", "viewer", "system_actor", "provider", "user"}
        if role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid user role: {role}",
            )
            
        return CurrentUser(user_id=user_id, role=role, workspace_id=workspace_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


def audit_access_denied(db, user_id: str, attempted_workspace_id: str, action: str, reason: str):
    """Log a security event to the audit trail for a workspace isolation or access violation."""
    from governance.models.event import GovernanceEvent
    from datetime import datetime, timezone
    import uuid
    event = GovernanceEvent(
        id=str(uuid.uuid4()),
        workspace_id=attempted_workspace_id,
        target_type="workspace",
        target_id=attempted_workspace_id,
        actor_id=user_id,
        actor_type="user",
        action="access_denied",
        reason=reason,
        reason_code="ACCESS_DENIED",
        event_payload={"action_attempted": action, "user_id": user_id},
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
