# 🚀 Deployment & Infrastructure Operations Guide

> **Production Deployment, Edge Acceleration, and Zero-Config Developer Setup**  
> **Status:** Authoritative (Reflects Actual Implemented Codebase)  
> **Backend Engine:** FastAPI ASGI on Uvicorn (Port 8000)  
> **Frontend Engine:** React 18 / Vite on Node (Port 5173)  
> **Database:** SQLite 3 (Default Local) / PostgreSQL 16+ (Production High-Concurrency)  
> **Mobile Tunnel:** Cloudflare Quick Tunnel (`cloudflared`)

---

## 📖 Table of Contents

- [1. Infrastructure Architecture & Deployment Topology](#1-infrastructure-architecture--deployment-topology)
- [2. System Prerequisites & Hardware Specifications](#2-system-prerequisites--hardware-specifications)
- [3. Environment Variables Configuration](#3-environment-variables-configuration)
  - [3.1 Backend `.env` Specification](#31-backend-env-specification)
  - [3.2 Frontend `.env` Configuration](#32-frontend-env-configuration)
- [4. Quick-Start Orchestration (Windows Batch Runners)](#4-quick-start-orchestration-windows-batch-runners)
  - [4.1 Master Launcher (`run_visionforge.bat`)](#41-master-launcher-run_visionforgebat)
  - [4.2 Standalone Backend Launcher (`start_backend.bat`)](#42-standalone-backend-launcher-start_backendbat)
  - [4.3 Standalone Frontend Launcher (`start_frontend.bat`)](#43-standalone-frontend-launcher-start_frontendbat)
- [5. Step-by-Step Manual Installation (Windows / macOS / Linux)](#5-step-by-step-manual-installation-windows--macos--linux)
- [6. Mobile Camera Pairing via Cloudflare Quick Tunnel](#6-mobile-camera-pairing-via-cloudflare-quick-tunnel)
- [7. Production Containerization (Docker & Compose Architecture)](#7-production-containerization-docker--compose-architecture)
- [8. Cloud Platform Deployment (Render, Railway, Vercel)](#8-cloud-platform-deployment-render-railway-vercel)
- [9. Health Checks & Operational Diagnostics](#9-health-checks--operational-diagnostics)
- [10. Troubleshooting Runbook & Common Failure Modes](#10-troubleshooting-runbook--common-failure-modes)

---

## 1. Infrastructure Architecture & Deployment Topology

VisionForge AI is engineered for **hybrid deployment**: it runs on factory-floor edge gateways, high-throughput desktop inspection docks, and cloud environments:

```mermaid
flowchart TD
    subgraph ClientTier["Client & Intake Tier"]
        Desktop["🖥️ Factory Desktop Workstation<br/>(Chrome / Edge - localhost:5173)"]
        Mobile["📱 Line Operator Smartphone<br/>(Safari / Chrome Camera Intake)"]
    end

    subgraph IngressTier["Ingress & Tunneling Tier"]
        CF["☁️ Cloudflare Quick Tunnel<br/>(cloudflared → localhost:5173)"]
    end

    subgraph AppTier["Application Server Tier"]
        Vite["⚡ Vite Dev / Nginx Reverse Proxy<br/>(:5173 / :80)"]
        FastAPI["🚀 FastAPI ASGI Multi-Worker<br/>(Uvicorn :8000)"]
    end

    subgraph InferenceTier["AI / ML Execution Tier"]
        YOLO["👁️ Ultralytics YOLO11n<br/>(PyTorch CUDA / CPU)"]
        FAISS["🔍 FAISS Vector Index<br/>(Cosine Similarity)"]
        OpenCV["🔬 OpenCV 4.9 Engine<br/>(Laplacian / ELA / SSIM)"]
        VLM["🤖 Cloud APIs (Async HTTPS)<br/>(Gemini 3.5 & Groq LPU)"]
    end

    subgraph StorageTier["Persistence & Data Tier"]
        DB[(🗄️ Relational DB<br/>SQLite / PostgreSQL 16)]
        Uploads["📁 File System / Persistent Volume<br/>(data/inspection_uploads/)"]
        Reports["📄 Audit PDF Store<br/>(data/reports/)"]
    end

    Desktop --> Vite
    Mobile --> CF --> Vite
    Vite -->|/api/v1/* Proxy| FastAPI
    FastAPI --> YOLO & FAISS & OpenCV & VLM
    FastAPI --> DB & Uploads & Reports
```

---

## 2. System Prerequisites & Hardware Specifications

### Minimum System Requirements (Developer PC / Edge Gateway)
- **CPU:** Quad-Core x86_64 / ARM64 (Intel Core i5 8th Gen+, AMD Ryzen 5, Apple Silicon M-Series).
- **RAM:** 8 GB minimum (16 GB recommended for concurrent YOLO11n + CLIP embedding).
- **Disk Space:** 5 GB free SSD storage for PyTorch models, YOLO weights, and dataset cache.
- **GPU Acceleration (Optional):** NVIDIA GPU with CUDA 12.0+ (enables sub-15ms YOLO inference).

### Software Requirements
| Tool / Framework | Minimum Version | Recommended Version | Purpose |
|:---|:---|:---|:---|
| **Python** | `3.11.0` | `3.12` or `3.13` | Backend API, LangGraph, PyTorch, OpenCV. |
| **Node.js** | `v18.0.0` | `v20.x LTS` | Frontend build engine, Vite, React 18. |
| **npm** | `9.0.0` | `10.x+` | Frontend package manager. |
| **Git** | `2.40.0` | `latest` | Repository and submodule tracking. |
| **cloudflared** | `latest` | Auto-downloaded | Mobile camera pairing tunnel. |

---

## 3. Environment Variables Configuration

### 3.1 Backend `.env` Specification
Create `backend/.env` from the provided `backend/.env.example` template:

```bash
cd backend
cp .env.example .env     # On Linux / macOS
copy .env.example .env   # On Windows
```

| Environment Variable | Default Value | Description |
|:---|:---|:---|
| `APP_NAME` | `VisionForge-AI` | Application identifier in headers and logs. |
| `APP_VERSION` | `0.1.0` | SemVer release version. |
| `ENVIRONMENT` | `development` | Environment mode (`development`, `production`). |
| `DEBUG` | `True` | Enables verbose SQL logging and stack traces. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./visionforge.db` | Database connection string. Use `postgresql+asyncpg://...` for production. |
| `JWT_SECRET_KEY` | `change-me-in-production` | Secret cryptographic salt for signing JWT tokens. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifespan. |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifespan. |
| `GEMINI_API_KEY` | `""` | Google AI Studio API key (for Gemini 2.5 Flash & Embeddings). |
| `GROQ_API_KEY` | `""` | Groq Cloud API key (for Qwen 3.8 VLM & LPU AI Judge). |
| `LLM_TIMEOUT_SECONDS` | `10.0` | Socket timeout for VLM and LLM inference calls before fast-failover. |
| `MIN_BLUR_VARIANCE` | `100.0` | Laplacian variance threshold for Stage 1. |
| `MIN_BRIGHTNESS` | `40.0` | Minimum mean pixel brightness threshold. |
| `MAX_BRIGHTNESS` | `220.0` | Maximum mean pixel brightness threshold. |
| `SIMILARITY_THRESHOLD` | `0.75` | Minimum FAISS cosine similarity for blueprint matching. |

---

## 4. Quick-Start Orchestration (Windows Batch Runners)

For Windows factory docks and hackathon evaluation, VisionForge includes one-click automated batch scripts:

### 4.1 Master Launcher (`run_visionforge.bat`)
Launches the entire system in a single step:
1. Verifies Python and Node.js installation.
2. Checks backend virtual environment (`backend/venv`); creates it and installs dependencies if missing.
3. Automatically seeds the database with demo accounts and golden blueprints.
4. Starts the Uvicorn backend server on port 8000.
5. Starts the Vite frontend workstation on port 5173.
6. Automatically launches Google Chrome or default browser pointing to `http://localhost:5173`.

```cmd
# Double-click in Windows Explorer or run from CMD:
run_visionforge.bat
```

### 4.2 Standalone Backend Launcher (`start_backend.bat`)
Activates the Python virtual environment and starts FastAPI:
```cmd
start_backend.bat
```

### 4.3 Standalone Frontend Launcher (`start_frontend.bat`)
Installs any newly added npm packages and starts the Vite React dev server:
```cmd
start_frontend.bat
```

---

## 5. Step-by-Step Manual Installation (Windows / macOS / Linux)

### 1. Clone the Repository
```bash
git clone https://github.com/Disha-1610/VisionForge.git
cd VisionForge
```

### 2. Configure Backend
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS / Linux:
source venv/bin/activate

# Install Python requirements
pip install -r requirements.txt

# Create .env file and paste your API keys
cp .env.example .env

# Start Backend Server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- **Backend API:** `http://localhost:8000`
- **Swagger Documentation:** `http://localhost:8000/docs`

### 3. Configure Frontend
Open a new terminal window:
```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite React server
npm run dev
```
- **Workstation HUD:** `http://localhost:5173`

---

## 6. Mobile Camera Pairing via Cloudflare Quick Tunnel

To allow mobile phones to stream live camera imagery to the workstation without requiring complicated router port forwarding:

1. Click **"Mobile Camera"** on the desktop HUD (`/inspections/new`).
2. The frontend triggers `GET /api/v1/system/tunnel-url`.
3. If not already active, the backend launches an ephemeral Cloudflare Quick Tunnel (`cloudflared tunnel --url http://localhost:5173`).
4. A public HTTPS URL (e.g. `https://rapid-sensor-alpha.trycloudflare.com`) is generated and encoded into a QR code.
5. The operator scans the QR code with their phone, opening the mobile intake viewfinder. The captured image uploads directly to the desktop queue.

---

## 7. Production Containerization (Docker & Compose Architecture)

For production deployment across enterprise factory servers, VisionForge provides a complete multi-container Docker Compose configuration:

### `Dockerfile.backend`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system OpenCV dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### `docker-compose.yml`
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: visionforge-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgrespassword
      POSTGRES_DB: visionforge
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: visionforge-backend
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgrespassword@postgres:5432/visionforge
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      GROQ_API_KEY: ${GROQ_API_KEY}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    volumes:
      - ./backend/data:/app/data

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: visionforge-frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  pgdata:
```

Launch the production stack:
```bash
docker-compose up -d --build
```

---

## 8. Cloud Platform Deployment (Render, Railway, Vercel)

### Deploying Backend to Render / Railway
1. **Root Directory:** Set to `backend`.
2. **Build Command:** `pip install -r requirements.txt`.
3. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. **Environment Variables:** Add `GEMINI_API_KEY`, `GROQ_API_KEY`, `JWT_SECRET_KEY`.

### Deploying Frontend to Vercel / Netlify
1. **Root Directory:** Set to `frontend`.
2. **Build Command:** `npm run build`.
3. **Output Directory:** `dist`.
4. **Rewrite Rule (`vercel.json`):** Route `/api/v1/:path*` to your production backend URL.

---

## 9. Health Checks & Operational Diagnostics

The system exposes a comprehensive JSON health check at `/api/v1/system/health`:

```bash
curl http://localhost:8000/api/v1/system/health
```

### Sample Health Payload
```json
{
  "status": "healthy",
  "app_name": "VisionForge-AI",
  "version": "0.1.0",
  "database": "connected",
  "faiss_index": "loaded (3 vectors, dim=3072)",
  "yolo_model": "loaded (component_detector.pt, 8 classes)",
  "vlm_providers": {
    "gemini": "configured",
    "groq": "configured"
  }
}
```

---

## 10. Troubleshooting Runbook & Common Failure Modes

### 1. Port 8000 or 5173 Already in Use
- **Symptom:** `OSError: [Errno 10048] address already in use`
- **Resolution:**
  ```cmd
  # Find and kill process on port 8000 (Windows)
  netstat -ano | findstr :8000
  taskkill /PID <PID> /F
  ```

### 2. Missing OpenCV System Libraries (Linux / Docker)
- **Symptom:** `ImportError: libGL.so.1: cannot open shared object file`
- **Resolution:** Install system graphics libraries:
  ```bash
  sudo apt-get install -y libgl1-mesa-glx libglib2.0-0
  ```

### 3. Missing or Unset Cloud API Keys
- **Symptom:** `LLMClientException: GEMINI_API_KEY is empty`
- **Resolution:** Verify `backend/.env` contains valid keys from Google AI Studio and Groq Cloud.

### 4. Cross-Machine Broken Image Paths in Database
- **Symptom:** Images render as broken placeholders on a teammate's machine.
- **Resolution:** VisionForge's `_resolve_image_path` in `image_utils.py` automatically normalizes file paths relative to `BASE_DIR`. Simply restart the backend server to re-index.

---

*For security safeguards and secret handling, see [`docs/SECURITY.md`](SECURITY.md).*  
*For end-to-end automated testing procedures, see [`docs/TESTING.md`](TESTING.md).*
