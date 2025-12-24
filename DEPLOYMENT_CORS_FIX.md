# Workflow Deployment CORS Fix Implementation

## 🎯 **Problem Solved**

Fixed CORS error when accessing workflow deployment endpoint from external origins:

```
Access to fetch at 'https://aicc.uksouth.cloudapp.azure.com/api/workflow-deploy/{project_id}/'
from origin 'http://localhost:5500' has been blocked by CORS policy:
Response to preflight request doesn't pass access control check:
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

---

## ✅ **Solution Implemented**

Implemented **Django-Based CORS** with dynamic origin validation from database.

### **Architecture:**

```
Client (http://localhost:5500)
    ↓
    ↓ OPTIONS/POST request
    ↓
Nginx (reverse proxy)
    ↓ Passes through WITHOUT adding CORS headers
    ↓
Django WorkflowDeploymentCORSMiddleware
    ↓ Validates origin against WorkflowAllowedOrigin table
    ↓ Adds CORS headers dynamically
    ↓
Django View (public_chat_endpoint)
    ↓ Checks rate limit (per-origin)
    ↓ Executes workflow
    ↓
Response with CORS headers
```

---

## 📋 **Changes Made**

### **1. Nginx Configuration Updates**

#### **File: `nginx/nginx.dev.conf`** (Development)

**Added deployment-specific location block (HTTP):**
```nginx
# WORKFLOW DEPLOYMENT API - HTTP (CORS handled by Django)
location ~ ^/api/workflow-deploy {
    proxy_pass http://backend;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Extended timeout for workflow execution
    proxy_read_timeout 300s;
    proxy_connect_timeout 10s;
    proxy_send_timeout 300s;
    proxy_http_version 1.1;

    # NO CORS headers - Django middleware handles this
}
```

**Added deployment-specific location block (HTTPS):**
```nginx
# WORKFLOW DEPLOYMENT API - HTTPS (CORS handled by Django)
location ~ ^/api/workflow-deploy {
    proxy_pass http://backend;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;

    # Extended timeout for workflow execution
    proxy_read_timeout 300s;
    proxy_connect_timeout 10s;
    proxy_send_timeout 300s;
    proxy_http_version 1.1;

    # NO CORS headers - Django middleware handles this
}
```

**Updated existing API location to EXCLUDE deployment endpoints:**
```nginx
# Before:
location ~ ^/api/(?!public-chatbot) {

# After:
location ~ ^/api/(?!public-chatbot|workflow-deploy) {
```

#### **File: `nginx/nginx.conf`** (Production)

Same changes applied to both HTTP (port 80) and HTTPS (port 443) server blocks.

---

### **2. .gitignore Updates**

**File: `.gitignore`**

Removed exclusions for CORS-related implementation files so you can work on them from multiple repos:

```diff
-# =============================================================================
-# SCRIPTS FOLDER
-# =============================================================================
-# Local development scripts
-scripts/
-
-# =============================================================================
-# NGINX FOLDER
-# =============================================================================
-# Nginx configuration files
-nginx/
+# NOTE: scripts/ and nginx/ folders are now tracked in git
+# so you can work on them from multiple remote repositories
+# (k8s/ remains ignored as it's infrastructure config, not part of the implementation)
```

**Note:** The `k8s/` folder remains in `.gitignore` as it contains Kubernetes infrastructure configurations that are not required for the CORS implementation.

---

## 🔧 **Existing Django Implementation (Already in Place)**

### **Django CORS Middleware**

**File: `backend/agent_orchestration/middleware/deployment_cors.py`**

✅ Already implemented:
- Origin validation against `WorkflowAllowedOrigin` database table
- Handles both preflight (OPTIONS) and actual requests
- Adds appropriate CORS headers dynamically

### **Django Settings**

**File: `backend/core/settings.py:101`**

✅ Already enabled:
```python
MIDDLEWARE = [
    # ...
    'agent_orchestration.middleware.deployment_cors.WorkflowDeploymentCORSMiddleware',
    # ...
]
```

### **Rate Limiting**

**File: `backend/agent_orchestration/deployment_rate_limiter.py`**

✅ Already implemented:
- Per-origin rate limiting
- Uses Django cache for tracking
- Fallback to deployment-level rate limit if no origin-specific limit

**Priority (line 84-116):**
1. **Per-origin rate limit** (from `WorkflowAllowedOrigin.rate_limit_per_minute`)
2. **Deployment default rate limit** (from `WorkflowDeployment.rate_limit_per_minute`)

---

## 🧪 **Testing Instructions**

### **Step 1: Add Allowed Origin in Deploy Page**

1. Navigate to your project's **Deploy** section
2. Select a workflow and configure deployment settings
3. Click **"Add Allowed Origin"**
4. Enter origin: `http://localhost:5500`
5. Set rate limit (e.g., `10` requests/minute)
6. Click **Save**
7. **Activate** the deployment

### **Step 2: Restart Docker Containers**

```bash
# Restart Nginx and Backend to load new configuration
docker compose restart nginx backend

# Or restart all containers
docker compose restart
```

### **Step 3: Serve the Test HTML File**

**Option A: Using Python HTTP Server**
```bash
cd /home/alokkrsahu/ai_catalogue
python3 -m http.server 5500
```

**Option B: Using VS Code Live Server**
- Install "Live Server" extension
- Configure port 5500
- Right-click `test_deployment_cors.html` → "Open with Live Server"

### **Step 4: Run the Test**

1. Open browser: `http://localhost:5500/test_deployment_cors.html`
2. Enter your **Project ID** (UUID)
3. Verify **API Base URL** (default: `https://aicc.uksouth.cloudapp.azure.com`)
4. Enter a **test message**
5. Click **"🚀 Test CORS"**

### **Expected Success Response:**

```
✅ CORS SUCCESS!

Status: 200
Origin: http://localhost:5500
CORS Headers:
  - Access-Control-Allow-Origin: http://localhost:5500
  - Access-Control-Allow-Credentials: true

Response:
{
  "status": "success",
  "response": "...",
  "metadata": {
    "request_id": "...",
    "execution_time_ms": 1234,
    "workflow_name": "...",
    "session_id": "..."
  }
}
```

---

## 🔍 **Troubleshooting**

### **1. Still Getting CORS Error**

**Check:**
- ✅ Did you add `http://localhost:5500` to allowed origins in Deploy page?
- ✅ Is the deployment **active**?
- ✅ Did you restart Nginx and Backend containers?
- ✅ Is the project ID correct?

**Debug:**
```bash
# Check Nginx logs
docker compose logs -f nginx

# Check Django logs
docker compose logs -f backend | grep CORS

# Check Nginx config is loaded
docker compose exec nginx nginx -t
```

### **2. Rate Limit Exceeded**

**Error:**
```json
{
  "status": "error",
  "error": "Rate limit exceeded. Please try again later.",
  "retry_after": 42
}
```

**Solution:**
- Wait for the `retry_after` seconds
- Or increase the rate limit in Deploy page

### **3. Origin Not Allowed**

**Error (in Django logs):**
```
🚫 CORS: Origin http://localhost:5500 is not allowed for deployment {id}
```

**Solution:**
1. Go to Deploy page
2. Check allowed origins list
3. Ensure origin matches exactly (including protocol and port)
4. Make sure origin is **active** (not disabled)

---

## 📊 **Rate Limiting Behavior**

### **Per-Origin Rate Limits:**

| Origin | Rate Limit | Priority |
|--------|-----------|----------|
| `http://localhost:5500` | 10 req/min | **Highest** (per-origin) |
| `https://example.com` | 20 req/min | **Highest** (per-origin) |
| *Any other origin* | 10 req/min | **Fallback** (deployment default) |

### **Rate Limit Response Headers:**

The middleware adds standard rate limit headers:
- `Access-Control-Allow-Origin`: Validated origin
- `Access-Control-Allow-Methods`: `GET, POST, OPTIONS`
- `Access-Control-Allow-Headers`: `Origin, Content-Type, Accept, Authorization, X-Requested-With`
- `Access-Control-Allow-Credentials`: `true`
- `Access-Control-Max-Age`: `86400` (24 hours)

---

## 🎨 **User Experience Flow**

### **Deploy Page Workflow:**

```
1. User opens "Deploy" section
   ↓
2. User selects workflow from dropdown
   ↓
3. User clicks "Add Allowed Origin"
   ↓
4. User enters origin URL (e.g., http://localhost:5500)
   ↓
5. User sets per-origin rate limit (e.g., 10)
   ↓
6. User clicks "Save"
   ↓
7. Origin added to WorkflowAllowedOrigin table
   ↓
8. User activates deployment
   ↓
9. Django middleware validates requests from that origin
   ↓
10. External clients can now call the deployment endpoint!
```

---

## 🔐 **Security Features**

### **Origin Validation:**
- ✅ Exact match (case-insensitive)
- ✅ Protocol must match (http vs https)
- ✅ Port must match
- ✅ Trailing slashes are normalized

### **Rate Limiting:**
- ✅ Per-minute window (sliding)
- ✅ Per-origin tracking
- ✅ Cached in Django cache (Redis recommended for production)
- ✅ Returns `429 Too Many Requests` with `retry_after`

### **Deployment Validation:**
- ✅ Only **active** deployments can receive requests
- ✅ Deployment must have a **configured workflow**
- ✅ Origin must be in **allowed origins** list
- ✅ Origin must be **active** (not disabled)

---

## 📝 **API Response Examples**

### **Success Response:**
```json
{
  "status": "success",
  "response": "I can help you with document analysis, answering questions based on your uploaded documents, and providing intelligent insights.",
  "metadata": {
    "request_id": "deploy_20241224_120530_1234_a1b2c3d4",
    "execution_time_ms": 1523,
    "workflow_name": "Document Analysis Workflow",
    "session_id": "sess_abc123xyz"
  }
}
```

### **Rate Limit Error:**
```json
{
  "status": "error",
  "error": "Rate limit exceeded. Please try again later.",
  "retry_after": 42,
  "request_id": "deploy_20241224_120531_5678_e5f6g7h8"
}
```

### **Origin Not Allowed:**
```json
{
  "status": "error",
  "error": "Origin not allowed"
}
```

### **Deployment Not Found:**
```json
{
  "status": "error",
  "error": "No active deployment found for this project",
  "request_id": "deploy_20241224_120532_9012_i9j0k1l2"
}
```

---

## 🚀 **Next Steps**

1. **Test the fix** using the provided HTML test file
2. **Deploy to production** (Nginx config already updated)
3. **Monitor rate limits** in Django admin or logs
4. **Add additional allowed origins** as needed via Deploy page

---

## 📚 **Related Files**

- **Nginx Config (Dev):** `nginx/nginx.dev.conf`
- **Nginx Config (Prod):** `nginx/nginx.conf`
- **Django Middleware:** `backend/agent_orchestration/middleware/deployment_cors.py`
- **Rate Limiter:** `backend/agent_orchestration/deployment_rate_limiter.py`
- **Deployment Views:** `backend/agent_orchestration/deployment_views.py`
- **Test File:** `test_deployment_cors.html`
- **Models:** `backend/agent_orchestration/models.py`

---

## ✅ **Summary**

**What was the problem?**
- CORS error when accessing deployment endpoint from external origins
- Nginx was adding its own CORS headers with hardcoded whitelist
- Dynamically added origins in Deploy page were ignored

**What's the solution?**
- Nginx now **bypasses** CORS for `/api/workflow-deploy/*`
- Django middleware **handles CORS** with database validation
- Per-origin rate limiting works as designed
- Users can add allowed origins via Deploy page UI

**What's already implemented?**
- ✅ Django CORS middleware
- ✅ Rate limiting (per-origin + deployment fallback)
- ✅ Origin validation against database
- ✅ Deploy page UI for managing origins

**What was changed?**
- ✅ Nginx configuration (exclude deployment endpoints from CORS)
- ✅ .gitignore (allow scripts, k8s, nginx folders in git)

---

**Implementation Date:** December 24, 2024
**Status:** ✅ **Ready for Testing**
