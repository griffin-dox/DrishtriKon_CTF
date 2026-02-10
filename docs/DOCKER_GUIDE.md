# 🐳 Docker Guide - DrishtriKon CTF Platform

Complete Docker deployment and development guide.

## 📋 Overview

The platform provides two Docker configurations:

- **docker-compose.yml**: Production-ready multi-container setup
- **docker-compose.dev.yml**: Lightweight development environment

---

## 🏗️ Architecture

### Production Stack

```
┌─────────────────────────────────────────┐
│           Nginx (Reverse Proxy)         │
│         SSL/TLS, Rate Limiting          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      Flask App (Gunicorn Workers)       │
│    Multi-worker, Thread-based           │
└──────┬─────────────────────┬────────────┘
       │                     │
┌──────▼─────────┐  ┌────────▼────────────┐
│  PostgreSQL 15 │  │   Redis Cache       │
│   (Primary DB) │  │   (Optional)        │
└────────────────┘  └─────────────────────┘
```

---

## 🚀 Quick Start

### Development

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up

# Access: http://localhost:5000
```

### Production

```bash
# Configure environment
cp .env.example .env
nano .env  # Fill in production values

# Start all services
docker-compose up -d

# With nginx and redis
docker-compose --profile with-nginx --profile with-redis up -d
```

---

## 📦 Production Deployment

### Step 1: Environment Configuration

`.env` file (required):

```bash
# Security
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")

# Database
POSTGRES_DB=drishtrikon_ctf
POSTGRES_USER=ctf_user
POSTGRES_PASSWORD=secure-random-password

# Email
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@your-domain.com

# reCAPTCHA
RECAPTCHA_SITE_KEY=your-site-key
RECAPTCHA_SECRET_KEY=your-secret-key

# Optional
DISCORD_SECURITY_WEBHOOK_URL=your-webhook-url
```

### Step 2: Start Services

```bash
# Build and start
docker-compose up -d --build

# Check status
docker-compose ps

# Expected output:
# drishtrikon_db    running   5432/tcp
# drishtrikon_web   running   0.0.0.0:8000->8000/tcp
```

### Step 3: Initialize Database

```bash
# Run migrations
docker-compose exec web flask db upgrade

# Verify
docker-compose exec db psql -U ctf_user -d drishtrikon_ctf -c "\dt"
```

### Step 4: Create Admin User

```bash
docker-compose exec web python << 'EOF'
from app import create_app
from app.models import User
from app.extensions import db

app = create_app('production')
with app.app_context():
    admin = User(username='admin', email='admin@example.com')
    admin.set_password('ChangeThisPassword!')
    admin.role = 'OWNER'
    admin.email_verified = True
    db.session.add(admin)
    db.session.commit()
    print("Admin user created successfully!")
EOF
```

---

## 🛠️ Service Management

### Container Operations

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose stop

# Restart specific service
docker-compose restart web

# Remove all containers
docker-compose down

# Remove containers and volumes (DESTRUCTIVE!)
docker-compose down -v
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f db

# Last 100 lines
docker-compose logs --tail=100 web

# Since specific time
docker-compose logs --since "2024-02-10T12:00:00" web
```

### Executing Commands

```bash
# Run Flask CLI
docker-compose exec web flask --help

# Python shell
docker-compose exec web python

# Database migrations
docker-compose exec web flask db migrate -m "description"
docker-compose exec web flask db upgrade

# Clear cache
docker-compose exec web python -c "from app.extensions import cache; from app import create_app; app = create_app(); with app.app_context(): cache.clear()"
```

---

## 🔧 Development Workflow

### Local Development with Docker

```bash
# Start dev environment
docker-compose -f docker-compose.dev.yml up

# Features:
# - Auto-reload on code changes
# - Debug mode enabled
# - Simplified configuration
# - SQLite database (no PostgreSQL needed)
```

### Making Code Changes

```bash
# Code changes are automatically reflected (volume mount)

# If you modify requirements.txt
docker-compose down
docker-compose build --no-cache web
docker-compose up -d

# If you modify database models
docker-compose exec web flask db migrate -m "your changes"
docker-compose exec web flask db upgrade
```

### Database Access

```bash
# PostgreSQL shell
docker-compose exec db psql -U ctf_user -d drishtrikon_ctf

# Common queries
List all tables:   \dt
Describe table:    \d table_name
List users:        SELECT * FROM users;
Exit:              \q
```

---

## 🎯 Profiles (Optional Services)

### With Nginx (Reverse Proxy)

```bash
# Start with nginx profile
docker-compose --profile with-nginx up -d

# Access: http://localhost (port 80)
# HTTPS: https://localhost (port 443, requires SSL certs)

# Place SSL certificates in nginx/ssl/
mkdir -p nginx/ssl
cp your-cert.pem nginx/ssl/cert.pem
cp your-key.pem nginx/ssl/key.pem
```

### With Redis (Enhanced Caching)

```bash
# Start with redis profile
docker-compose --profile with-redis up -d

# Update .env
CACHE_TYPE=redis
REDIS_PASSWORD=your-redis-password

# Restart web service
docker-compose restart web
```

### Both Profiles

```bash
docker-compose --profile with-nginx --profile with-redis up -d
```

---

## 📊 Monitoring

### Health Checks

```bash
# Application health
curl http://localhost:8000/healthz

# Container health
docker-compose ps

# Resource usage
docker stats

# Disk usage
docker system df
```

### Performance Metrics

```bash
# Database connections
docker-compose exec db psql -U ctf_user -d drishtrikon_ctf -c "SELECT count(*) FROM pg_stat_activity;"

# Cache stats (if Redis)
docker-compose exec redis redis-cli INFO stats

# Application performance endpoint
curl http://localhost:8000/admin/performance/stats
```

---

## 🔄 Updates & Maintenance

### Updating the Application

```bash
# Pull latest code
git pull origin main

# Rebuild and recreate
docker-compose build --no-cache
docker-compose up -d --force-recreate

# Run migrations
docker-compose exec web flask db upgrade

# Clear cache
docker-compose exec web python -c "from app.services.cache.management import emergency_clear_cache; from app import create_app; app = create_app(); with app.app_context(): emergency_clear_cache()"
```

### Database Backups

```bash
# Create backup
docker-compose exec -T db pg_dump -U ctf_user drishtrikon_ctf > backup_$(date +%Y%m%d).sql

# With compression
docker-compose exec -T db pg_dump -U ctf_user drishtrikon_ctf | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore from backup
docker-compose exec -T db psql -U ctf_user -d drishtrikon_ctf < backup_20240210.sql
```

### Volume Management

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect drishtrikon_ctf_postgres_data

# Backup volume
docker run --rm -v drishtrikon_ctf_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .

# Restore volume
docker run --rm -v drishtrikon_ctf_postgres_data:/data -v $(pwd):/backup alpine sh -c "cd /data && tar xzf /backup/postgres_backup.tar.gz"
```

---

## 🐛 Troubleshooting

### Common Issues

**Port already in use**

```bash
# Check what's using port 8000
sudo lsof -i :8000
# Or change port in docker-compose.yml
```

**Database connection failed**

```bash
# Check database is running
docker-compose ps db

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

**Web container exits immediately**

```bash
# Check logs for errors
docker-compose logs web

# Common causes:
# - Missing environment variables
# - Database not ready (wait a few seconds and retry)
# - Syntax errors in code
```

**Out of memory**

```bash
# Check usage
docker stats

# Reduce Gunicorn workers
# Edit docker-compose.yml CMD: --workers 2 (instead of 4)

# Clear Docker cache
docker system prune -a
```

### Debug Mode

```bash
# Run container interactively
docker-compose run --rm web bash

# Inside container:
env | grep DATABASE_URL
flask db upgrade
python -c "from app import create_app; app = create_app(); print(app.config)"
```

---

## 🔐 Security Best Practices

### Container Security

```bash
# Scan for vulnerabilities
docker scout quickview your-image:latest

# Or use Trivy
trivy image your-image:latest

# Keep base images updated
docker-compose build --pull --no-cache
```

### Network Isolation

The `docker-compose.yml` creates an isolated network:

- Database only accessible from web container
- Redis only accessible from web container
- Only web/nginx expose ports to host

### Secrets Management

```bash
# Never commit .env file
# Use Docker secrets in swarm mode:
docker secret create db_password /path/to/password.txt

# Or use external secret managers:
# - AWS Secrets Manager
# - HashiCorp Vault
# - Azure Key Vault
```

---

## 📝 Docker Compose Reference

### Available Services

- `db`: PostgreSQL 15 database
- `redis`: Redis cache (profile: with-redis)
- `web`: Flask application
- `nginx`: Nginx reverse proxy (profile: with-nginx)

### Useful Commands

```bash
# View service configuration
docker-compose config

# Pull latest images
docker-compose pull

# Build without cache
docker-compose build --no-cache

# Scale service (web only)
docker-compose up -d --scale web=3

# Remove orphaned containers
docker-compose down --remove-orphans
```

---

## 🧪 Testing in Docker

```bash
# Run tests in container
docker-compose exec web pytest tests/ -v

# With coverage
docker-compose exec web pytest --cov=app --cov-report=term

# Run linting
docker-compose exec web flake8 app/
```

---

**Last Updated**: February 2026
