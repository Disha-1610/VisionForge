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
| **AI / ML (NVIDIA NIM)** | LangGraph, NVIDIA NIM (`nemotron-3-super-120b`, `nemotron-3-nano-omni-30b`), OpenCLIP, FAISS, PaddleOCR |
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

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Node.js 18+ (for frontend)
- Ollama (for LLM inference)

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/Disha-1610/VisionForge.git
cd VisionForge

# 2. Create virtual environment & install dependencies
make setup

# 3. Activate the virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Configure environment variables
# Edit .env with your database credentials and API keys

# 5. Run database migrations
make migrate

# 6. Start the development server
make dev
```

The API will be available at `http://localhost:8000` with Swagger docs at `http://localhost:8000/docs`.

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