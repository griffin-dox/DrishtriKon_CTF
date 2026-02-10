# 🚀 Deployment Guide - DrishtriKon CTF Platform

Complete production deployment guide for the DrishtriKon CTF platform.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Docker Deployment](#docker-deployment-recommended)
- [Manual Deployment](#manual-deployment)
- [Cloud Deployment](#cloud-deployment)
- [SSL/TLS Configuration](#ssltls-configuration)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **OS**: Ubuntu 20.04+ / Debian 11+ / RHEL 8+
- **CPU**: 2+ cores
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 20GB+ available space
- **Network**: Public IP with ports 80/443 open

### Software Requirements

- Docker 24+ & Docker Compose 2.20+
- PostgreSQL 15+ (if not using Docker)
- Nginx 1.24+ (if not using Docker nginx)
- Python 3.11+ (for manual deployment)
- Git

---

## Docker Deployment (Recommended)

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -SL https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 2. Application Setup

```bash
# Clone repository
cd /opt
sudo git clone https://github.com/your-username/DrishtriKon_CTF.git
cd DrishtriKon_CTF

# Configure environment
cp .env.example .env
sudo nano .env

# Required variables:
# - SECRET_KEY (32+ chars random string)
# - SESSION_SECRET (32+ chars random string)
# - POSTGRES_PASSWORD (strong password)
# - MAIL_USERNAME and MAIL_PASSWORD
# - RECAPTCHA keys (recommended)
```

### 3. Deploy

```bash
# Build and start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f web

# Run database migrations
docker-compose exec web flask db upgrade

# Create admin user (optional)
docker-compose exec web python -c "from app import create_app; from app.models import User; app = create_app(); with app.app_context(): admin = User(username='admin', email='admin@example.com'); admin.set_password('change-this-password'); admin.role = 'OWNER'; admin.email_verified = True; from app.extensions import db; db.session.add(admin); db.session.commit()"
```

### 4. With Nginx Reverse Proxy

```bash
# Start with nginx profile
docker-compose --profile with-nginx up -d

# Or use standalone nginx (see SSL section)
```

---

## Manual Deployment

### 1. Install Dependencies

```bash
# Python and PostgreSQL
sudo apt install python3.11 python3.11-venv python3-pip postgresql-15

# System dependencies
sudo apt install libpq-dev gcc
```

### 2. Database Setup

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE drishtrikon_ctf;
CREATE USER ctf_user WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE drishtrikon_ctf TO ctf_user;
\q
```

### 3. Application Setup

```bash
# Create app directory
sudo mkdir -p /opt/drishtrikon-ctf
cd /opt/drishtrikon-ctf

# Clone repository
sudo git clone https://github.com/your-username/DrishtriKon_CTF.git .

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt gunicorn

# Configure
cp .env.example .env
nano .env

# Run migrations
flask db upgrade
```

### 4. Systemd Service

Create `/etc/systemd/system/drishtrikon.service`:

```ini
[Unit]
Description=DrishtriKon CTF Platform
After=network.target postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/drishtrikon-ctf
Environment="PATH=/opt/drishtrikon-ctf/.venv/bin"
Environment="FLASK_ENV=production"
ExecStart=/opt/drishtrikon-ctf/.venv/bin/gunicorn \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --threads 2 \
    --timeout 60 \
    --access-logfile /var/log/drishtrikon/access.log \
    --error-logfile /var/log/drishtrikon/error.log \
    wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Create log directory
sudo mkdir -p /var/log/drishtrikon
sudo chown www-data:www-data /var/log/drishtrikon

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable drishtrikon
sudo systemctl start drishtrikon
sudo systemctl status drishtrikon
```

---

## Cloud Deployment

### AWS EC2

```bash
# Launch EC2 instance (t3.medium recommended)
# Security Group: Allow 22, 80, 443

# Connect and follow Docker deployment steps
ssh -i your-key.pem ubuntu@your-instance-ip

# Configure AWS RDS for PostgreSQL (recommended)
# Update DATABASE_URL in .env with RDS endpoint
```

### DigitalOcean Droplet

```bash
# Create Droplet (2 vCPU, 4GB RAM)
# Follow Docker deployment steps

# Use DO Managed PostgreSQL
# Update DATABASE_URL with managed database connection
```

### Azure Container Instances

```bash
# Build and push image
docker build -t your-registry.azurecr.io/drishtrikon-ctf:latest .
docker push your-registry.azurecr.io/drishtrikon-ctf:latest

# Deploy with Azure CLI
az container create \
    --resource-group myResourceGroup \
    --name drishtrikon-ctf \
    --image your-registry.azurecr.io/drishtrikon-ctf:latest \
    --cpu 2 --memory 4 \
    --ports 80 443 \
    --environment-variables DATABASE_URL=... SECRET_KEY=...
```

---

## SSL/TLS Configuration

### Using Let's Encrypt (Certbot)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# For Docker nginx
docker-compose exec nginx certbot --nginx -d your-domain.com

# For standalone nginx
sudo certbot --nginx -d your-domain.com

# Auto-renewal (runs twice daily)
sudo systemctl status certbot.timer
```

### Manual SSL Certificate

```bash
# Place certificates
sudo mkdir -p /opt/drishtrikon-ctf/nginx/ssl
sudo cp your-cert.pem /opt/drishtrikon-ctf/nginx/ssl/cert.pem
sudo cp your-key.pem /opt/drishtrikon-ctf/nginx/ssl/key.pem
sudo chmod 600 /opt/drishtrikon-ctf/nginx/ssl/key.pem

# Update nginx.conf to use certificates
# Restart nginx
docker-compose restart nginx
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check application health
curl http://localhost:8000/healthz

# Check all services
docker-compose ps

# View resource usage
docker stats
```

### Log Monitoring

```bash
# Application logs
docker-compose logs -f web

# Nginx logs
docker-compose logs -f nginx

# Database logs
docker-compose logs -f db

# Specific timeframe
docker-compose logs --since "2024-02-10T12:00:00" web
```

### Database Backups

```bash
# Automated daily backup
cat > /opt/drishtrikon-ctf/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/drishtrikon"
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T db pg_dump -U ctf_user drishtrikon_ctf | gzip > $BACKUP_DIR/backup_$DATE.sql.gz
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete
EOF

chmod +x /opt/drishtrikon-ctf/backup.sh

# Add to crontab
echo "0 2 * * * /opt/drishtrikon-ctf/backup.sh" | sudo crontab -
```

### Updates & Maintenance

```bash
# Pull latest changes
cd /opt/drishtrikon-ctf
git pull origin main

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d --force-recreate

# Run new migrations
docker-compose exec web flask db upgrade

# Clear cache
docker-compose exec web python -c "from app.extensions import cache; from app import create_app; app = create_app(); with app.app_context(): cache.clear()"
```

---

## Troubleshooting

### Common Issues

**Container won't start**

```bash
# Check logs
docker-compose logs web

# Check environment variables
docker-compose exec web env | grep -E "SECRET_KEY|DATABASE_URL"

# Rebuild
docker-compose build --no-cache web
docker-compose up -d web
```

**Database connection errors**

```bash
# Check database is running
docker-compose ps db

# Test connection
docker-compose exec db psql -U ctf_user -d drishtrikon_ctf -c "SELECT 1"

# Check DATABASE_URL format
# postgresql://user:password@host:port/database
```

**502 Bad Gateway (Nginx)**

```bash
# Check upstream is running
docker-compose ps web

# Check nginx config
docker-compose exec nginx nginx -t

# Restart nginx
docker-compose restart nginx
```

**High memory usage**

```bash
# Check stats
docker stats

# Reduce Gunicorn workers in docker-compose.yml
# CMD ["gunicorn", "--workers", "2", ...]

# Clear cache
docker-compose exec web python -c "from app.services.cache.management import emergency_clear_cache; from app import create_app; app = create_app(); with app.app_context(): emergency_clear_cache()"
```

---

## Performance Tuning

### Database Optimization

```bash
# Increase connection pool
# In .env
SQLALCHEMY_ENGINE_OPTIONS='{"pool_size": 30, "max_overflow": 50}'

# Create indexes (run once)
docker-compose exec web python -c "from app.services.db_optimization import create_performance_indexes; from app import create_app; app = create_app(); with app.app_context(): create_performance_indexes()"
```

### Caching

```bash
# Enable Redis cache for better performance
docker-compose --profile with-redis up -d

# Update .env
CACHE_TYPE=redis
REDIS_URL=redis://:your-password@redis:6379/0
```

### Gunicorn Workers

```bash
# Calculate optimal workers: (2 × CPU cores) + 1
# For 2 CPU cores: 5 workers

# Update docker-compose.yml or systemd service
--workers 5 --threads 2
```

---

## Security Checklist

- [ ] Change all default secrets (SECRET_KEY, SESSION_SECRET, database passwords)
- [ ] Enable HTTPS/SSL
- [ ] Configure firewall (ufw/iptables)
- [ ] Set up regular backups
- [ ] Enable Discord/Slack security alerts
- [ ] Configure fail2ban for SSH protection
- [ ] Review and update security headers in nginx.conf
- [ ] Enable reCAPTCHA
- [ ] Monitor logs for suspicious activity
- [ ] Keep Docker images and system packages updated

---

## Support

For deployment issues:

- Check [Troubleshooting](#troubleshooting) section
- Review logs: `docker-compose logs -f`
- Open issue: https://github.com/your-username/DrishtriKon_CTF/issues

---

**Last Updated**: February 2026
