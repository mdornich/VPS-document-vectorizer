# Hostinger Docker Deployment Guide

## Prerequisites

1. **Hostinger VPS** with Docker support (KVM-based VPS recommended)
2. **Domain** pointed to your Hostinger VPS IP
3. **SSH access** to your VPS
4. **Docker and Docker Compose** installed

## Step 1: Server Setup

### 1.1 Connect to your Hostinger VPS

```bash
ssh root@your-vps-ip
```

### 1.2 Install Docker (if not already installed)

```bash
# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt-get install docker-compose-plugin -y

# Verify installation
docker --version
docker compose version
```

### 1.3 Configure Firewall

```bash
# Allow SSH
ufw allow 22/tcp

# Allow dashboard port
ufw allow 5555/tcp

# Enable firewall
ufw enable
```

## Step 2: Deploy Application

### 2.1 Clone Repository

```bash
# Create app directory
mkdir -p /opt/document-vectorizer
cd /opt/document-vectorizer

# Clone your repository (or upload files via SFTP)
git clone https://github.com/yourusername/document-vectorizer.git .
```

### 2.2 Setup Credentials

```bash
# Create credentials directory
mkdir -p credentials

# Upload your Google Cloud credentials JSON file
# Use SFTP or SCP to upload google-credentials.json to:
# /opt/document-vectorizer/credentials/google-credentials.json
```

### 2.3 Configure Environment

```bash
# Copy production environment template
cp .env.production .env

# Edit with your actual values
nano .env
```

Required environment variables:

```env
# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/google-credentials.json
GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key_here

# OpenAI
OPENAI_API_KEY=sk-your_api_key_here

# Email (Gmail)
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password_here
ALERT_EMAIL=admin@yourdomain.com

# Security
FLASK_SECRET_KEY=generate_a_secure_key_here
```

### 2.4 Build and Start

```bash
# Build the Docker image
docker compose -f docker-compose.production.yml build

# Start the application
docker compose -f docker-compose.production.yml up -d

# Check logs
docker compose -f docker-compose.production.yml logs -f
```

## Step 3: Configure Nginx (Optional but Recommended)

### 3.1 Install Nginx

```bash
apt-get install nginx -y
```

### 3.2 Configure Reverse Proxy

Create `/etc/nginx/sites-available/vectorizer`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5555;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3.3 Enable Site

```bash
ln -s /etc/nginx/sites-available/vectorizer /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### 3.4 Setup SSL with Let's Encrypt

```bash
apt-get install certbot python3-certbot-nginx -y
certbot --nginx -d your-domain.com
```

## Step 4: Monitoring and Maintenance

### 4.1 Health Check

```bash
# Check application health
curl http://localhost:5555/api/health

# Check Docker status
docker compose -f docker-compose.production.yml ps
```

### 4.2 View Logs

```bash
# Application logs
docker compose -f docker-compose.production.yml logs vectorizer

# Follow logs in real-time
docker compose -f docker-compose.production.yml logs -f vectorizer
```

### 4.3 Restart Application

```bash
docker compose -f docker-compose.production.yml restart
```

### 4.4 Update Application

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d
```

## Step 5: Backup Strategy

### 5.1 Automated Backups

Create `/opt/document-vectorizer/backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/document-vectorizer"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup Docker volumes
docker run --rm \
  -v vectorizer-data:/data \
  -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/data_$DATE.tar.gz -C / data

# Backup environment file
cp /opt/document-vectorizer/.env $BACKUP_DIR/env_$DATE

# Keep only last 7 days of backups
find $BACKUP_DIR -type f -mtime +7 -delete
```

### 5.2 Schedule Backups

```bash
# Make backup script executable
chmod +x /opt/document-vectorizer/backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/document-vectorizer/backup.sh") | crontab -
```

## Step 6: Monitoring with Uptime Robot

1. Sign up for [Uptime Robot](https://uptimerobot.com/) (free tier available)
2. Add new monitor:
   - Monitor Type: HTTP(s)
   - URL: `https://your-domain.com/api/health`
   - Monitoring Interval: 5 minutes
   - Alert Contacts: Your email

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose -f docker-compose.production.yml logs

# Check permissions
ls -la credentials/
chmod 600 credentials/google-credentials.json
```

### Out of memory

```bash
# Check memory usage
docker stats

# Adjust memory limits in docker-compose.production.yml
```

### Connection issues

```bash
# Check if port is listening
netstat -tlnp | grep 5555

# Check firewall
ufw status

# Test locally
curl http://localhost:5555/api/health
```

## Security Checklist

- [ ] Changed default passwords
- [ ] Configured firewall (ufw)
- [ ] SSL certificate installed
- [ ] Regular security updates scheduled
- [ ] Backup strategy implemented
- [ ] Monitoring configured
- [ ] Non-root user for Docker (in Dockerfile)
- [ ] Secrets in environment variables (not in code)

## Support

For issues specific to the Document Vectorizer application, check:
- Application logs: `docker compose logs`
- Dashboard: `https://your-domain.com`
- Health endpoint: `https://your-domain.com/api/health`

For Hostinger-specific issues:
- Hostinger Support: https://www.hostinger.com/support
- Hostinger Knowledge Base: https://support.hostinger.com/