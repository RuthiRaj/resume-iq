# ResumeIQ Backend (FastAPI & AI Engine)

Dedicated Python backend service providing high-performance ATS resume scanning, Gemini AI orchestration, and Firebase token verification for ResumeIQ.

## 🚀 Quickstart

### 1. Create Virtual Environment
```bash
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Configure your GEMINI_API_KEY in .env
```

### 4. Run Development Server
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Health Check
```bash
curl http://localhost:8000/api/v1/health
```
