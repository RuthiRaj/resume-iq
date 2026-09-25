# ResumeIQ Containerization & Production Runtime Guide

This document describes the container architecture, multi-stage OCI image builds, Docker Compose local orchestration, health/readiness endpoints, security hardening, and operational runbook for ResumeIQ.

---

## 1. System Architecture

```text
               Client Web Browser
                       │ (HTTP/HTTPS :3000)
                       ▼
       ┌─────────────────────────────────┐
       │   resumeiq-frontend (Container) │
       │   Next.js 15 Standalone + BFF   │
       │   Non-root (nextjs UID 10001)   │
       └────────────────┬────────────────┘
                        │ (Internal HTTP :8000 on resumeiq-network)
                        │ (BACKEND_API_URL=http://backend:8000)
                        ▼
       ┌─────────────────────────────────┐
       │   resumeiq-backend (Container)  │
       │   FastAPI ASGI AI ATS Engine    │
       │   Non-root (appuser UID 10001)  │
       └────────┬───────────────┬────────┘
                │               │
       (HTTPS Outbound)  (HTTPS Outbound)
                ▼               ▼
        Firebase Firestore  AI Provider Chain
        & Cloudinary        (Groq, Gemini, NVIDIA)
```

---

## 2. Container Images

Both images use multi-stage builds to produce minimal, hardened, unprivileged runtime artifacts.

### Backend (`backend/Dockerfile`)
- **Base Builder**: `python:3.11-slim`
- **Base Runtime**: `python:3.11-slim`
- **User**: `appuser` (`UID 10001`, `GID 10001`)
- **Port**: `8000`
- **Healthcheck**: `GET /health` every 30s
- **Entrypoint**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Stateless Invariant**: In-memory stream processing (`io.BytesIO`). No persistent local disk state required.

### Frontend (`frontend/Dockerfile`)
- **Base Builder**: `node:20-alpine` (`npm ci` & `npm run build` with `output: "standalone"`)
- **Base Runtime**: `node:20-alpine`
- **User**: `nextjs` (`UID 10001`, `GID 10001`)
- **Port**: `3000`
- **Healthcheck**: `GET /` every 30s via `wget`
- **Entrypoint**: `node server.js`

---

## 3. Quickstart: Running with Docker Compose

### Prerequisites
- Docker Engine 24.0+ / Docker Desktop
- Docker Compose v2.20+

### Step 1: Configure Local Environment
Copy the override example to provide local API keys without committing secrets:
```bash
cp docker-compose.override.yml.example docker-compose.override.yml
```
Edit `docker-compose.override.yml` to insert your development AI keys (e.g. `GROQ_API_KEY`).

### Step 2: Build and Launch Containers
```bash
docker compose up --build -d
```

### Step 3: Verify Status
```bash
docker compose ps
```
Both `resumeiq-backend` and `resumeiq-frontend` will report `healthy`.

### Step 4: Access the Application
- Web Application: `http://localhost:3000`
- Backend API Direct: `http://localhost:8000`
- Backend Liveness Probe: `http://localhost:8000/health`
- Backend Readiness Probe: `http://localhost:8000/health/ready`

### Step 5: Stop Containers Gracefully
```bash
docker compose down
```

---

## 4. Environment Variables

| Variable | Target | Description | Default |
|:---|:---|:---|:---|
| `ENVIRONMENT` | Backend | Runtime environment (`production`, `development`, `test`) | `production` |
| `BACKEND_PORT` | Backend | Internal listening port | `8000` |
| `LOG_LEVEL` | Backend | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `FIREBASE_PROJECT_ID` | Backend | Google Cloud / Firebase project ID | `resumeiq-3cfe6` |
| `CORS_ORIGINS` | Backend | Allowed CORS client origins | `http://localhost:3000` |
| `AI_PROVIDER_CHAIN` | Backend | Ordered failover chain (`groq,gemini,nvidia`) | `groq,gemini,nvidia` |
| `GROQ_API_KEY` | Backend | Groq Cloud API Key | *(Secret)* |
| `GEMINI_API_KEY` | Backend | Google Gemini API Key | *(Secret)* |
| `NVIDIA_API_KEY` | Backend | NVIDIA NIM API Key | *(Secret)* |
| `CLOUDINARY_CLOUD_NAME` | Backend | Cloudinary cloud name (optional backup storage) | *(Optional)* |
| `CLOUDINARY_API_KEY` | Backend | Cloudinary API key | *(Optional)* |
| `CLOUDINARY_API_SECRET` | Backend | Cloudinary API secret | *(Optional)* |
| `BACKEND_API_URL` | Frontend | Server-to-server BFF URL to reach FastAPI container | `http://backend:8000` |
| `NEXT_PUBLIC_BACKEND_API_URL` | Frontend | Browser fallback URL for client calls | `http://localhost:8000` |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Frontend | Firebase Web SDK Client API Key | *(Public identifier)* |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID`| Frontend | Firebase Web SDK Project ID | `resumeiq-3cfe6` |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`| Frontend | Firebase Web SDK Auth Domain | `resumeiq-3cfe6.firebaseapp.com` |

---

## 5. Health & Readiness Semantics

### Liveness Probe (`GET /health`)
- Used by Docker daemon / Kubernetes `livenessProbe` to verify process responsiveness.
- Responds in $<1\text{ms}$ with HTTP 200 without touching external databases or AI APIs.

### Readiness Probe (`GET /health/ready`)
- Used by load balancers / Kubernetes `readinessProbe` to route production traffic.
- Validates:
  1. Configuration completeness (`config`).
  2. Auth JWKS token verification client state (`auth_jwks`).
  3. HTTP outbound connection pool state (`http_pool`).
- Returns HTTP 200 (`"status": "ready"`) when operational; HTTP 503 (`"status": "not_ready"`) if degraded.
- Performs zero database mutations or expensive AI model calls.

---

## 6. Container Security Controls

- **Unprivileged Execution**: Both containers execute under dedicated non-root users (`UID 10001`).
- **No-New-Privileges**: `security_opt: [no-new-privileges:true]` prevents privilege escalation.
- **Capabilities Dropped**: `cap_drop: [ALL]` strips all Linux root capabilities.
- **Read-Only Root Filesystem**: `read_only: true` is enforced with a temporary memory-backed `/tmp` (`tmpfs`) volume.
- **Secret Isolation**: `.dockerignore` files prevent `.env` files, credentials, and `.git` trees from entering image layers. Secrets are strictly injected via runtime environment variables.

---

## 7. Graceful Shutdown

Upon receiving `SIGTERM` from Docker:
1. Uvicorn stops accepting incoming connections.
2. In-flight requests are allowed to complete within the grace period.
3. Lifespan context manager cleanly closes the persistent HTTP connection pool and AI provider client sessions.
4. Process exits cleanly with code 0.

---

## 8. Deployment Target Neutrality

ResumeIQ images comply strictly with OCI container standards. The containers can be deployed to:
- Google Cloud Run (Fully managed serverless container runtime)
- AWS ECS / Fargate or Azure Container Apps
- Kubernetes clusters (using standard Deployment and Service manifests)
- Self-hosted Docker / Docker Swarm hosts
