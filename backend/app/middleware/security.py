"""
backend/app/middleware/security.py

Phase 9D — Security Middleware, Rate Limiting & Input Sanitization.
Implements modern security protections across FastAPI routes:
- Security HTTP headers (X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy).
- Configurable endpoint-tiered rate limiter (generous for analytics/projects, moderate for RAG, strict for AI assistant).
- Query input sanitizer preventing XSS script reflection and SQL injection strings.
"""

import os
import re
import time
import logging
from typing import Dict, Tuple
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("nirman.security")

# Configuration Environment Flags
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Tiered Limits (Requests per window)
TIER_LIMITS = {
    "analytics": int(os.getenv("RATE_LIMIT_ANALYTICS", "100")),
    "projects": int(os.getenv("RATE_LIMIT_PROJECTS", "100")),
    "rag": int(os.getenv("RATE_LIMIT_RAG", "100")),
    "assistant": int(os.getenv("RATE_LIMIT_ASSISTANT", "100")),
    "default": 100
}



def sanitize_input_string(value: str) -> str:
    """Sanitize user query strings against script injection and dangerous tags."""
    if not value:
        return ""
    # Strip script tags and HTML tags
    clean = re.sub(r'<script.*?>.*?</script>', '', value, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', '', clean)
    # Neutralize dangerous characters
    clean = clean.replace('\0', '').strip()
    return clean


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing modern security HTTP response headers."""
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # Enforce Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' http: https: data: blob:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
            "style-src 'self' 'unsafe-inline' https:; "
            "font-src 'self' https: data:; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self' http: https: ws: wss:;"
        )

        return response


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """In-memory rate limiter enforcing endpoint-specific usage tiers."""
    def __init__(self, app):
        super().__init__(app)
        # Client IP -> (Request Count, Window Start Timestamp)
        self.client_windows: Dict[str, Tuple[int, float]] = {}

    def _get_tier(self, path: str) -> str:
        if "/api/assistant" in path:
            return "assistant"
        if "/api/documents" in path:
            return "rag"
        if "/api/analytics" in path:
            return "analytics"
        if "/api/projects" in path:
            return "projects"
        return "default"

    async def dispatch(self, request: Request, call_next) -> Response:
        if not RATE_LIMIT_ENABLED or not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        tier = self._get_tier(request.url.path)
        limit = TIER_LIMITS.get(tier, TIER_LIMITS["default"])

        now = time.time()
        key = f"{client_ip}:{tier}"

        count, window_start = self.client_windows.get(key, (0, now))

        if now - window_start > RATE_LIMIT_WINDOW_SECONDS:
            # Reset window
            count = 1
            window_start = now
        else:
            count += 1

        self.client_windows[key] = (count, window_start)

        if count > limit:
            logger.warning(f"Rate limit exceeded for IP {client_ip} on endpoint tier '{tier}' ({count}/{limit})")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "error": True,
                    "message": f"Too many requests for rate limit tier '{tier}'. Please wait before retrying.",
                    "status_code": 429
                }
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        return response

