# 🧪 CORS Fix Testing Steps

## Quick Testing Guide

### **Prerequisites:**
1. ✅ Project created with workflow deployed
2. ✅ Docker containers running

### **Step-by-Step Testing:**

#### **1. Add Allowed Origin** (via UI)

Navigate to: `http://localhost:5173/features/intellidoc/project/{your-project-id}`

1. Click on **"Deploy"** tab (page 4)
2. Select a workflow from dropdown
3. Set rate limit (e.g., 10 req/min)
4. Click **"Add Allowed Origin"**
5. Enter: `http://localhost:5500`
6. Set per-origin rate limit: `10`
7. Click **Save**
8. Toggle deployment to **Active**

#### **2. Restart Services**

```bash
cd /home/alokkrsahu/ai_catalogue
docker compose restart nginx backend
```

Wait ~10 seconds for services to restart.

#### **3. Serve Test HTML File**

```bash
# In the ai_catalogue directory
python3 -m http.server 5500
```

Keep this terminal open.

#### **4. Run Test**

1. Open browser: `http://localhost:5500/test_deployment_cors.html`
2. Enter your **Project ID** (get it from the URL when viewing the project)
3. Click **"🚀 Test CORS"**

#### **Expected Success:**

```
✅ CORS SUCCESS!

Status: 200
Origin: http://localhost:5500
CORS Headers:
  - Access-Control-Allow-Origin: http://localhost:5500
  - Access-Control-Allow-Credentials: true
```

---

## 🔍 Quick Verification Checklist

- [ ] Allowed origin added in Deploy page
- [ ] Deployment is **Active**
- [ ] Nginx restarted
- [ ] Backend restarted
- [ ] Test HTML served on port 5500
- [ ] Browser shows success response

---

## 🐛 Debugging Commands

```bash
# Check if containers are running
docker compose ps

# Check Nginx config syntax
docker compose exec nginx nginx -t

# Watch Nginx logs
docker compose logs -f nginx | grep workflow-deploy

# Watch Django CORS logs
docker compose logs -f backend | grep CORS

# Check allowed origins in Django admin
# Navigate to: http://localhost:5173/admin/
# Login and check WorkflowAllowedOrigin table
```

---

## 📋 Files Created/Modified

### **Modified:**
1. `nginx/nginx.dev.conf` - Added deployment endpoint CORS bypass
2. `nginx/nginx.conf` - Added deployment endpoint CORS bypass (production)
3. `.gitignore` - Removed scripts/ and nginx/ exclusions (k8s/ remains ignored)

### **Created:**
1. `test_deployment_cors.html` - CORS testing tool
2. `DEPLOYMENT_CORS_FIX.md` - Comprehensive documentation
3. `TESTING_STEPS.md` - This file

---

## ✅ Rate Limiting Verification

Test rate limiting by clicking "🚀 Test CORS" rapidly (>10 times in 1 minute).

**Expected Error:**
```json
{
  "status": "error",
  "error": "Rate limit exceeded. Please try again later.",
  "retry_after": 42
}
```

This confirms per-origin rate limiting is working!

---

## 🎯 Success Criteria

✅ CORS error is gone
✅ Response includes correct CORS headers
✅ Rate limiting works per-origin
✅ Multiple origins can be added
✅ Origins can be removed/disabled

---

**Ready to test!** 🚀
