# Deployment Guide

## Railway Deployment

### Prerequisites
1. [Railway account](https://railway.app/)
2. GitHub repository connected

### Quick Deploy

1. **Connect Repository**
   - Go to [Railway](https://railway.app/)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose `timf34/arxiv2md`

2. **Railway Auto-Detection**
   - Railway will automatically detect Python
   - It will use `Procfile` or `railway.toml` for deployment config
   - Dependencies from `requirements.txt` will be installed

3. **Environment Variables** (Optional)
   - Railway will automatically set `PORT`
   - All other variables have sensible defaults
   - Optional variables (if needed):
     ```
     APP_VERSION=0.1.0
     APP_REPOSITORY=https://github.com/timf34/arxiv2md
     ARXIV2MD_CACHE_TTL_SECONDS=86400
     ```

4. **Deploy**
   - Railway will automatically deploy on push to main
   - Your app will be available at: `https://your-app.railway.app`

### Local Cache vs S3

**Current Setup**: Local file cache (`.arxiv2md_cache/`)
- ✅ Simple, no additional setup
- ❌ Cache cleared on each deploy
- ❌ Not shared across instances

**Future: S3 Cache** (Optional improvement)
- ✅ Persistent across deploys
- ✅ Shared across instances
- ℹ️ Requires AWS S3 bucket setup

### Health Check

After deployment, verify the app is running:
```bash
curl https://your-app.railway.app/health
```

Should return: `{"status":"healthy"}`

### Monitoring

Railway provides built-in:
- Deployment logs
- Runtime logs
- Metrics dashboard
- Auto-restart on failures

### Custom Domain (Optional)

1. Go to your Railway project settings
2. Click "Domains"
3. Add your custom domain
4. Update DNS records as instructed

---

## Manual Deployment (Local Testing)

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

# Or use the CLI
python -m arxiv2md 2501.11120v1 -o output.txt
```

## Troubleshooting

### Port Issues
Railway sets `$PORT` automatically. The Procfile uses this:
```
web: uvicorn server.main:app --host 0.0.0.0 --port $PORT
```

### Static Files Not Loading
Check that `src/static/` is committed to git and included in the deployment.

### Module Import Errors
Ensure `src/` is in the Python path. Railway should detect this automatically.

### Cache Issues
Cache is ephemeral on Railway's free tier. For production, consider:
- Railway's persistent volumes (paid)
- S3 bucket integration
