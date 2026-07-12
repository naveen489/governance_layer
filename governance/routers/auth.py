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
    password: str
    role: str
    workspace_id: str = "default"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

@router.post("/token", response_model=TokenResponse)
def login_for_access_token(body: LoginRequest):
    """Generate a mock JWT token containing user_id, role, and workspace_id claims after verifying credentials."""
    from governance.auth import MOCK_USERS_DB
    
    user_info = MOCK_USERS_DB.get(body.user_id)
    if not user_info or user_info["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if user_info["role"] != body.role or user_info["workspace_id"] != body.workspace_id:
        raise HTTPException(status_code=403, detail="Role or Workspace mismatch")
        
    token_data = {
        "sub": body.user_id,
        "role": body.role,
        "workspace_id": body.workspace_id
    }
    token = create_access_token(data=token_data)
    return {"access_token": token, "token_type": "bearer"}
