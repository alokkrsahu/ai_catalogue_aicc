# Docker Build Network Error - Enhanced Fix V2

## 🔍 Problem

**Error:**
```
Err: Unable to connect to deb.debian.org:http: [IP: 151.101.190.132 80]
```

**Root Cause:**
- Docker build cannot connect to Debian package repositories
- Using `python:3.13-slim` which is based on Debian Trixie (testing/unstable)
- Network connectivity issues during package installation
- Some packages are failing to download

---

## ✅ Enhanced Fixes Applied

### Fix 1: Use Stable Debian Base Image

**Changed from:**
```dockerfile
FROM python:3.13-slim
```

**Changed to:**
```dockerfile
FROM python:3.13-slim-bookworm
```

**Why:**
- `bookworm` is Debian 12 (stable) - more reliable mirrors
- `trixie` is Debian 13 (testing) - may have connectivity issues
- Stable releases have better mirror availability

### Fix 2: Split Package Installation

**Strategy:**
1. **Essential packages** (must succeed): curl, wget, build tools, Python dev, PostgreSQL dev
2. **Document processing** (retry on failure): poppler, tesseract, antiword, unrtf
3. **Audio processing** (optional): flac, ffmpeg, sox, etc. - continue even if they fail

**Benefits:**
- Build can complete even if some optional packages fail
- Essential functionality still works
- Better error isolation

### Fix 3: Enhanced Retry Logic

**Added:**
- Retry `apt-get update` up to 3 times with 10-second delays
- Retry document processing tools installation if first attempt fails
- Continue build even if optional audio packages fail

### Fix 4: Docker Compose Network Configuration

**Added to `docker-compose.yml`:**
```yaml
backend:
  build:
    network: host
```

**Why:**
- Uses host network during build for better connectivity
- Bypasses Docker's default bridge network
- May resolve DNS/connectivity issues

---

## 🚀 Quick Solutions

### Solution 1: Rebuild with Fixed Dockerfile (Recommended)
```bash
docker compose build --no-cache backend
```

### Solution 2: Build with Host Network Explicitly
```bash
DOCKER_BUILDKIT=1 docker compose build --network=host backend
```

### Solution 3: Build Individual Service
```bash
docker compose build --no-cache backend
```

### Solution 4: Use Alternative Base Image (If Still Failing)

If issues persist, you can temporarily use Python 3.12 which uses Debian Bookworm:

```dockerfile
FROM python:3.12-slim-bookworm
```

Then rebuild:
```bash
docker compose build --no-cache backend
```

---

## 🔧 Alternative: Minimal Package Installation

If network issues persist, you can create a minimal Dockerfile that only installs essential packages:

```dockerfile
FROM python:3.13-slim-bookworm

WORKDIR /app

# Install only essential packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        wget \
        build-essential \
        python3-dev \
        libpq-dev \
        pkg-config \
        git \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Optional: Install document processing tools later if needed
# RUN apt-get update && apt-get install -y poppler-utils tesseract-ocr
```

---

## 📊 Package Priority

### Tier 1: Essential (Must Install)
- curl, wget, ca-certificates, gnupg2
- build-essential, python3-dev
- libpq-dev (PostgreSQL)
- pkg-config, git
- libxml2-dev, libxslt1-dev (XML processing)
- libjpeg-dev, libmagic1 (Image/file type detection)

### Tier 2: Important (Retry on Failure)
- poppler-utils (PDF processing)
- tesseract-ocr (OCR)
- antiword, unrtf (Document conversion)

### Tier 3: Optional (Continue if Fails)
- flac, ffmpeg, lame (Audio processing)
- libmad0, libsox-fmt-mp3, sox (Audio tools)
- swig, libpulse-dev (Audio libraries)

---

## 🧪 Testing

### Test Network Connectivity
```bash
# Test if you can reach Debian repositories
docker run --rm --network=host python:3.13-slim-bookworm \
    sh -c "apt-get update && echo 'Network OK'"
```

### Test Build
```bash
# Clean build
docker compose build --no-cache backend

# Check build logs for errors
docker compose build backend 2>&1 | tee build.log
```

---

## 🔍 Troubleshooting

### If Still Getting Network Errors:

1. **Check your internet connection:**
   ```bash
   curl -I http://deb.debian.org/debian/
   ```

2. **Try different DNS:**
   Add to `docker-compose.yml`:
   ```yaml
   backend:
     dns:
       - 8.8.8.8
       - 1.1.1.1
   ```

3. **Use proxy if behind firewall:**
   ```bash
   export HTTP_PROXY=http://proxy:port
   export HTTPS_PROXY=http://proxy:port
   docker compose build backend
   ```

4. **Build without cache:**
   ```bash
   docker compose build --no-cache --pull backend
   ```

---

## ✅ Summary

**Changes Made:**
1. ✅ Changed base image to `python:3.13-slim-bookworm` (stable Debian)
2. ✅ Split packages into essential/optional tiers
3. ✅ Added retry logic with delays
4. ✅ Made audio packages optional (continue on failure)
5. ✅ Added `network: host` to docker-compose build config

**Expected Result:**
- Build should complete even if some optional packages fail
- Essential functionality will work
- Better network reliability with stable Debian base

---

## 🚀 Next Steps

1. **Try rebuilding:**
   ```bash
   docker compose build --no-cache backend
   ```

2. **If still failing, check which packages are failing:**
   - If essential packages fail → network/DNS issue
   - If only optional packages fail → build will succeed

3. **Monitor build logs** to see which tier of packages is failing

