# 📋 VisionForge AI — Extended MVP+ Implementation Plan

> **Team:** Anil + Disha  
> **Start:** 17 August 2026  
> **Target End:** 30 September 2026 (6.5 weeks)  
> **Strategy:** Extended MVP — Full 8-stage pipeline with 4 evidence agents, YOLO fine-tuning, analytics dashboard, and a 7-page frontend (Landing, Login, Dashboard, New Inspection, Inspection Detail, Reports, Analytics). Every tool/model remains free-tier or fully local. Focus is pipeline accuracy, explainable reports, and a polished demo-ready application.  
> **Rule:** Backend first → Frontend → Deploy  
> **Days:** Monday–Saturday (6 days/week)

---

## 🏁 Implementation Status — VisionForge.md ↔ Code (verified Sep 2026)

`VisionForge.md` is the **design source of truth**; this plan maps its features to schedule. Status below reflects the actual codebase (verified via tests/imports):

| VisionForge.md feature | Plan slot | Status |
|:---|:---|:---:|
| Async SQLAlchemy + pooling + session ctx | W1 D2 | ✅ Done |
| Models: user, vendor, product, inspection, evidence (incl. YOLO count fields) | W1 D1 | ✅ Done |
| JWT access/refresh + bcrypt + token-type check | W1 D2 | ✅ Done |
| Schemas (auth, inspection, product, vendor, report) | W1 D3 | ✅ Done |
| Routers: auth, products, vendors, inspections (+ background task, case numbers) | W1 D4 | ✅ Done |
| Evidence Store (append-only, immutable, thread-safe) | W1 D4 | ✅ Done |
| Working Memory (per-stage StageResult tracking — SSE-ready) | W1 D5 | ✅ Done |
| LLM Client (Groq/Gemini primary→fallback routing) | W1 D5 | ✅ Done |
| Embedding Service (Gemini 1-shot → OpenCLIP fallback + FAISS) | W1/W2 | ✅ Done |
| Alembic migration 001 (5 tables, 2-role enum) | W1 D6 | ✅ Done |
| Test suite (16 passing: auth, RBAC, evidence store, memory, schemas) | W1 D6 | ✅ Done |
| file_utils (safe upload), workflow stub | W2 D1 | ✅ Done |
| **RBAC — 2 roles (OPERATOR/ADMIN), `require_roles()` factory** | W1 (added) | ✅ Done |
| Pipeline stages 1–3 (quality_check, authenticity, reference_match) | W2 | 🔲 Planned |
| ROI templates + image_utils | W2 D2 | 🔲 Planned |
| LangGraph workflow (replace stub) | W2 D3/W4 D3 | 🔲 Planned |
| Pipeline stages 4–5 + 4 agents | W3 | 🔲 Planned |
| YOLO dataset merge (10 classes) + fine-tune | W3 D4 | 🔲 Planned |
| Stages 6–8, reporting, analytics + by-operator RBAC | W4 | 🔲 Planned |
| SSE endpoint `GET /inspections/{id}/events` + status fallback | W4 D4 | 🔲 Planned (contract documented) |
| Frontend (7 pages + design system + components) | W5–W6 | 🔲 Planned |
| CI/CD + Render/Vercel deploy | W7 | 🔲 Planned |

> **Rule:** when a VisionForge.md feature lands in code, update this table in the same commit.

---



```
VisionForge-MVP/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # CI pipeline — pytest, linting & frontend build check
│       └── cd.yml                    # CD pipeline — auto-deploy backend (Render) & frontend (Vercel)
├── .gitignore
├── README.md
├── docker-compose.yml
├── docker-compose.prod.yml
├── Makefile
│
├── backend/
│   ├── Dockerfile
│   ├── Dockerfile.prod
│   ├── render.yaml                   # Render.com backend service deployment config
│   ├── .env.example
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic.ini
│   │
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 001_initial_tables.py
│   │       ├── 002_add_vendor_master.py
│   │       └── 003_add_analytics_indexes.py
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── product.py            # GoldenReference
│   │   │   ├── vendor.py             # Master Vendor & Site list
│   │   │   ├── inspection.py         # includes verdict, review, vendor_id, location
│   │   │   └── evidence.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── inspection.py
│   │   │   ├── product.py
│   │   │   ├── vendor.py
│   │   │   └── report.py
│   │   │
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── products.py
│   │   │   ├── vendors.py
│   │   │   ├── inspections.py
│   │   │   ├── reports.py
│   │   │   └── analytics.py
│   │   │
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── workflow.py           # LangGraph — wires all 8 stages
│   │   │   ├── state.py
│   │   │   │
│   │   │   ├── stages/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── quality_check.py
│   │   │   │   ├── authenticity.py
│   │   │   │   ├── reference_match.py
│   │   │   │   ├── roi_scheduler.py
│   │   │   │   ├── evidence_execution.py
│   │   │   │   ├── evidence_fusion.py
│   │   │   │   ├── judge.py
│   │   │   │   └── policy_engine.py
│   │   │   │
│   │   │   └── agents/
│   │   │       ├── __init__.py
│   │   │       ├── base_agent.py
│   │   │       ├── ocr_agent.py
│   │   │       ├── label_agent.py
│   │   │       ├── structural_agent.py
│   │   │       └── vlm_agent.py
│   │   │
│   │   ├── shared/
│   │   │   ├── __init__.py
│   │   │   ├── memory.py
│   │   │   ├── evidence_store.py
│   │   │   └── llm_client.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── embedding_service.py
│   │   │   ├── reporting_service.py
│   │   │   └── analytics_service.py
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── image_utils.py
│   │       ├── cv_utils.py
│   │       └── file_utils.py
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_pipeline/
│       │   ├── __init__.py
│       │   ├── test_quality_check.py
│       │   ├── test_authenticity.py
│       │   ├── test_reference_match.py
│       │   ├── test_roi_scheduler.py
│       │   ├── test_evidence_execution.py
│       │   ├── test_evidence_fusion.py
│       │   ├── test_judge.py
│       │   └── test_policy_engine.py
│       └── test_agents/
│           ├── __init__.py
│           ├── test_ocr_agent.py
│           ├── test_label_agent.py
│           ├── test_structural_agent.py
│           └── test_vlm_agent.py
│
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   ├── index.html
│   ├── vercel.json                   # Vercel deployment & SPA routing rewrites
│   ├── .env.example
│   │
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       │
│       ├── pages/
│       │   ├── LandingPage.jsx       # public — hero, how-it-works, CTA
│       │   ├── LoginPage.jsx
│       │   ├── DashboardPage.jsx
│       │   ├── NewInspectionPage.jsx
│       │   ├── InspectionDetailPage.jsx
│       │   ├── ReportsPage.jsx       # filterable archive of all reports
│       │   └── AnalyticsPage.jsx
│       │
│       ├── components/
│       │   ├── landing/
│       │   │   ├── HeroSection.jsx
│       │   │   ├── HowItWorks.jsx
│       │   │   ├── FeatureGrid.jsx
│       │   │   └── SocialProof.jsx
│       │   ├── common/
│       │   │   ├── LoadingSpinner.jsx
│       │   │   ├── ErrorBoundary.jsx
│       │   │   ├── Pagination.jsx
│       │   │   ├── StatCard.jsx
│       │   │   ├── StatusChip.jsx
│       │   │   ├── EmptyState.jsx
│       │   │   ├── SkeletonLoader.jsx
│       │   │   ├── Toast.jsx
│       │   │   └── ConfirmDialog.jsx
│       │   ├── layout/
│       │   │   ├── Navbar.jsx
│       │   │   ├── Sidebar.jsx
│       │   │   ├── Footer.jsx
│       │   │   └── Breadcrumbs.jsx
│       │   ├── inspection/
│       │   │   ├── ImageUploader.jsx
│       │   │   ├── ImageCompare.jsx
│       │   │   ├── PipelineProgress.jsx  # SSE-driven live 8-stage progress (EventSource on /inspections/{id}/events, polling fallback)
│       │   │   ├── ROIOverlay.jsx
│       │   │   ├── EvidenceCard.jsx
│       │   │   └── VerdictBanner.jsx
│       │   ├── products/
│       │   │   └── GoldenReferenceUploader.jsx  # admin upload → products CRUD + FAISS index
│       │   ├── reports/
│       │   │   ├── ReportsTable.jsx
│       │   │   └── ReportFilters.jsx
│       │   └── analytics/
│       │       ├── FraudTrendChart.jsx
│       │       ├── VendorLocationTable.jsx
│       │       ├── VendorRiskTable.jsx
│       │       └── SummaryCards.jsx
│       │
│       ├── context/
│       │   ├── AuthContext.jsx
│       │   └── ThemeContext.jsx
│       │
│       ├── services/
│       │   ├── api.js
│       │   ├── authService.js
│       │   ├── inspectionService.js
│       │   ├── productService.js
│       │   ├── reportsService.js
│       │   └── analyticsService.js
│       │
│       ├── hooks/
│       │   ├── useAuth.js
│       │   └── useInspection.js
│       │
│       └── routes/
│           └── AppRoutes.jsx
│
├── data/
│   ├── golden_images/
│   │   └── sample_uploads/
│   ├── inspection_uploads/
│   ├── roi_templates/
│   ├── faiss_index/
│   ├── yolo_weights/
│   │   └── component_detector.pt
│   └── test_data/
│       ├── golden_set/
│       └── fraud_set/
│
└── docs/
    ├── VisionForge-AI-Pipeline-Architecture.md
    ├── api_reference.md
    ├── deployment_guide.md
    ├── test_results.md
    └── demo_script.md
```

---

## 🗓️ Week 1 (Aug 17–22) — Foundation (Backend Core)

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Aug 17)** | Repo create, `.gitignore`, `README.md`, folder structure, `requirements.txt`, `.env` + `.env.example` (all env vars: DB, JWT, Gemini, Groq, CLIP, file paths) | DB models: `user.py`, `product.py`, `vendor.py` (Master Vendor & Site list with `id`, `name`, `site_name`, `code`), `inspection.py` (includes vendor_id, location, verdict fields), `evidence.py` |
| **Day 2 (Aug 18)** | `core/security.py` — JWT token creation (access + refresh tokens), password hashing (bcrypt), token validation | `core/database.py` — async SQLAlchemy engine + Alembic init, connection pooling setup, session management |
| **Day 3 (Aug 19)** | `schemas/auth.py` (Login, Register, Token, User response) + `schemas/inspection.py` (InspectionCreate, InspectionUpdate, InspectionResponse with evidence) | `schemas/product.py` (GoldenReferenceCreate, ProductResponse) + `schemas/vendor.py` (VendorCreate, VendorResponse, VendorDropdown) + `schemas/report.py` (ReportResponse) |
| **Day 4 (Aug 20)** | `routers/auth.py` (login/register/me/refresh endpoints) + `routers/products.py` (CRUD for golden references) + `routers/vendors.py` (vendor master list CRUD & dropdown endpoints) | `routers/inspections.py` (skeleton with upload endpoint) + `shared/evidence_store.py` (in-memory store with append-only pattern) |
| **Day 5 (Aug 21)** | `services/embedding_service.py` — CLIP + FAISS setup (local, free) — test with sample images | `shared/llm_client.py` — Gemini + Groq wrapper (with retry & failover logic), `shared/memory.py` (working memory per inspection) |
| **Day 6 (Aug 22)** | **Integration Day** — Auth + golden-reference upload flow end-to-end test. Write tests for auth endpoints. | **Integration Day** — Vendor CRUD + evidence store tests. Finalize DB migrations. |

---

## 🗓️ Week 2 (Aug 24–29) — Pipeline Stages 1–3 + Shared Services

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Aug 24)** | `pipeline/stages/quality_check.py` — blur detection (Laplacian variance), lighting (brightness histogram), format validation, resolution check, duplicate detection | `pipeline/stages/authenticity.py` — ELA (Error Level Analysis), EXIF validation (using exifread), basic tamper detection (noise consistency) |
| **Day 2 (Aug 25)** | `pipeline/stages/reference_match.py` — Dual embedding generation (Gemini 1-shot -> OpenCLIP fallback) for uploaded image, FAISS/vector search, golden image selection with similarity threshold | Create sample ROI templates in `data/roi_templates/` (3-5 JSON files with bounding boxes for capacitors, connectors, chips, labels) + `utils/image_utils.py` (crop, resize, conversion functions) |
| **Day 3 (Aug 26)** | `pipeline/state.py` — define inspection state dataclass (WorkingMemory + EvidenceStore integration) | `pipeline/workflow.py` — LangGraph foundation: define nodes, edges, compile graph with checkpointing |
| **Day 4 (Aug 27)** | `services/embedding_service.py` — dual embedding generation (Gemini `gemini-embedding-2` 1-shot primary + OpenCLIP `ViT-B-32` fallback), FAISS index build/update | `shared/llm_client.py` — implement vision capabilities for VLM Agent (Gemini 3.5 Flash + Groq Qwen fallback) |
| **Day 5 (Aug 28)** | Unit tests for Stages 1–3 | Unit tests for image utils and embedding service |
| **Day 6 (Aug 29)** | **Integration Day** — Test Stages 1–3 end-to-end with sample images, verify golden reference matching accuracy | **Integration Day** — Review and finalize ROI template format, document for Stage 4 |

---

## 🗓️ Week 3 (Aug 31–Sep 5) — Pipeline Stages 4–5 + Agents + YOLO Fine-Tune

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Aug 31)** | `pipeline/stages/roi_scheduler.py` — read ROI template, map ROI types to agents, produce execution plan, handle priority ordering | Stage 5: `pipeline/stages/evidence_execution.py` — dispatch framework for parallel agent execution, cropping ROI pairs from golden & inspection images |
| **Day 2 (Sep 1)** | `agents/base_agent.py` — Abstract base class with run() method, confidence standardization | `agents/ocr_agent.py` — Primary: PaddleOCR, Secondary: EasyOCR integration for text extraction and comparison |
| **Day 3 (Sep 2)** | `agents/label_agent.py` — OpenCV template matching for labels, seals, logos (using golden template) | `agents/structural_agent.py` — SSIM calculation (OpenCV) foundation |
| **Day 4 (Sep 3)** | **YOLO Dataset Preparation** — Merge public PCB-component datasets from Roboflow Universe (`https://universe.roboflow.com/search?q=pcb+components`, `?q=electronic+component+detection`; DeepPCB reference: `https://github.com/tangsanli5201/DeepPCB`) + self-shot battery/RAM photos; unify to the 10-class single shared model (Motherboard: capacitor, resistor, ic_chip, connector, screw • Battery: terminal, seal, battery_cell • RAM: ram_ic_chip, gold_pin_connector) on Roboflow free tier, export YOLO format | **YOLO Fine-Tune** — Set up Google Colab notebook, fine-tune YOLO11n on merged dataset (~300 images, 10 classes, T4 GPU, ~1-2 hours), export weights |
| **Day 5 (Sep 4)** | `agents/structural_agent.py` — Integrate YOLO component detection, compare golden vs inspection component counts | `agents/vlm_agent.py` — Primary: Gemini 3.5 Flash, fallback: Groq Qwen 3.6 27B, prompt engineering for visual anomaly detection |
| **Day 6 (Sep 5)** | **Integration Day** — Test Stages 4–5 end-to-end: ROI scheduling → evidence execution → agents → verify YOLO detections on sample crops | **Integration Day** — Test all 4 agents independently with ROI crops, log results, fix issues |

---

## 🗓️ Week 4 (Sep 7–12) — Pipeline Stages 6–8 + Core Testing

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Sep 7)** | `pipeline/stages/evidence_fusion.py` — Multi-angle merge, weighing SSIM vs YOLO signal, duplicate removal, confidence aggregation | `pipeline/stages/judge.py` — Prompt design for verdict + root cause reasoning with evidence weighting |
| **Day 2 (Sep 8)** | `pipeline/stages/policy_engine.py` — Hardcoded rules: fraud score thresholds → action mapping (Accept/Retake/Quarantine/Verification) | `services/reporting_service.py` — Report generation with ReportLab (PDF), evidence summary, ROI overlays |
| **Day 3 (Sep 9)** | `pipeline/workflow.py` — Wire all 8 stages via LangGraph, add error handling and state persistence | `routers/reports.py` — Report fetch endpoints (PDF/JSON), report schema integration |
| **Day 4 (Sep 10)** | `routers/analytics.py` + `services/analytics_service.py` — Summary queries, vendor/location breakdown, monthly trend, vendor-risk breakdown. **RBAC on analytics: operator sees only own activity (`created_by = current_user.id`), admin sees everything; plus admin-only `GET /analytics/by-operator` (per-operator inspection & fraud breakdown)** | `routers/inspections.py` — Complete upload → trigger pipeline → approve/override endpoints, background task for pipeline execution. **Real-time pipeline progress via SSE: `GET /inspections/{id}/events` — FastAPI StreamingResponse (`text/event-stream`) emitting an event on every stage start/complete/fail (stage, stage_name, status, n/8, detail) sourced from Working Memory / LangGraph state; final `verdict` event then closes the stream. Also keep lightweight `GET /inspections/{id}/status` as the polling fallback endpoint.** |
| **Day 5 (Sep 11)** | **Curate Test Dataset** — 30-40 golden-vs-fraud image pairs (include challenging cases: lighting variations, angle changes, subtle tampering) | **Accuracy Testing** — Run full pipeline on test set, log results, calculate precision/recall, document failure cases |
| **Day 6 (Sep 12)** | **Integration Day** — Fix bugs from accuracy run, write unit tests for all pipeline stages | **Integration Day** — Write unit tests for all agents, finalize test results documentation |

---

## 🗓️ Week 5 (Sep 14–19) — Frontend Core Pages + Landing + Integration

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Sep 14)** | Frontend setup: Vite + React, package.json, routing (React Router — public routes `/`, `/login`; protected routes for the rest, plus a `*` → NotFoundPage), Tailwind CSS configuration **+ SaaS Design System tokens: status color palette (Accept/emerald, Quarantine/red, Review/amber, Processing/blue), dark mode via `ThemeContext`, typography scale (Inter), spacing & radius tokens, sidebar layout shell** | `services/api.js` — Axios setup with interceptors for auth, error handling; `context/AuthContext.jsx`; global `Toast` provider (success/error/info toasts on every mutation) |
| **Day 2 (Sep 15)** | `pages/LandingPage.jsx` + `components/landing/HeroSection.jsx` + `HowItWorks.jsx` (4-step pipeline teaser) + `FeatureGrid.jsx` (agent/product feature cards) + `SocialProof.jsx` (metrics strip — "X parts inspected, Y fraud cases caught"), CTA to Login | `pages/LoginPage.jsx` — Login/Register forms with validation (split-card SaaS layout: form left, product value props right); `components/common/` (LoadingSpinner, ErrorBoundary, Pagination, EmptyState, SkeletonLoader, StatusChip) |
| **Day 3 (Sep 16)** | `pages/DashboardPage.jsx` — `StatCard` summary row (today's inspections, pending review, fraud detected this week, fraud rate), recent inspections feed with `StatusChip` badges, `GoldenReferenceUploader` panel (admin: upload golden images per product — Motherboard/Battery/RAM → `POST /products`), "+ New Inspection" CTA | `pages/NewInspectionPage.jsx` — Drag-drop upload with multi-image thumbnails, vendor dropdown (`GET /vendors`) + inline add, location field, product-type selector (Motherboard/Battery/RAM), triggers the 8-stage pipeline → redirects to Inspection Detail |
| **Day 4 (Sep 17)** | `pages/InspectionDetailPage.jsx` — Verdict banner, evidence cards, approve/override actions | `components/inspection/ImageUploader.jsx` + `components/inspection/ImageCompare.jsx` — drag-drop zone + side-by-side comparison with zoom; `components/inspection/PipelineProgress.jsx` — **SSE-driven live 8-stage stepper: native `EventSource` on `/inspections/{id}/events`, animated stage transitions on each `stage` event, verdict banner renders on the final `verdict` event; automatic fallback to `GET /inspections/{id}/status` polling (2-3s) if the SSE connection errors, plus auto-reconnect on transient drops** |
| **Day 5 (Sep 18)** | `components/inspection/ROIOverlay.jsx` — Render YOLO bounding boxes on images, crop visualization | `components/inspection/EvidenceCard.jsx` + `components/inspection/VerdictBanner.jsx` — fraud probability, confidence, category |
| **Day 6 (Sep 19)** | **Integration Day** — Connect Landing → Login → Dashboard → New Inspection → Inspection Detail flow end-to-end | **Integration Day** — UI polish, responsiveness fixes, loading states, error messages |

---

## 🗓️ Week 6 (Sep 21–26) — Reports + Analytics + Polish

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Sep 21)** | `pages/ReportsPage.jsx` — filterable archive of all reports, links to Inspection Detail | `components/reports/ReportFilters.jsx` (date range, vendor, location, verdict, category) + `components/reports/ReportsTable.jsx` |
| **Day 2 (Sep 22)** | `pages/AnalyticsPage.jsx` — Summary cards layout, integration with analytics endpoints | `components/analytics/SummaryCards.jsx` — Fraud rate, total inspections, fraud cases, top offender displays |
| **Day 3 (Sep 23)** | `components/analytics/FraudTrendChart.jsx` — Monthly trend chart (Recharts/Chart.js) with interactive tooltips | `components/analytics/VendorLocationTable.jsx` + `components/analytics/VendorRiskTable.jsx` (vendor × fraud-category breakdown, matches `/analytics/vendor-risk`) |
| **Day 4 (Sep 24)** | **Advanced Features** — Export report as PDF/CSV from Reports page and Inspection Detail | **Testing** — Frontend unit tests (Jest + React Testing Library), integration tests for critical paths |
| **Day 5 (Sep 25)** | **Performance Optimization** — Code splitting, lazy loading, memoization for components | **Backend Refinements** — Add comprehensive logging (request IDs, pipeline steps, agent execution), improve LLM client retry logic |
| **Day 6 (Sep 26)** | **Integration Day** — Full end-to-end test: landing → login → upload → pipeline → report → analytics with realistic data | **Integration Day** — UI/UX final polish, dark mode toggle, mobile responsiveness, accessibility improvements |

---

## 🗓️ Week 7 (Sep 28–30) — CI/CD + Cloud Deployment (Render & Vercel) + Demo Prep

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Sep 28)** | **CI/CD & Backend Deployment Setup** — Create `.github/workflows/ci.yml` (pytest, linting, frontend build) + `.github/workflows/cd.yml` (auto-deploy triggers), configure `backend/render.yaml` & Dockerfile with production env vars | **Frontend Cloud Prep** — Configure `frontend/vercel.json` (SPA routing rewrites & security headers), verify production build bundle, create `frontend/.env.example` with `VITE_API_URL` |
| **Day 2 (Sep 29)** | **Backend Deployment (Render.com)** — Deploy backend web service on Render connected to PostgreSQL (Supabase/Neon), run Alembic migrations on startup, verify health check (`/health`) & live Swagger API docs | **Frontend Deployment (Vercel)** — Deploy React frontend on Vercel, connect to live Render API URL, configure CORS, verify live authenticated user flows (Landing → Login → Dashboard) |
| **Day 3 (Sep 30)** | **Live Pipeline & Demo Verification** — Test complete live flow on production (Vercel + Render): Image upload → 8-stage pipeline → AI Judge verdict → PDF download → Analytics dashboard, polish README.md with live links | **MVP DONE 🎉** — End-to-end production smoke test, verify mobile responsiveness on live Vercel URL, prepare demo script walkthrough with sample inspection images |

---

## 📊 Extended Timeline Summary

| Phase | Duration | Dates | Key Deliverables |
|:---|:---|:---|:---|
| **Week 1: Foundation** | 6 days | Aug 17–22 | Core setup, models, schemas, auth, base shared services |
| **Week 2: Pipeline Stages 1–3** | 6 days | Aug 24–29 | Quality check, authenticity, reference match with CLIP+FAISS, shared services |
| **Week 3: Pipeline Stages 4–5 + Agents** | 6 days | Aug 31–Sep 5 | ROI scheduler, evidence execution, 4 agents complete, YOLO fine-tuned |
| **Week 4: Pipeline Stages 6–8 + Testing** | 6 days | Sep 7–12 | Evidence fusion, judge, policy engine, reporting, accuracy testing |
| **Week 5: Frontend Core + Landing** | 6 days | Sep 14–19 | Landing, Login, Dashboard, New Inspection, Inspection Detail, core components |
| **Week 6: Reports + Analytics + Polish** | 6 days | Sep 21–26 | Reports archive, Analytics dashboard, PDF/CSV export, optimization, testing |
| **Week 7: Deploy + Demo** | 3 days | Sep 28–30 | Dockerize, deploy to Vercel + Render, demo prep, final polish |
| **Total** | **6.5 weeks** | Aug 17 – Sep 30 | **Production-ready MVP with full pipeline, analytics, and polished UI** |

---

## 👤 Work Split Summary (Extended)

| Area | Anil | Disha |
|:---|:---|:---|
| **Core Setup** | security, main.py, config, Docker setup | database, exceptions, migrations, docker-compose |
| **Models & Schemas** | user, inspection + auth/inspection schemas | product, vendor, evidence + product/vendor/report schemas |
| **Routers & Shared** | auth, products, reports, analytics | vendors, inspections, evidence_store, llm_client, memory |
| **Pipeline Stages** | quality_check, reference_match, roi_scheduler, evidence_fusion, policy_engine | authenticity, evidence_execution, judge |
| **Agents** | base_agent, label, vlm | ocr, structural (+ YOLO fine-tune and integration) |
| **Services** | embedding_service (CLIP+FAISS) | reporting_service (PDF), analytics_service (SQL) |
| **Frontend Core** | Landing, Dashboard, InspectionDetail, ROIOverlay, deploy (Vercel) | Login, NewInspection, ImageUploader, ImageCompare, EvidenceCard, VerdictBanner |
| **Frontend Reports & Analytics** | ReportsPage, AnalyticsPage, FraudTrendChart, PDF/CSV export | ReportFilters, ReportsTable, SummaryCards, VendorLocationTable, VendorRiskTable |
| **Testing** | Backend unit tests, integration tests, pytest suite | Frontend unit tests, accuracy test set curation, UI/UX testing |
| **Deployment & CI/CD** | Backend deploy (Render), GitHub Actions CI/CD workflows (`.github/workflows/`), API docs | Frontend deploy (Vercel), `vercel.json` SPA config, production smoke test |
| **Documentation** | API reference, architecture doc | README, test results, demo script |

> **Note:** Every Saturday (Day 6) both work together on code review + integration testing.

---

## 🧠 Free-Tier Cheat Sheet (Updated)

| Need | Use | Not |
|:---|:---|:---|
| Text reasoning (Judge) | Primary: Groq — `openai/gpt-oss-20b` (verified), Secondary: Google Gemini — `gemini-3.5-flash` | Paid OpenAI/Anthropic API |
| Vision reasoning (VLM Agent) | Primary: Google Gemini — `gemini-3.5-flash`, Secondary: Groq — `qwen/qwen3.6-27b` | Paid GPT-4V / Claude vision |
| Image embeddings | Open-source CLIP (`openai/clip-vit-base-patch32`) local / `gemini-embedding-2` | Paid embedding APIs |
| Object detection (Structural Agent) | YOLO11n, self fine-tuned, AGPL-3.0 (free — repo stays open-source) | Ultralytics Enterprise license |
| Dataset annotation | Roboflow free tier | Paid annotation tools |
| Model training | Google Colab free GPU (T4) | Paid Colab Pro / cloud GPU |
| OCR | Primary: PaddleOCR, Secondary: EasyOCR (local) | Paid OCR APIs |
| Hosting Backend | Render.com free tier / Railway.app free tier | Paid cloud hosting |
| Hosting Frontend | Vercel free tier | Paid hosting |
| Database | PostgreSQL (Supabase free tier / Neon free tier) | Paid DB hosting |

---

## 📈 Progress Tracker (Extended)

| Week | Day | Anil | Disha | Status |
|:-----|:----|:----:|:-----:|:------:|
| **W1** | D1 (Aug 17) | ✅ | ✅ | |
| | D2 (Aug 18) | ✅ | ✅ | |
| | D3 (Aug 19) | ✅ | ✅ | |
| | D4 (Aug 20) | ✅ | ✅ | |
| | D5 (Aug 21) | ✅ | ✅ | |
| | D6 (Aug 22) | ✅ | ✅ | **Completed ✅** |
| **W2** | D1 (Aug 24) | | |
| | D2 (Aug 25) | | |
| | D3 (Aug 26) | | |
| | D4 (Aug 27) | | |
| | D5 (Aug 28) | | |
| | D6 (Aug 29) | ✅ | ✅ |
| **W3** | D1 (Aug 31) | | |
| | D2 (Sep 1) | | |
| | D3 (Sep 2) | | |
| | D4 (Sep 3) | | |
| | D5 (Sep 4) | | |
| | D6 (Sep 5) | ✅ | ✅ |
| **W4** | D1 (Sep 7) | | |
| | D2 (Sep 8) | | |
| | D3 (Sep 9) | | |
| | D4 (Sep 10) | | |
| | D5 (Sep 11) | | |
| | D6 (Sep 12) | ✅ | ✅ |
| **W5** | D1 (Sep 14) | | |
| | D2 (Sep 15) | | |
| | D3 (Sep 16) | | |
| | D4 (Sep 17) | | |
| | D5 (Sep 18) | | |
| | D6 (Sep 19) | ✅ | ✅ |
| **W6** | D1 (Sep 21) | | |
| | D2 (Sep 22) | | |
| | D3 (Sep 23) | | |
| | D4 (Sep 24) | | |
| | D5 (Sep 25) | | |
| | D6 (Sep 26) | ✅ | ✅ |
| **W7** | D1 (Sep 28) | | |
| | D2 (Sep 29) | | |
| | D3 (Sep 30) | ✅ | ✅ |

---

## 🎯 Critical Success Factors

1. **Pipeline Accuracy** — Measured precision/recall on test set is the primary success metric
2. **YOLO Integration** — Component-level detection must be properly integrated and tested
3. **Free-Tier Adherence** — No accidental paid API usage, stay within rate limits
4. **End-to-End Flow** — Upload → Pipeline → Report → Analytics must work seamlessly
5. **Demo-Ready UI** — Polished, responsive, with clear visualizations and explanations

---

## 🔄 Risk Mitigation

| Risk | Mitigation |
|:---|:---|
| YOLO fine-tune fails on limited data | Use SSIM as fallback, expand with more public Roboflow Universe datasets or annotate more self-shot images for better accuracy |
| LLM rate limits exceeded | Implement exponential backoff, use fallback models aggressively, cache common prompts |
| Deployment issues | Early Docker setup, test on free tiers (Render, Vercel) with staging environment |
| Frontend-backend integration delays | Start frontend after Week 4, use mock data initially, integrated testing every Saturday |
| Pipeline performance too slow | Precompute embeddings, batch processing, optimize image sizes, use CPU for lightweight stages |

---

## 🚀 Next Steps After MVP (Roadmap)

- **Multi-Agent Debate** — Extend Judge with debate between specialized agents
- **Fraud Knowledge Graph** — Build relationship graph across components, labels, OCR findings
- **Continuous Learning** — Store fraud patterns and use for future detection
- **5 Additional Evidence Agents** — Component, Material, Connector, Manufacturing, Usage
- **Vendor Management Page** — dedicated CRUD UI, replacing the inline "add vendor" shortcut on New Inspection
- **Human Review Queue Page** — dedicated multi-reviewer queue, replacing the single Approve/Override action
- **Production Scaling** — Move to paid tiers, implement proper authentication, rate limiting, monitoring

---

This extended plan ensures:
- ✅ Complete 8-stage pipeline with all agents
- ✅ YOLO properly fine-tuned and integrated
- ✅ Full analytics dashboard (vendor/location/monthly breakdown)
- ✅ Polished, demo-ready frontend
- ✅ Deployment to free-tier hosting
- ✅ Accuracy metrics documented
- ✅ Buffer time for unexpected issues
