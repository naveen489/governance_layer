"""
Router: /api/governance/auth
Mock authentication endpoint to generate JWT tokens for MVP usage.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from governance.auth import create_access_token

router = APIRouter(prefix="/api/governance/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    user_id: str
    role: str
    workspace_id: str = "default"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

@router.post("/token", response_model=TokenResponse)
def login_for_access_token(body: LoginRequest):
    """Generate a mock JWT token containing user_id, role, and workspace_id claims."""
    # In a real system, this would verify credentials against an IDP.
    # For MVP, we just trust the inputs and sign a token.
    token_data = {
        "sub": body.user_id,
        "role": body.role,
        "workspace_id": body.workspace_id
    }
    token = create_access_token(data=token_data)
    return {"access_token": token, "token_type": "bearer"}
