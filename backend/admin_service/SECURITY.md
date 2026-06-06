# 🔐 Admin Service Security Guide

## Current Security Status

### ✅ Implemented Security Features

**1. Rate Limiting & Brute Force Protection**
- Max 5 failed login attempts per IP
- 15-minute lockout after failed attempts
- Automatic IP blocking for suspicious activity

**2. Suspicious Activity Detection**
- Blocks common attack patterns: `/admin`, `/wp-admin`, `/.env`, SQL injection attempts
- Real-time threat monitoring
- Automatic IP blacklisting

**3. Multi-Admin System**
- Role-based access control (super_admin, admin, moderator)
- Permission-based API access
- Secure admin creation/management

**4. Password Security**
- Minimum 8 characters with letters + digits
- Bcrypt hashing with salt
- Password change functionality

**5. JWT Token Security**
- Secure token generation
- Token expiration (60 minutes)
- Proper token validation

## 🚨 Current Security Issues & Solutions

### Issue 1: Default Admin Credentials
**Problem**: Default admin@studysync.com / admin123
**Risk**: High - Anyone can access admin panel

**Solutions**:

#### Option A: Change Default Password (Quick Fix)
```bash
# Login and change password immediately
curl -X POST http://localhost:8008/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@studysync.com", "password": "admin123"}'

# Use token to change password
curl -X POST http://localhost:8008/api/v1/admin-management/change-password \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "admin123", "new_password": "SecurePass123!"}'
```

#### Option B: Create New Super Admin & Disable Default
```bash
# Create new super admin
curl -X POST http://localhost:8008/api/v1/admin-management/create \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-secure-email@company.com",
    "password": "YourSecurePassword123!",
    "full_name": "Your Name",
    "role": "super_admin"
  }'

# Deactivate default admin
curl -X POST http://localhost:8008/api/v1/admin-management/{default-admin-id}/deactivate \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Issue 2: Open CORS Policy
**Problem**: `allow_origins=["*"]` allows any domain
**Risk**: Medium - CSRF attacks possible

**Solution**: Update CORS settings
```python
# In app/main.py, change:
allow_origins=["https://yourdomain.com", "https://admin.yourdomain.com"]
```

### Issue 3: No HTTPS Enforcement
**Problem**: HTTP traffic not encrypted
**Risk**: High - Credentials sent in plain text

**Solution**: Add HTTPS redirect middleware
```python
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
app.add_middleware(HTTPSRedirectMiddleware)
```

## 🛡️ Production Security Checklist

### Immediate Actions (Before Going Live)

- [ ] **Change default admin password**
- [ ] **Create production admin account**
- [ ] **Deactivate default admin**
- [ ] **Update JWT secret key** (use `openssl rand -hex 32`)
- [ ] **Configure proper CORS origins**
- [ ] **Enable HTTPS/TLS**
- [ ] **Set up firewall rules** (only allow necessary ports)

### Environment Variables to Update

```env
# Strong JWT secret (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-super-secure-64-character-hex-string

# Production admin credentials
SUPER_ADMIN_EMAIL=admin@yourcompany.com
SUPER_ADMIN_PASSWORD=YourVerySecurePassword123!

# Disable default admin creation
CREATE_DEFAULT_ADMIN=false
```

### Network Security

```bash
# Firewall rules (example for Ubuntu/Debian)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 80/tcp    # HTTP (redirect to HTTPS)
sudo ufw deny 8008/tcp   # Block direct admin service access
sudo ufw enable

# Use reverse proxy (nginx/traefik) for HTTPS termination
```

## 🔍 Security Monitoring

### Current Monitoring Features

**1. Failed Login Tracking**
- IP-based attempt counting
- Automatic lockout after 5 failures
- 15-minute cooldown period

**2. Suspicious Request Detection**
- Common attack pattern blocking
- Real-time IP blacklisting
- Request logging for audit

**3. Admin Action Logging**
- All admin actions logged to database
- IP address and user agent tracking
- Audit trail for compliance

### Health Check Endpoints

```bash
# Basic health
curl http://localhost:8008/health

# Kafka connectivity
curl http://localhost:8008/health/kafka

# Database connections
curl http://localhost:8008/health/databases
```

## 🚀 Secure Deployment Guide

### 1. Docker Production Setup

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  admin_service:
    build: ./admin_service
    environment:
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - SUPER_ADMIN_EMAIL=${SUPER_ADMIN_EMAIL}
      - SUPER_ADMIN_PASSWORD=${SUPER_ADMIN_PASSWORD}
      - CREATE_DEFAULT_ADMIN=false
    networks:
      - internal
    # Don't expose port directly
    # ports:
    #   - "8008:8008"
  
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl/certs
    depends_on:
      - admin_service
```

### 2. Nginx Reverse Proxy

```nginx
# nginx.conf
server {
    listen 443 ssl;
    server_name admin.yourdomain.com;
    
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/certs/key.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000";
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=admin:10m rate=10r/m;
    limit_req zone=admin burst=5 nodelay;
    
    location / {
        proxy_pass http://admin_service:8008;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Environment Security

```bash
# Create secure .env file
cat > admin_service/.env.prod << EOF
# Database URLs (use strong passwords)
DATABASE_URL=postgresql+asyncpg://admin_user:$(openssl rand -base64 32)@postgres_admin:5432/admin_db

# JWT Configuration (generate secure key)
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Admin Configuration
SUPER_ADMIN_EMAIL=admin@yourcompany.com
SUPER_ADMIN_PASSWORD=$(openssl rand -base64 16)
CREATE_DEFAULT_ADMIN=false

# Security Settings
RATE_LIMIT_ENABLED=true
MAX_LOGIN_ATTEMPTS=3
LOCKOUT_TIME_MINUTES=30
EOF

# Secure file permissions
chmod 600 admin_service/.env.prod
```

## 🔧 Advanced Security Features

### 1. Two-Factor Authentication (Future Enhancement)

```python
# Add to admin user model
class AdminUser(Base):
    # ... existing fields ...
    totp_secret: Optional[str] = Column(String(32), nullable=True)
    is_2fa_enabled: bool = Column(Boolean, default=False)
    backup_codes: Optional[List[str]] = Column(JSON, nullable=True)
```

### 2. Session Management

```python
# Add session tracking
class AdminSession(Base):
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: UUID = Column(UUID(as_uuid=True), ForeignKey("admin_user.id"))
    token_hash: str = Column(String(255), nullable=False)
    ip_address: str = Column(String(45), nullable=False)
    user_agent: str = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    expires_at: datetime = Column(DateTime, nullable=False)
    is_active: bool = Column(Boolean, default=True)
```

### 3. API Key Authentication (For Service-to-Service)

```python
# Add API key model
class AdminAPIKey(Base):
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: str = Column(String(255), nullable=False)
    key_hash: str = Column(String(255), nullable=False)
    permissions: List[str] = Column(JSON, nullable=False)
    created_by: UUID = Column(UUID(as_uuid=True), ForeignKey("admin_user.id"))
    expires_at: Optional[datetime] = Column(DateTime, nullable=True)
    is_active: bool = Column(Boolean, default=True)
```

## 📊 Security Metrics & Alerts

### Key Metrics to Monitor

1. **Failed login attempts per hour**
2. **Blocked IPs count**
3. **Admin actions per user**
4. **Suspicious request patterns**
5. **Token usage patterns**

### Alert Conditions

```python
# Example alert conditions
ALERTS = {
    "high_failed_logins": {"threshold": 50, "window": "1h"},
    "multiple_admin_logins": {"threshold": 3, "window": "5m"},
    "suspicious_requests": {"threshold": 10, "window": "1m"},
    "database_errors": {"threshold": 5, "window": "5m"},
}
```

## 🎯 Quick Security Test

Test your admin service security:

```bash
# Test rate limiting
for i in {1..10}; do
  curl -X POST http://localhost:8008/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "wrong@email.com", "password": "wrongpass"}'
  echo "Attempt $i"
done

# Test suspicious pattern blocking
curl "http://localhost:8008/admin?id=1' OR '1'='1"

# Test health endpoints
curl http://localhost:8008/health
curl http://localhost:8008/health/kafka
curl http://localhost:8008/health/databases
```

## 📝 Security Summary

**Current Status**: 🟡 **Moderate Security**
- ✅ Rate limiting implemented
- ✅ Multi-admin system ready
- ✅ Password security enforced
- ⚠️ Default credentials need change
- ⚠️ HTTPS not enforced
- ⚠️ CORS too permissive

**Next Steps**:
1. Change default admin password immediately
2. Create production admin account
3. Configure HTTPS/TLS
4. Update CORS settings
5. Set up monitoring alerts

**Production Ready**: After completing security checklist above ✅