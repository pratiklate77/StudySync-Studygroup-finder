from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, Set

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityMiddleware(BaseHTTPMiddleware):
    """Enhanced security middleware for admin service."""
    
    def __init__(self, app, max_attempts: int = 5, lockout_time: int = 900):  # 15 minutes
        super().__init__(app)
        self.max_attempts = max_attempts
        self.lockout_time = lockout_time
        self.failed_attempts: Dict[str, list] = defaultdict(list)
        self.blocked_ips: Set[str] = set()
        self.suspicious_patterns = [
            "/wp-admin",
            "/phpmyadmin",
            "/.env",
            "eval(",
            "javascript:",
        ]
    
    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        
        # Check if IP is blocked
        if self._is_ip_blocked(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="IP temporarily blocked due to suspicious activity"
            )
        
        # Check for suspicious patterns
        if self._is_suspicious_request(request):
            self._record_failed_attempt(client_ip)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Suspicious request detected"
            )
        
        # Rate limiting for login attempts
        if request.url.path == "/api/v1/auth/login" and request.method == "POST":
            if self._is_rate_limited(client_ip):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many login attempts. Try again in {self.lockout_time // 60} minutes."
                )
        
        response = await call_next(request)
        
        # Record failed login attempts
        if (request.url.path == "/api/v1/auth/login" and 
            request.method == "POST" and 
            response.status_code == 401):
            self._record_failed_attempt(client_ip)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get real client IP considering proxies."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _is_suspicious_request(self, request: Request) -> bool:
        """Check if request contains suspicious patterns."""
        url_path = request.url.path.lower()
        query_string = str(request.url.query).lower()
        
        for pattern in self.suspicious_patterns:
            if pattern in url_path or pattern in query_string:
                return True
        
        return False
    
    def _record_failed_attempt(self, ip: str) -> None:
        """Record failed attempt for IP."""
        current_time = time.time()
        self.failed_attempts[ip].append(current_time)
        
        # Clean old attempts
        self.failed_attempts[ip] = [
            attempt for attempt in self.failed_attempts[ip]
            if current_time - attempt < self.lockout_time
        ]
        
        # Block IP if too many attempts
        if len(self.failed_attempts[ip]) >= self.max_attempts:
            self.blocked_ips.add(ip)
    
    def _is_rate_limited(self, ip: str) -> bool:
        """Check if IP is rate limited."""
        current_time = time.time()
        recent_attempts = [
            attempt for attempt in self.failed_attempts[ip]
            if current_time - attempt < self.lockout_time
        ]
        return len(recent_attempts) >= self.max_attempts
    
    def _is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is currently blocked."""
        if ip not in self.blocked_ips:
            return False
        
        # Check if block should be lifted
        current_time = time.time()
        recent_attempts = [
            attempt for attempt in self.failed_attempts[ip]
            if current_time - attempt < self.lockout_time
        ]
        
        if not recent_attempts:
            self.blocked_ips.discard(ip)
            return False
        
        return True