# Stable Apps Document Vectorizer - Deployment Guide

## Overview
This is a production-ready deployment of the document-vectorizer application, optimized for stability and memory management. The deployment includes critical bug fixes, memory corruption prevention, and enhanced rate limiting.

## 🔧 Recent Fixes and Improvements

### Critical Bug Fixes
- ✅ Fixed `web_app.py:468` AttributeError for `alert_email`
- ✅ Added missing `convert_token_to_pickle.py` OAuth utility

### Memory Management Improvements
- ✅ File size limits: 50MB maximum per file
- ✅ PDF processing limits: 1000 pages maximum
- ✅ Excel processing limits: 100,000 rows maximum
- ✅ Aggressive garbage collection after document processing
- ✅ Memory usage monitoring and logging
- ✅ Docker memory limit increased from 2G to 4G

### Performance Optimizations
- ✅ Polling interval increased from 60s to 300s (5 minutes)
- ✅ Google Drive API caching (2-minute cache duration)
- ✅ API rate limiting: 10 calls/second maximum
- ✅ File tracker moved from `/tmp` to persistent volume
- ✅ Conservative batch processing settings

### UI Settings Persistence (NEW)
- ✅ **Polling interval updates from UI now persist across Docker restarts**
- ✅ Runtime settings stored in `config/runtime_settings.json`
- ✅ Dynamic schedule updates (changes take effect immediately)
- ✅ UI feedback shows persistence status and schedule updates
- ✅ Settings validation with proper error handling

### Resource Management
- ✅ Persistent volumes for data, logs, cache, and tracker
- ✅ Health checks and auto-restart policies
- ✅ Proper user permissions and security settings
- ✅ Enhanced logging with rotation

## 🚀 Deployment Instructions

### Prerequisites
1. **VPS Access**: SSH access to 69.62.70.133 as `stable-admin`
2. **Docker**: Docker and docker-compose installed
3. **Google Cloud Project**: Fresh OAuth credentials needed
4. **Existing Services**: 
   - Same OpenAI API key (with new rate limiting)
   - Same Google Drive folder
   - Same Supabase database

### Step 1: Deploy to VPS

```bash
# SSH to VPS
ssh stable-admin@69.62.70.133

# Clone or update the repository
cd /path/to/document-vectorizer-main

# Make deployment script executable
chmod +x deploy-stable.sh

# Run deployment
./deploy-stable.sh
```

### Step 2: Configure Environment

Edit `.env.stable` with your actual credentials:

```bash
# Update these values in .env.stable
GOOGLE_DRIVE_FOLDER_ID=your_actual_folder_id
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key
OPENAI_API_KEY=sk-your-openai-key
```

### Step 3: Setup Google OAuth

1. **Create new Google Cloud Project** (recommended for fresh start)
2. **Download client_secrets.json** and place at `config/client_secrets.json`
3. **Generate OAuth token** using the provided utility:

```bash
# Use the improved token converter
python convert_token_to_pickle.py /path/to/your/oauth_token.json
```

### Step 4: Restart and Verify

```bash
# Restart with new configuration
docker-compose -f docker-compose.stable.yml down
docker-compose -f docker-compose.stable.yml up -d

# Check status
docker-compose -f docker-compose.stable.yml logs -f
```

### Step 5: Test Settings Persistence (Optional)

```bash
# Run the persistence test
python3 test_persistence.py

# Test polling interval persistence via UI:
# 1. Go to http://69.62.70.133:8001
# 2. Change polling interval to 3600 seconds
# 3. Restart container: docker-compose -f docker-compose.stable.yml restart
# 4. Verify setting persisted in UI
```

## 📊 Monitoring and Management

### Dashboard Access
- **URL**: http://69.62.70.133:8001
- **Container**: `document-vectorizer-stable`
- **Internal Port**: 5555 (mapped to external 8001)

### Key Commands

```bash
# View logs
docker-compose -f docker-compose.stable.yml logs -f

# Check resource usage
docker stats document-vectorizer-stable

# Restart application
docker-compose -f docker-compose.stable.yml restart

# Stop application  
docker-compose -f docker-compose.stable.yml down

# Update and redeploy
git pull origin main
./deploy-stable.sh
```

### Health Monitoring
- Health check endpoint: `http://69.62.70.133:8001/health`
- Automatic restart on failures
- Memory usage logging every processing cycle

## ⚙️ Configuration Details

### Conservative Settings Applied
- **Polling Interval**: 300s (5 minutes) - reduced API pressure
- **Batch Size**: 5 documents - lower memory usage
- **Chunk Size**: 300 tokens - smaller memory footprint  
- **Rate Limits**: 8/min, 80/hour, 800/day - very conservative
- **File Limits**: 50MB max, 1000 PDF pages, 100K Excel rows

### Memory Management
- Docker memory limit: 4GB (up from 2GB)
- Automatic garbage collection after each file
- Memory usage monitoring and alerting
- Persistent volumes instead of temporary storage

### Rate Limiting (New Feature)
- Daily cost limit: $10 USD
- Request throttling at multiple levels
- OpenAI API cost tracking
- Automatic shutdown on limit breach

## 🚨 Troubleshooting

### Common Issues

1. **Memory Corruption**: 
   - Fixed with file size limits and garbage collection
   - Monitor with: `docker stats document-vectorizer-stable`

2. **OAuth Issues**:
   - Use fresh Google Cloud project
   - Regenerate client secrets and token
   - Check file permissions on config files

3. **Rate Limiting**:
   - Monitor daily costs in dashboard
   - Adjust limits in `.env.tnt` if needed
   - Check OpenAI API usage

4. **Container Won't Start**:
   ```bash
   # Check logs for specific errors
   docker-compose -f docker-compose.stable.yml logs
   
   # Verify environment file
   cat .env.stable
   
   # Check file permissions
   ls -la config/
   ```

### Emergency Recovery
If the application crashes with memory corruption:

```bash
# Immediate restart
docker-compose -f docker-compose.stable.yml restart

# If that fails, force recreation
docker-compose -f docker-compose.stable.yml down
docker system prune -f
./deploy-stable.sh
```

## 📈 Success Metrics

The deployment is successful when:
- ✅ Application runs without memory corruption crashes
- ✅ Rate limiting prevents OpenAI cost overruns  
- ✅ Conservative polling reduces system stress
- ✅ File tracker persists across restarts
- ✅ Dashboard accessible at http://69.62.70.133:8001
- ✅ Documents processed without size-related errors

## 📞 Support

For issues with this deployment:
1. Check the troubleshooting section above
2. Review logs: `docker-compose -f docker-compose.stable.yml logs`
3. Verify all configuration files are correct
4. Ensure all prerequisites are met

---

**Deployment completed**: Focus on stability over speed with conservative settings to prevent the memory corruption issues experienced in the previous deployment.