# 🚀 VisionForge AI — Deployment & Infrastructure Guide

> **Status:** Authoritative (Reflects Actual Implemented Codebase)  
> **Backend Engine:** FastAPI (ASGI on Uvicorn)  
> **Frontend Engine:** React 18 / Vite 5 (Tailwind CSS HUD)  
> **Database:** SQLite 3 (Zero-Config Development) / PostgreSQL 16+ (High-Concurrency Production)  
> **Mobile Intake Tunnel:** Cloudflare Quick Tunnel (`cloudflared`)

---

## 📑 Table of Contents

- [1. Infrastructure & Deployment Topology](#1-infrastructure--deployment-topology)
- [2. System Prerequisites & Environment Requirements](#2-system-prerequisites--environment-requirements)
- [3. Environment Variables Configuration](#3-environment-variables-configuration)
  - [3.1 Backend `.env` Specification](#31-backend-env-specification)
  - [3.2 Frontend `.env` Specification](#32-frontend-env-specification)
- [4. Quick-Start Orchestration (Windows Batch Runners)](#4-quick-start-orchestration-windows-batch-runners)
  - [4.1 Master Launcher (`run_visionforge.bat`)](#41-master-launcher-run_visionforgebat)
  - [4.2 Standalone Backend Launcher (`start_backend.bat`)](#42-standalone-backend-launcher-start_backendbat)
  - [4.3 Standalone Frontend Launcher (`start_frontend.bat`)](#43-standalone-frontend-launcher-start_frontendbat)
- [5. Mobile Camera Pairing via Cloudflare Quick Tunnel](#5-mobile-camera-pairing-via-cloudflare-quick-tunnel)
- [6. Database Initialization & Factory Seeding](#6-database-initialization--factory-seeding)
- [7. Production Containerization (Docker Architecture)](#7-production-containerization-docker-architecture)
- [8. Health Checks & Diagnostic Endpoints](#8-health-checks--diagnostic-endpoints)
- [9. Operational Troubleshooting & Runbook](#9-operational-troubleshooting--runbook)

---

## 1. Infrastructure & Deployment Topology

VisionForge AI is engineered for hybrid deployment: high-throughput desktop workstations, factory-floor edge PCs, and cleanroom mobile tablets:

```mermaid
flowchart TD
    subgraph ClientLayer["Intake & Client Layer"]
        Desktop["🖥️ Factory Desktop Workstation<br/>(Chrome / Edge - localhost:5173)"]
        Mobile["📱 Line Operator Smartphone<br/>(Safari / Chrome Camera Intake)"]
    end

    subgraph TunnelLayer["Ingress & Tunneling"]
        CF["☁️ Cloudflare Quick Tunnel<br/>(cloudflared → localhost:5173)"]
    end

    subgraph AppLayer["Application Layer (localhost:8000)"]
        Vite["⚡ Vite Dev / Nginx Reverse Proxy<br/>(:5173 / :80)"]
        FastAPI["🚀 FastAPI ASGI Server<br/>(Uvicorn Multi-Worker :8000)"]
    end

    subgraph MLServices["AI / ML Acceleration"]
        YOLO["👁️ Ultralytics YOLO11n<br/>(PyTorch / TensorRT)"]
        FAISS["🔍 FAISS Vector Engine<br/>(L2 Cosine Distance)"]
        OpenCV["🔬 OpenCV 4.9<br/>(Laplacian, ELA, SSIM)"]
        VLM["🤖 Cloud LLM / VLM APIs<br/>(Gemini 3.5 & Groq LPU)"]
    end

    subgraph StorageLayer["Data & Persistence Layer"]
        DB[(🗄️ Relational DB<br/>SQLite / PostgreSQL 16)]
        Uploads["📁 File System / Volume<br/>(data/inspection_uploads/)"]
        Reports["📄 Audit PDF Store<br/>(data/reports/)"]
    end

    Desktop --> Vite
    Mobile --> CF --> Vite
    Vite -->|/api/v1/* Proxy| FastAPI
    FastAPI --> YOLO & FAISS & OpenCV & VLM
    FastAPI --> DB & Uploads & Reports
```

---

## 2. System Prerequisites & Environment Requirements

### Minimum Hardware Specification (Edge Gateway / Dev PC)
- **CPU:** Quad-Core x86_64 / ARM64 (Intel Core i5 8th Gen+, AMD Ryzen 5, Apple Silicon M-Series).
- **RAM:** 8 GB minimum (16 GB recommended for multi-stream YOLO11n + CLIP embedding).
- **Disk Space:** 5 GB free SSD storage for dataset cache, model weights, and SQLite database.
- **GPU Acceleration (Optional):** NVIDIA GPU with CUDA 12.0+ (supports TensorRT / PyTorch CUDA for sub-15ms inference).

### Software Dependencies
| Component | Minimum Version | Verified Version | Purpose |
|:---|:---|:---|:---|
| **Python** | `3.11.0` | `3.13.0` | Backend API, LangGraph, PyTorch, OpenCV. |
| **Node.js** | `v18.0.0` | `v20.x` / `v22.x` | Frontend toolchain, Vite build engine, Cloudflare tunnel bridge. |
| **npm** | `9.0.0+` | `10.x+` | Package manager for React dependencies. |
| **Git** | `2.40+` | `2.45+` | Version control & repository tracking. |
| **cloudflared** | `latest` | Auto-downloaded | Mobile camera HTTPS loopback tunneling. |

---

## 3. Environment Variables Configuration

### 3.1 Backend `.env` Specification

Copy the template from `backend/.env.example` to `backend/.env`:

```bash
cp backend/.env.example backend/.env
```

```ini
# ══════════════════════════════════════════════════════════════════════════════
# VisionForge-AI — Backend Configuration
# ══════════════════════════════════════════════════════════════════════════════

# ── Application Metadata ──────────────────────────────────────────────────────
APP_NAME=VisionForge-AI
APP_VERSION=0.1.0
DEBUG=true

# ── Relational Database ───────────────────────────────────────────────────────
# SQLite Zero-Config Local Mode:
DATABASE_URL=sqlite+aiosqlite:///data/visionforge.db

# PostgreSQL Production Mode:
# DATABASE_URL=postgresql+asyncpg://postgres:your_secure_password@localhost:5432/visionforge

DATABASE_ECHO=false
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800

# ── Authentication & Cryptography ─────────────────────────────────────────────
JWT_SECRET_KEY=your_generated_random_64_character_hex_secret_here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ── Cross-Origin Resource Sharing (CORS) ──────────────────────────────────────
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# ── Google Gemini Cloud AI (Primary VLM Agent, Secondary AI Judge) ───────────
# Obtain free API key from https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
GEMINI_VLM_MODEL=gemini-3.5-flash
GEMINI_JUDGE_MODEL=gemini-3.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-2

# ── Groq Cloud LPU AI (Primary AI Judge, Secondary VLM Agent) ─────────────────
# Obtain free API key from https://console.groq.com/
GROQ_API_KEY=your_groq_api_key_here
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_VLM_MODEL=qwen/qwen3.8-27b
GROQ_JUDGE_MODEL=openai/gpt-oss-20b

# ── Visual Embedding & Similarity Baselines ───────────────────────────────────
CLIP_MODEL=openai/clip-vit-base-patch32
SIMILARITY_THRESHOLD=0.75
```

### 3.2 Frontend `.env` Specification

Copy the template from `frontend/.env.example` to `frontend/.env`:

```bash
cp frontend/.env.example frontend/.env
```

```ini
# VisionForge Frontend Configuration
# Base API prefix routed through Vite proxy:
VITE_API_BASE_URL=/api/v1

# Automatically injected by `npm run tunnel` when Cloudflare tunnel is active:
# VITE_PUBLIC_URL=https://visionforge-mobile-tunnel.trycloudflare.com
```

---

## 4. Quick-Start Orchestration (Windows Batch Runners)

VisionForge includes automated batch execution scripts for single-click operator launch on Windows workstations:

### 4.1 Master Launcher (`run_visionforge.bat`)

The master runner orchestrates all preflight checks, port clearance, mobile tunnel setup, and process spawning:

```bat
# Execute from Repository Root
.\run_visionforge.bat
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. [Preflight Check] Verifies python.exe and npm.cmd are in system PATH.    │
│ 2. [Port Clearance] Kills stale zombie processes holding ports 5173 & 8000. │
│ 3. [Tunnel Prompt] Queries operator to enable Cloudflare HTTPS tunnel.      │
│ 4. [Backend Spawn] Launches Uvicorn ASGI server (:8000) in new window.      │
│ 5. [Frontend Spawn] Launches Vite React Dev server (:5173) in new window.   │
│ 6. [Browser Launch] Opens default web browser directly to localhost:5173.   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Standalone Backend Launcher (`start_backend.bat`)

Launches the Python FastAPI backend server with hot-reloading:

```bat
.\start_backend.bat
```
- **Bound Address:** `http://0.0.0.0:8000`
- **Swagger Documentation:** `http://localhost:8000/docs`
- **ReDoc Documentation:** `http://localhost:8000/redoc`

### 4.3 Standalone Frontend Launcher (`start_frontend.bat`)

Launches the Vite React development server:

```bat
.\start_frontend.bat
```
- **Bound Address:** `http://localhost:5173`
- **Vite Proxy:** Automatically forwards `/api` requests to `http://localhost:8000/api`.

---

## 5. Mobile Camera Pairing via Cloudflare Quick Tunnel

Factory line operators frequently need to capture high-angle macro images using smartphone cameras. Because modern mobile browsers require secure contexts (`https://`) to access `navigator.mediaDevices.getUserMedia`, VisionForge provides an automated zero-config tunnel bridge (`frontend/scripts/tunnel.mjs`):

```mermaid
sequenceDiagram
    participant Op as 👷 Line Operator
    participant Script as 📜 tunnel.mjs
    participant CF as ☁️ Cloudflare CDN
    participant UI as 🖥️ Workstation UI

    Op->>Script: npm run tunnel (or via run_visionforge.bat)
    Script->>Script: Verify or download cloudflared-windows-amd64.exe (~55MB)
    Script->>CF: Spawn quick tunnel: cloudflared --url http://localhost:5173
    CF-->>Script: Assigned https://<random-hash>.trycloudflare.com
    Script->>Script: Write URL to frontend/.env & frontend/.tunnel.url
    UI->>UI: DesktopGuardModal reads VITE_PUBLIC_URL
    UI->>Op: Display dynamic pairing QR Code on workstation screen
    Op->>Op: Operator scans QR code on smartphone camera
    Op->>UI: Instant PWA camera interface opens with live crosshair HUD
```

### Manual Tunnel Execution
```bash
cd frontend
npm run tunnel
```

---

## 6. Database Initialization & Factory Seeding

To create all database tables, foreign key constraints, and seed default demonstration hardware blueprints:

### Zero-Config SQLite Initialization
```bash
cd backend
python scripts/seed_demo_data.py
```

### Seed Data Population Summary:
- **Administrative Account:** `admin@visionforge.ai` / `adminpassword123`
- **Line Operator Account:** `operator@visionforge.ai` / `operatorpassword123`
- **Seeded Hardware Blueprints:**
  - `Industrial ATX Motherboard V1` (Part ID: `PCB-MCU-V2`)
  - `48V Telecom Lithium Battery Pack` (Part ID: `BAT-48V-LFP`)
  - `32GB DDR4 Server ECC Memory` (Part ID: `RAM-ECC-32G`)
- **Seeded Supply-Chain Vendors:**
  - `Foxconn Precision Assembly` (`VND-FOX-01`)
  - `Delta Electronics Taiwan` (`VND-DLT-02`)
  - `Shenzhen Micro-Tech Ltd` (`VND-SZX-03`)

---

## 7. Production Containerization (Docker Architecture)

For enterprise manufacturing deployment, VisionForge can be packaged into standardized multi-container Docker pods:

### Docker Compose Reference Topology (`docker-compose.yml`)

```yaml
version: '3.8'

services:
  # ── PostgreSQL Database ─────────────────────────────────────────────────────
  db:
    image: postgres:16-alpine
    container_name: visionforge-db
    restart: always
    environment:
      POSTGRES_USER: visionforge
      POSTGRES_PASSWORD: ${DB_PASSWORD:-secure_db_password}
      POSTGRES_DB: visionforge
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U visionforge"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ── FastAPI Backend ─────────────────────────────────────────────────────────
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: visionforge-backend
    restart: always
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://visionforge:${DB_PASSWORD:-secure_db_password}@db:5432/visionforge
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      GROQ_API_KEY: ${GROQ_API_KEY}
    volumes:
      - backend_uploads:/app/data/inspection_uploads
      - backend_reports:/app/data/reports
    ports:
      - "8000:8000"

  # ── React Frontend (Nginx Production Serve) ─────────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: visionforge-frontend
    restart: always
    depends_on:
      - backend
    ports:
      - "80:80"

volumes:
  postgres_data:
  backend_uploads:
  backend_reports:
```

### Backend Production `Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV and ReportLab
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## 8. Health Checks & Diagnostic Endpoints

VisionForge exposes diagnostic endpoints for load balancers and container orchestrators:

| Endpoint | Method | Expected Output | Purpose |
|:---|:---:|:---|:---|
| `/api/v1/health` | `GET` | `{"status": "healthy", "version": "0.1.0"}` | Uptime monitoring & Kubernetes liveness probe. |
| `/api/v1/system/network` | `GET` | `{"local_ip": "...", "port": 5173, "is_tunneled": true}` | Mobile intake pairing configuration discovery. |
| `/docs` | `GET` | HTML Swagger UI | Interactive OpenAPI schema explorer. |

---

## 9. Operational Troubleshooting & Runbook

### Issue 1: Port `8000` or `5173` Already in Use
- **Symptom:** `Uvicorn failed to bind to address ('0.0.0.0', 8000): address already in use`.
- **Remedy:** The master launcher `run_visionforge.bat` automatically frees these ports. To clear manually in PowerShell:
  ```powershell
  Get-NetTCPConnection -LocalPort 5173,8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  ```

### Issue 2: Cloudflare Tunnel Download or Launch Failure
- **Symptom:** `Download failed: HTTP 403 / Tunnel did not report URL in time`.
- **Remedy:** Download `cloudflared-windows-amd64.exe` manually from Cloudflare's GitHub release page, place it in `%USERPROFILE%\.visionforge\bin\cloudflared.exe`, or set the environment variable:
  ```powershell
  $env:VISIONFORGE_CLOUDFLARED = "C:\path\to\cloudflared.exe"
  ```

### Issue 3: Missing YOLO Model Weights File
- **Symptom:** `FileNotFoundError: backend/app/models/component_detector.pt`.
- **Remedy:** Verify that `backend/app/models/component_detector.pt` exists. If missing, the structural agent automatically initializes a baseline YOLO11n weights checkpoint or runs OpenCV SSIM structural fallback.

### Issue 4: CORS Cross-Origin Blocking on LAN Devices
- **Symptom:** `Access to XMLHttpRequest at 'http://192.168.1.X:8000' from origin 'http://192.168.1.X:5173' has been blocked by CORS policy`.
- **Remedy:** In `backend/.env`, add your local network IP or subnet to `CORS_ORIGINS`:
  ```ini
  CORS_ORIGINS=["http://localhost:5173","http://192.168.1.*","*"]
  ```

---

*For test verification procedures, consult [`docs/TESTING.md`](TESTING.md).*
