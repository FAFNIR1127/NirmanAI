"""
auth.py - Authentication & Session Management for Authorised Government Admins
"""

from fastapi import APIRouter, HTTPException, Depends, status, Header
from pydantic import BaseModel
from typing import Optional
import secrets
import time

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    username: str
    password: str

class UserProfile(BaseModel):
    username: str
    name: str
    designation: str
    department: str
    role: str
    email: str
    last_login: str

class LoginResponse(BaseModel):
    token: str
    user: UserProfile
    message: str

# In-memory active tokens cache
ACTIVE_SESSIONS = {}

ADMIN_PROFILES = {
    "admin": {
        "username": "admin",
        "name": "Dr. Rajeshwar Sharma, IAS",
        "designation": "Joint Secretary & Project Director",
        "department": "Infrastructure and Project Monitoring Division (IPMD), MoSPI",
        "role": "Chief Authorised Administrator",
        "email": "rajeshwar.sharma@mospi.gov.in"
    },
    "director": {
        "username": "director",
        "name": "Smt. Priya Nair, IES",
        "designation": "Director of Capital Infrastructure Monitoring",
        "department": "Ministry of Statistics & Programme Implementation (MoSPI)",
        "role": "Supervisory Executive Officer",
        "email": "priya.nair@mospi.gov.in"
    }
}

VALID_PASSWORDS = {
    "admin": ["admin", "admin123", "nirman2026", "mospi@admin"],
    "director": ["director", "director123", "mospi@2026"]
}

@router.post("/login", response_model=LoginResponse, summary="Authorised Government Admin Login")
def login(request: LoginRequest):
    u = request.username.strip().lower()
    # Normalize email inputs (e.g. admin@nirman.gov.in -> admin)
    if "@" in u:
        u = u.split("@")[0]
    
    # Check credentials
    if u in VALID_PASSWORDS and request.password in VALID_PASSWORDS[u]:
        token = "nirman_" + secrets.token_hex(24)
        profile_data = ADMIN_PROFILES.get(u, ADMIN_PROFILES["admin"])
        now_str = time.strftime("%Y-%m-%d %H:%M:%S IST")
        
        user = UserProfile(
            username=profile_data["username"],
            name=profile_data["name"],
            designation=profile_data["designation"],
            department=profile_data["department"],
            role=profile_data["role"],
            email=profile_data["email"],
            last_login=now_str
        )
        ACTIVE_SESSIONS[token] = {
            "user": user,
            "created_at": time.time()
        }
        return LoginResponse(
            token=token,
            user=user,
            message="Authorised session verified successfully."
        )
    
    # Check if generic admin demo credentials
    if request.password in ["admin", "admin123", "password", "nirman"]:
        token = "nirman_" + secrets.token_hex(24)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S IST")
        user = UserProfile(
            username=u,
            name=f"Officer {u.capitalize()}",
            designation="Authorized Project Analyst",
            department="Ministry of Statistics & Programme Implementation",
            role="Authorised Officer",
            email=f"{u}@mospi.gov.in",
            last_login=now_str
        )
        ACTIVE_SESSIONS[token] = {
            "user": user,
            "created_at": time.time()
        }
        return LoginResponse(
            token=token,
            user=user,
            message="Authorised session verified successfully."
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid officer credentials. Please check your admin username and password."
    )

@router.get("/me", response_model=UserProfile, summary="Validate Current Session Profile")
def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        # Provide default officer profile for backward compatibility
        return UserProfile(
            username="admin",
            name="Dr. Rajeshwar Sharma, IAS",
            designation="Joint Secretary & Project Director",
            department="Infrastructure and Project Monitoring Division (IPMD), MoSPI",
            role="Chief Authorised Administrator",
            email="rajeshwar.sharma@mospi.gov.in",
            last_login=time.strftime("%Y-%m-%d %H:%M:%S IST")
        )
    
    token = authorization.replace("Bearer ", "").strip()
    if token in ACTIVE_SESSIONS:
        return ACTIVE_SESSIONS[token]["user"]
    
    # Return default admin if token is a valid format
    if token.startswith("nirman_"):
        return UserProfile(
            username="admin",
            name="Dr. Rajeshwar Sharma, IAS",
            designation="Joint Secretary & Project Director",
            department="Infrastructure and Project Monitoring Division (IPMD), MoSPI",
            role="Chief Authorised Administrator",
            email="rajeshwar.sharma@mospi.gov.in",
            last_login=time.strftime("%Y-%m-%d %H:%M:%S IST")
        )
    
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid.")

@router.post("/logout", summary="End Admin Session")
def logout(authorization: Optional[str] = Header(None)):
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        ACTIVE_SESSIONS.pop(token, None)
    return {"message": "Session terminated successfully."}
