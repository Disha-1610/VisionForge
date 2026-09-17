# 🔍 VisionForge-AI

> **AI-Powered Visual Inspection & Fraud Detection System**

VisionForge-AI is an intelligent inspection platform that uses multi-agent AI pipelines to detect counterfeit parts, manufacturing defects, and fraudulent modifications in product images. It compares uploaded inspection images against golden reference images through a 14-stage pipeline — from image quality validation to explainable fraud reports.

---

## ✨ Key Features

- **14-Stage Inspection Pipeline** — Image quality check → Authenticity verification → Reference matching → ROI-based agent inspection → Multi-agent debate → Final verdict
- **9 Specialized Evidence Agents** — OCR, Label, Component, Structural, Material, Connector, Manufacturing, Usage, VLM (Vision Language Model)
- **Multi-Agent Debate** — Conflicting evidence is resolved through structured AI debate
- **Causal Reasoning** — Root-cause analysis with full cause-and-effect chains
- **Explainable Reports** — PDF reports with heatmaps, evidence overlays, and audit trails
- **Human Review Workflow** — Escalation queue for uncertain cases
- **Fraud Knowledge Graph** — Connected evidence relationships for pattern detection
- **Analytics Dashboard** — Fraud trends, vendor risk, detector accuracy tracking
- **Image Authenticity** — ELA, EXIF validation, copy-move detection, screenshot detection

---

## 🏗️ Architecture

```
Frontend (React + Vite)
        │
        ▼  REST API
Backend (FastAPI + LangGraph)
        │
        ├── Pipeline: 14 inspection stages
        ├── Shared Services: Working Memory, Evidence Store, Tool Registry, Knowledge Graph
        ├── Business Services: Human Review, Reporting, Analytics
        │
        ▼
Data Layer (PostgreSQL + FAISS + File Storage)
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|:---|:---|
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic |
| **AI / ML & Reasoning** | LangGraph, Google Gemini (`gemini-3.5-flash`, `gemini-embedding-2`), Groq (`gpt-oss-20b`, `qwen3.8-27b`), OpenCLIP, FAISS, PaddleOCR |
| **Computer Vision** | OpenCV, scikit-image, Pillow |
| **Frontend** | React 18, Vite, Tailwind CSS, shadcn/ui, Recharts |
| **Database & Caching** | PostgreSQL (async via asyncpg) / SQLite (local dev), Upstash Redis |
| **Reports** | ReportLab (PDF generation) |
| **Deployment** | Vercel (Frontend), Render (Backend), Docker & Docker Compose |

---

## 📁 Project Structure

```
VisionForge/
├── backend/
│   ├── app/
│   │   ├── core/           # Config, security, database, middleware, logging
│   │   ├── models/         # SQLAlchemy database models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── routers/        # FastAPI route handlers
│   │   ├── pipeline/       # 14-stage inspection pipeline
│   │   │   ├── stages/     # Pipeline stage implementations
│   │   │   └── agents/     # 9 specialized evidence agents
│   │   ├── shared/         # Working Memory, Evidence Store, Tool Registry, Knowledge Graph
│   │   ├── services/       # Business logic services
│   │   └── utils/          # Image processing, CV, file utilities
│   ├── tests/              # Test suites
│   └── migrations/         # Alembic database migrations
├── frontend/
│   └── src/
│       ├── pages/          # React page components
│       ├── components/     # Reusable UI components
│       ├── hooks/          # Custom React hooks
│       ├── context/        # Auth & Theme context
│       ├── services/       # API service functions
│       └── utils/          # Formatters, validators, constants
├── data/                   # Golden images, uploads, reports, FAISS index
└── docs/                   # Architecture, API reference, deployment guides
```

---

## 🚀 Quick Start (Team Setup Guide)

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & npm
- Free API Keys:
  - [Google Gemini API Key](https://aistudio.google.com/) (Required for primary VLM agent)
  - [Groq API Key](https://console.groq.com/) (Required for AI Judge & VLM round-robin)
- *(Note: SQLite is configured by default for zero-setup local development — PostgreSQL is optional)*

---

### Option A: 1-Click Master Launcher (Windows)

1. Double-click `run_visionforge.bat` in the root folder.
2. The launcher will automatically check prerequisites, start the backend on port `8000`, launch the frontend on port `5173`, and open your browser!

---

### Option B: Step-by-Step Manual Setup (Windows / macOS / Linux)

#### 1. Clone the Repository
```bash
git clone https://github.com/Disha-1610/VisionForge.git
cd VisionForge
```

#### 2. Backend Setup
```bash
cd backend

# Create & activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies (FastAPI, PyTorch, FAISS, LangGraph, etc.)
pip install -r requirements.txt

# Create your .env config from template
# On Windows (cmd):
copy .env.example .env
# On Linux/macOS:
cp .env.example .env

# Edit backend/.env and paste your GEMINI_API_KEY and GROQ_API_KEY
# (All other settings work out-of-the-box with local SQLite)

# Start backend server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Backend API will be running at [http://localhost:8000](http://localhost:8000) with interactive Swagger Docs at [http://localhost:8000/docs](http://localhost:8000/docs).

#### 3. Frontend Setup
In a new terminal window:
```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite React development server
npm run dev
```
Frontend Workstation will be live at [http://localhost:5173](http://localhost:5173).

---

### 🔑 Default Demo Accounts

The local database automatically auto-initializes and seeds these accounts on first launch:

| Role | Email | Password |
|:---|:---|:---|
| **System Admin** | `admin@visionforge.ai` | `adminpassword123` |
| **Line Operator** | `operator@visionforge.ai` | `operatorpassword123` |

### 📦 Pre-Indexed Hardware Components
On startup, 3 baseline golden reference components and their vector embeddings are pre-loaded:
1. **Industrial ATX Motherboard V1** (`PCB-MCU-V2`)
2. **Smart Lithium Battery Pack 48V** (`BAT-STD-V1`)
3. **ECC DDR4 Server Module 16GB** (`RAM-DDR4-V1`)

---

## 📖 Documentation

- [Architecture Guide](docs/architecture.md)
- [API Reference](docs/api_reference.md)
- [Deployment Guide](docs/deployment.md)
- [Contributing Guide](docs/contributing.md)

---

## 👥 Team

| Member | Role |
|:---|:---|
| **Disha** | Backend + Frontend Development |
| **Anil** | Backend + Frontend Development |

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
