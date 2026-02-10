# 🚀 DrishtriKon CTF Platform

<div align="center">

**A production-grade Capture The Flag (CTF) platform built with Flask**

[![CI/CD](https://github.com/your-username/DrishtriKon_CTF/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/your-username/DrishtriKon_CTF/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Deployment](#-deployment) • [Security](#-security)

</div>

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Development](#-development)
- [Deployment](#-deployment)
- [Testing](#-testing)
- [Security](#-security)
- [Documentation](#-documentation)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### 🎯 Core Functionality

- **Multi-Role System**: Owner (Admin), Host, and Player roles with granular permissions
- **Competition Management**: Create, schedule, and manage CTF competitions
- **Challenge System**: Multiple challenge types with flag validation and scoring
- **Team Collaboration**: Team creation, invitations, and collaborative participation
- **Badge & Achievement System**: Automated badge assignment based on achievements
- **Real-time Leaderboards**: Dynamic scoring with performance caching

### 🔒 Security Features

- **Comprehensive Rate Limiting**: Endpoint-specific limits with user/IP tracking
- **Intrusion Detection System (IDS)**: Pattern-based attack detection
- **Honeypot System**: Fake routes and form fields to trap attackers
- **Session Security**: Strong session management with rotation
- **File Upload Validation**: Size and type restrictions
- **2FA via Email OTP**: Time-limited one-time passwords
- **reCAPTCHA v3**: Bot protection on sensitive endpoints
- **Security Headers**: CSP, HSTS, X-Frame-Options, and more

### ⚡ Performance & Scalability

- **Multi-tier Caching**: In-memory, filesystem, and Redis support
- **Database Optimization**: Connection pooling and query optimization
- **Static Asset Optimization**: Versioning and compression
- **Background Tasks**: Async execution for cleanup
- **Storage Management**: Automatic cache cleanup

### ☁️ Cloud Storage

- **AWS S3 / IDrive e2 Integration**: Secure file storage with encryption
- **Multi-layer File Validation**: Extension, MIME type, magic bytes verification
- **Presigned URLs**: Time-limited secure access to files
- **Automatic File Cleanup**: Old files deleted on updates
- **CORS Configuration**: Secure cross-origin resource sharing

---

## 🏗️ Architecture

```
DrishtriKon_CTF/
├── app/
│   ├── __init__.py              # Application factory (create_app)
│   ├── extensions.py            # Flask extensions (db, cache, login_manager)
│   ├── models/                  # SQLAlchemy ORM models
│   ├── routes/                  # Blueprint modules (auth, admin, host, player, etc.)
│   ├── security/                # Security layers (rate limiting, IDS, honeypot)
│   ├── services/                # Business logic
│   │   ├── s3_service.py       # AWS S3/IDrive e2 file uploads
│   │   ├── file_upload.py      # High-level upload helpers
│   │   └── cache/              # Caching strategies
│   ├── validators/              # Custom validators (file validation, etc.)
│   ├── templates/               # Jinja2 HTML templates
│   └── static/                  # CSS, JavaScript, images
├── docs/                        # Documentation
│   ├── DEPLOYMENT.md
│   ├── S3_FILE_STORAGE.md
│   ├── IDRIVE_E2_CORS_SETUP.md
│   └── ...
├── config.py                    # Configuration classes
├── wsgi.py                      # Production WSGI entry point (Gunicorn)
├── run.py                       # Development server entry point
├── requirements.txt             # Python dependencies
├── docker-compose.yml           # Docker orchestration
├── Dockerfile                   # Container definition
└── migrations/                  # Database migrations (Alembic)
```

**Tech Stack**:

- **Framework**: Flask 3.1+
- **ORM**: SQLAlchemy 2.0
- **Database**: PostgreSQL 15+
- **Caching**: Flask-Caching (simple, filesystem, Redis)
- **Storage**: AWS S3 / IDrive e2 with boto3
- **WSGI Server**: Gunicorn (production)
- **Container**: Docker + Docker Compose
- **Reverse Proxy**: Nginx (recommended for production)

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Git
- (Optional) AWS S3 or IDrive e2 account for file storage

### Local Development

```bash
# Clone repository
git clone https://github.com/your-username/DrishtriKon_CTF.git
cd DrishtriKon_CTF

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings (at minimum: SECRET_KEY, DATABASE_URL)

# Initialize database
flask db upgrade

# Run development server
python run.py
```

Visit: http://localhost:5000

### 🐳 Docker Quick Start

```bash
# Configure environment
cp .env.example .env
# Edit .env if needed

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec web flask db upgrade

# View logs
docker-compose logs -f
```

Visit: http://localhost:5000

---

## ⚙️ Configuration

### Required Environment Variables

```bash
# Flask & Security
SECRET_KEY=your-secret-key-min-32-chars
SESSION_SECRET=your-session-secret-min-32-chars

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/drishtrikon_ctf

# Email (Gmail)
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# reCAPTCHA
RECAPTCHA_SITE_KEY=your-site-key
RECAPTCHA_SECRET_KEY=your-secret-key

# AWS S3 / IDrive e2
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
AWS_PROFILE_BUCKET=drishtrikon-profiles
AWS_CHALLENGE_BUCKET=drishtrikon-challenges
```

See [.env.example](.env.example) for complete configuration.

---

## 🚢 Deployment

### Development

```bash
# Start development server with auto-reload
python run.py

# Or use Flask CLI
flask run
```

Access at: http://localhost:5000

### Production with Gunicorn

```bash
# Basic command
gunicorn wsgi:app --bind 0.0.0.0:${PORT}

# Recommended production settings
gunicorn wsgi:app \
  --bind 0.0.0.0:${PORT} \
  --workers 4 \
  --worker-class sync \
  --max-requests 1000 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
```

### Production with Docker

```bash
# Configure environment
cp .env.example .env
# Edit .env with production settings

# Build and run
docker-compose -f docker-compose.yml up -d

# Run migrations
docker-compose exec web flask db upgrade

# Check logs
docker-compose logs -f web
```

### Production with Nginx Reverse Proxy

```nginx
upstream gunicorn {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;
    client_max_body_size 16M;

    location / {
        proxy_pass http://gunicorn;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/app/static/;
        expires 30d;
    }
}
```

### Important Notes

⚠️ **Always use `wsgi:app`** - not `app:app` (uses application factory pattern)  
⚠️ **Set `FLASK_ENV=production`** in environment  
⚠️ **Enable HTTPS** with SSL certificate  
⚠️ **Configure all required env vars** before starting  
⚠️ **Run migrations** after deployment

---

## 📁 File Storage (S3/IDrive e2)

This platform includes secure cloud file storage integration:

- **Profile Pictures**: Stored in S3/IDrive e2 profiles bucket
- **Challenge Files**: PDFs, ZIPs stored in challenges bucket
- **Validation**: Multi-layer security (extension, MIME, magic bytes)
- **CORS**: Secure cross-origin access for your domain

### Setup S3/IDrive e2

1. Create buckets: `drishtrikon-profiles` and `drishtrikon-challenges`
2. Set environment variables (see Configuration section)
3. Configure CORS for your domain (see docs)

**Documentation**:

- [S3 File Storage Setup](docs/S3_FILE_STORAGE.md)
- [S3 Implementation Summary](docs/S3_IMPLEMENTATION_SUMMARY.md)
- [S3 Quick Reference](docs/S3_QUICK_REFERENCE.md)
- [IDrive e2 CORS Setup](docs/IDRIVE_E2_CORS_SETUP.md)
- [IDrive e2 CORS Testing](docs/IDRIVE_E2_CORS_TESTING.md)

---

## 🔐 Security

**Key Features**:

- Rate limiting on all endpoints
- Real-time intrusion detection
- Honeypot traps for attackers
- Strong session management
- CSRF protection
- Input validation and sanitization

**Best Practices**:

- Change all default secrets
- Enable HTTPS in production
- Monitor logs regularly
- Keep dependencies updated

---

## 📚 Documentation

Core Documentation:

- [Features Overview](docs/FEATURES.md)
- [Security Details](docs/SECURITY.md)
- [Database Resilience](docs/DATABASE_RESILIENCE.md)
- [Cache Management](docs/CACHE_MANAGEMENT.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

Cloud Storage & S3:

- [S3 File Storage Setup](docs/S3_FILE_STORAGE.md) - Complete AWS S3 integration guide
- [S3 Implementation Summary](docs/S3_IMPLEMENTATION_SUMMARY.md) - Technical details
- [S3 Quick Reference](docs/S3_QUICK_REFERENCE.md) - Developer quick start

IDrive e2 CORS Configuration:

- [CORS Setup Guide](docs/IDRIVE_E2_CORS_SETUP.md) - Complete setup instructions
- [CORS Quick Paste](docs/IDRIVE_E2_CORS_QUICK_PASTE.md) - Copy-paste ready configs
- [CORS Testing & Troubleshooting](docs/IDRIVE_E2_CORS_TESTING.md) - Testing procedures

Docker & Deployment:

- [Docker Guide](docs/DOCKER_GUIDE.md)
- [Docker Compose Configuration](docker-compose.yml)

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push and open a Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/DrishtriKon_CTF/issues)
- **Email**: support@your-domain.com

---

<div align="center">

**Made with ❤️ for the CTF community**

</div>
