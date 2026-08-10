# 📋 VisionForge-AI — 10-Week Master Implementation Plan

> **Team:** Disha + Anil  
> **Start:** 7 August 2026  
> **Target End:** ~7 October 2026 (Accelerated from Oct 15)  
> **Strategy:** ⚡ **Sprint Mode (Aug 10–27):** Heavy workload before classes start → **Normal Mode (Aug 28–Oct 7):** Relaxed steady pace after classes start.  
> **Rule:** Backend first → Frontend → Cloud Deployment  
> **Days:** Monday–Saturday (6 days/week)

---

## 📁 Full Project Structure (Reference)

```
VisionForge/
├── .github/
│   └── workflows/
│       └── ci.yml
├── README.md
├── LICENSE
├── .gitignore
├── docker-compose.yml
├── Makefile
│
├── backend/
│   ├── Dockerfile
│   ├── render.yaml
│   ├── .env.example
│   ├── requirements.txt
│   ├── alembic.ini
│   │
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 001_initial_tables.py
│   │       ├── 002_add_evidence_store.py
│   │       └── 003_add_fraud_memory.py
│   │
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   ├── exceptions.py
│   │   │   ├── middleware.py
│   │   │   ├── redis_client.py
│   │   │   └── logging_config.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── product.py
│   │   │   ├── inspection.py
│   │   │   ├── evidence.py
│   │   │   ├── review.py
│   │   │   └── analytics.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── product.py
│   │   │   ├── inspection.py
│   │   │   ├── review.py
│   │   │   └── report.py
│   │   │
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── inspections.py
│   │   │   ├── products.py
│   │   │   ├── reviews.py
│   │   │   ├── reports.py
│   │   │   ├── analytics.py
│   │   │   └── admin.py
│   │   │
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── workflow.py
│   │   │   ├── state.py
│   │   │   │
│   │   │   ├── stages/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── quality_check.py
│   │   │   │   ├── authenticity.py
│   │   │   │   ├── reference_match.py
│   │   │   │   ├── roi_scheduler.py
│   │   │   │   ├── evidence_fusion.py
│   │   │   │   ├── debate.py
│   │   │   │   ├── causal_reasoning.py
│   │   │   │   ├── judge.py
│   │   │   │   └── policy_engine.py
│   │   │   │
│   │   │   └── agents/
│   │   │       ├── __init__.py
│   │   │       ├── base_agent.py
│   │   │       ├── ocr_agent.py
│   │   │       ├── label_agent.py
│   │   │       ├── component_agent.py
│   │   │       ├── structural_agent.py
│   │   │       ├── material_agent.py
│   │   │       ├── connector_agent.py
│   │   │       ├── manufacturing_agent.py
│   │   │       ├── usage_agent.py
│   │   │       └── vlm_agent.py
│   │   │
│   │   ├── shared/
│   │   │   ├── __init__.py
│   │   │   ├── memory.py
│   │   │   ├── evidence_store.py
│   │   │   ├── tool_registry.py
│   │   │   ├── knowledge_graph.py
│   │   │   └── llm_client.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── embedding_service.py
│   │   │   ├── reporting_service.py
│   │   │   ├── review_service.py
│   │   │   ├── analytics_service.py
│   │   │   ├── fraud_memory_service.py
│   │   │   └── notification_service.py
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── image_utils.py
│   │       ├── cv_utils.py
│   │       └── file_utils.py
│   │
│   └── tests/
│       ├── conftest.py
│       ├── test_pipeline/
│       ├── test_agents/
│       ├── test_routers/
│       └── test_services/
│
├── frontend/
│   ├── Dockerfile
│   ├── vercel.json
│   ├── .env.example
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   │
│   ├── public/
│   │   └── images/
│   │
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       │
│       ├── pages/
│       │   ├── LoginPage.jsx
│       │   ├── DashboardPage.jsx
│       │   ├── NewInspectionPage.jsx
│       │   ├── InspectionListPage.jsx
│       │   ├── InspectionDetailPage.jsx
│       │   ├── HumanReviewPage.jsx
│       │   ├── AnalyticsPage.jsx
│       │   ├── ProductCatalogPage.jsx
│       │   ├── ROIEditorPage.jsx
│       │   └── SettingsPage.jsx
│       │
│       ├── components/
│       │   ├── common/
│       │   ├── layout/
│       │   ├── inspection/
│       │   ├── review/
│       │   └── analytics/
│       │
│       ├── hooks/
│       ├── context/
│       ├── services/
│       ├── routes/
│       └── utils/
│
├── data/
│   ├── golden_images/
│   ├── inspection_uploads/
│   ├── heatmaps/
│   ├── reports/
│   ├── roi_templates/
│   └── faiss_index/
│
└── docs/
    ├── architecture.md
    ├── api_reference.md
    ├── deployment.md
    └── contributing.md
```

---

## 🗓️ PHASE 1: SPRINT MODE (Aug 10 – Aug 27)
> ⚡ **High Workload Velocity** (Finishing Core Setup, Models, Schemas, Routers & Pipeline Layer A before college classes start!)

---

### Week 1 (Aug 7–12) — Project Foundation & Database Models

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Aug 7)** | [x] Repo create, `.gitignore`, `README.md`, `LICENSE`, `.env.example`, `Makefile`, poora folder structure banao | [x] `requirements.txt` — sab dependencies list karo, `venv` setup karo |
| **Day 2 (Aug 8)** | [x] `backend/app/core/config.py` — pydantic-settings se environment variables load karo | [x] `backend/app/core/database.py` — SQLAlchemy 2.0 async engine + asyncpg PostgreSQL session setup karo |
| **Day 3 (Aug 9)** | [x] `backend/app/core/security.py` — JWT token creation, password hashing (bcrypt) | [x] `backend/app/core/exceptions.py` — custom error classes banao (NotFound, Unauthorized, ValidationError, etc.) |
| **Day 4 (Aug 10)** | [ ] `backend/app/core/middleware.py` — CORS, global error handler, request logging middleware + `backend/app/core/redis_client.py` — Upstash Redis connection setup (rate limiting + caching) | [ ] `backend/app/core/logging_config.py` — structured JSON logging setup karo |
| **Day 5 (Aug 11)** | [ ] `backend/app/main.py` — FastAPI app create karo, middleware attach karo, startup/shutdown events | [ ] `backend/alembic.ini` + `backend/migrations/env.py` — Alembic migration setup karo |
| **Day 6 (Aug 12)** | ⚡ **HEAVY:** `backend/app/models/user.py` + `inspection.py` + `review.py` (User, Inspection, InspectionImage, HumanReview, AuditLog tables) | ⚡ **HEAVY:** `backend/app/models/product.py` + `evidence.py` + `analytics.py` (GoldenReference, Evidence, DetectorResult, FraudPattern, VendorScore tables) |

---

### Week 2 (Aug 14–19) — Schemas, Initial Migration & API Routers

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Aug 14)** | ⚡ `backend/app/schemas/auth.py` + `inspection.py` + `review.py` (LoginRequest, RegisterRequest, InspectionCreate, ReviewSubmit, etc.) | ⚡ `backend/app/schemas/product.py` + `report.py` (ProductCreate, ProductResponse, ROITemplateSchema, ReportMeta) |
| **Day 2 (Aug 15)** | `backend/migrations/versions/001_initial_tables.py` generate + `alembic upgrade head` test karo + `backend/app/routers/auth.py` (POST /login, POST /register, GET /me) | `backend/app/shared/llm_client.py` — NVIDIA NIM wrapper banao (chat + vision dono via OpenAI SDK), connection test |
| **Day 3 (Aug 16)** | `backend/app/routers/products.py` — CRUD endpoints for golden references (upload, list, delete, cascade sync with FAISS) | `backend/app/shared/memory.py` — Working Memory class banao (per-inspection state store) |
| **Day 4 (Aug 17)** | `backend/app/routers/inspections.py` — POST /inspect (upload + trigger pipeline), GET /inspections (list), GET /inspections/{id} | `backend/app/shared/evidence_store.py` — Evidence Store banao (append-only, audit trail) |
| **Day 5 (Aug 18)** | `backend/app/routers/reviews.py` + `reports.py` — GET /reviews (queue), POST /reviews/{id} submit verdict, GET /reports/{id}/pdf download | `backend/app/shared/tool_registry.py` — Tool Registry banao (tool name → function mapping) |
| **Day 6 (Aug 19)** | `backend/app/routers/analytics.py` + `admin.py` — dashboard data + admin settings endpoints | `backend/app/shared/knowledge_graph.py` — Fraud Knowledge Graph banao (NetworkX based) |

---

### Week 3 (Aug 21–27) — Pipeline Layer A (Deterministic Stages) — *Final Sprint before Classes*

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Aug 21)** | `backend/app/pipeline/state.py` — Pipeline TypedDict state define karo | `backend/app/utils/image_utils.py` — crop, resize, normalize, blur check, brightness check |
| **Day 2 (Aug 22)** | `backend/app/pipeline/stages/quality_check.py` — Stage 1: blur, lighting, format, resolution, duplicate detection, smart resize, background crop | `backend/app/utils/cv_utils.py` — OpenCV wrappers (histogram, edge detection, homography, etc.) |
| **Day 3 (Aug 23)** | `backend/app/pipeline/stages/authenticity.py` — Stage 2: ELA, EXIF validation, screenshot detection, noise analysis | Authenticity cont. — copy-move detection, lighting consistency, authenticity score calculation |
| **Day 4 (Aug 24)** | `backend/app/services/embedding_service.py` — CLIP embedding generation + FAISS index build/search/delete | `backend/app/utils/file_utils.py` — file I/O, path helpers, temp file cleanup |
| **Day 5 (Aug 25)** | `backend/app/pipeline/stages/reference_match.py` — Stage 3: FAISS search, Part ID match, angle verification, ROI template loading, manufacturer params | `data/roi_templates/` — 2-3 sample ROI template JSON files banao (motherboard, label, chip) |
| **Day 6 (Aug 26)** | `backend/app/pipeline/stages/roi_scheduler.py` — Stage 4: ROI template read, ROI type → agent mapping, golden+target crop, parallel scheduling | Dono milke: Stage 1-4 individually test karo — image upload se ROI crop tak poora flow |
| **Day 7 (Aug 27)** | 🎓 **CLASSES START TODAY!** `backend/app/pipeline/agents/base_agent.py` — Abstract base class | `backend/app/pipeline/agents/ocr_agent.py` — EasyOCR text read agent |

---

## 🗓️ PHASE 2: NORMAL MODE (Aug 28 – Oct 7)
> ☕ **Steady Pace After Classes Start** (Agents, Reasoning, Frontend & Cloud Deployment)

---

### Week 4 (Aug 28–Sep 3) — Specialist Evidence Agents

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Aug 28)** | [ ] `backend/app/pipeline/agents/structural_agent.py` — SSIM score, JET heatmap generate, anomaly regions mark | [ ] `backend/app/pipeline/agents/label_agent.py` — Template matching, QC seals, logos, stickers check |
| **Day 2 (Aug 29)** | [ ] `backend/app/pipeline/agents/component_agent.py` — Contour detection, capacitors/ICs count, position compare, missing parts | [ ] `backend/app/pipeline/agents/material_agent.py` — Color histogram (HSV), surface texture, non-OEM material detect |
| **Day 3 (Aug 30)** | [ ] `backend/app/pipeline/agents/connector_agent.py` — Edge detection, pins check, connector shape match, damage detect | [ ] `backend/app/pipeline/agents/manufacturing_agent.py` — Solder quality, assembly marks, manufacturing defects |
| **Day 4 (Aug 31)** | [ ] `backend/app/pipeline/agents/usage_agent.py` — Wear patterns (scratches, discoloration, age signs) | [ ] `backend/app/pipeline/agents/vlm_agent.py` — NVIDIA NIM Vision Model (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`) visual inspection |
| **Day 5 (Sep 1)** | [ ] Agent testing — sample ROI crops pe run karke evidence output verify karo | [ ] Agent testing & prompt tuning |
| **Day 6 (Sep 2)** | [ ] Dono milke: All 9 agents unit test & edge case verification complete karo | [ ] Agent integration test |

---

### Week 5 (Sep 4–10) — Pipeline Layer B & C (AI + Business Stages)

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Sep 4)** | [ ] `backend/app/pipeline/stages/evidence_fusion.py` — Stage 6: multi-angle merge, duplicate removal, confidence aggregation | [ ] `backend/app/pipeline/stages/debate.py` — Stage 7: multi-agent debate, LLM prompts for argue/defend/challenge |
| **Day 2 (Sep 5)** | [ ] Debate cont. — rounds logic, consensus check, max rounds, accepted evidence output | [ ] Evidence Fusion cont. — cross-angle matching, IoU duplicate detection, angle contribution tracking |
| **Day 3 (Sep 7)** | [ ] `backend/app/pipeline/stages/causal_reasoning.py` — Stage 8: evidence chain, root cause vs secondary effects, LLM narrative | [ ] `backend/app/pipeline/stages/judge.py` — Stage 9: all evidence read, LLM verdict (Accept/Reject/Review), confidence + fraud probability |
| **Day 4 (Sep 8)** | [ ] `backend/app/pipeline/stages/policy_engine.py` — Stage 10: configurable rules, fraud score → action, escalation rules | [ ] `backend/app/services/fraud_memory_service.py` — Stage 12: permanent storage, index by part/vendor/site, similar case search |
| **Day 5 (Sep 9)** | [ ] `backend/app/services/review_service.py` — Stage 11: human review logic, approve/reject/override, audit log | [ ] `backend/app/services/reporting_service.py` — Stage 13: ReportLab PDF, evidence embed, causal chain, heatmaps |
| **Day 6 (Sep 10)** | [ ] `backend/app/services/analytics_service.py` — Stage 14: fraud trends, vendor scores, detector accuracy, tampering stats | [ ] Dono milke: Stage 6-14 test karo |

---

### Week 6 (Sep 11–17) — Pipeline Integration & Backend Testing

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Sep 11)** | [ ] `backend/app/pipeline/workflow.py` — LangGraph StateGraph, sab stages nodes mein connect, edges define | [ ] Workflow cont. — conditional edges (quality fail → stop, authenticity low → flag, policy → human review) |
| **Day 2 (Sep 12)** | [ ] `backend/app/routers/inspections.py` update — POST /inspect se pipeline trigger, results DB mein save | [ ] `backend/app/services/notification_service.py` — alerts (human review needed, quarantine triggered) |
| **Day 3 (Sep 14)** | [ ] `backend/app/routers/admin.py` update — threshold tuning, ROI template upload, policy rules CRUD | [ ] `backend/migrations/versions/002_add_evidence_store.py` + `003_add_fraud_memory.py` — additional migrations |
| **Day 4 (Sep 15)** | [ ] Full pipeline end-to-end test — image upload se PDF report tak poora flow | [ ] `backend/tests/conftest.py` — test fixtures + test DB setup |
| **Day 5 (Sep 16)** | [ ] `backend/tests/test_pipeline/` — test_quality_check.py, test_authenticity.py, test_reference_match.py, test_debate.py, test_judge.py, test_full_pipeline.py | [ ] `backend/tests/test_agents/` — test_ocr_agent.py, test_label_agent.py, test_component_agent.py, test_structural_agent.py, test_vlm_agent.py |
| **Day 6 (Sep 17)** | [ ] `backend/tests/test_routers/` — test_auth.py, test_inspections.py, test_products.py + `backend/tests/test_services/` — test_embedding.py, test_reporting.py | [ ] Dono milke: **Backend DONE** ✅ — poora pipeline demo run, sab APIs test, sab stages working |

---

### Week 7 (Sep 18–24) — Frontend Setup & Core Pages

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Sep 18)** | [ ] Vite + React setup — `package.json`, `vite.config.js`, `index.html`, `frontend/src/main.jsx`, `frontend/src/App.jsx`, folder structure, dependencies install | [ ] `frontend/src/index.css` — global styles, design system (colors, fonts, spacing, dark mode variables) |
| **Day 2 (Sep 19)** | [ ] `frontend/src/context/AuthContext.jsx` + `frontend/src/context/ThemeContext.jsx` + `frontend/src/services/api.js` — auth context, theme context, axios setup with interceptors | [ ] `frontend/src/components/common/Button.jsx`, `Modal.jsx`, `Card.jsx`, `Table.jsx`, `Badge.jsx`, `Loader.jsx`, `Toast.jsx` |
| **Day 3 (Sep 21)** | [ ] `frontend/src/pages/LoginPage.jsx` — login/register form with JWT | [ ] `frontend/src/components/layout/Sidebar.jsx`, `Header.jsx`, `PageWrapper.jsx`, `ProtectedRoute.jsx` |
| **Day 4 (Sep 22)** | [ ] `frontend/src/pages/DashboardPage.jsx` — main landing page, summary cards, recent inspections | [ ] `frontend/src/routes/AppRoutes.jsx` — sab routes define, role-based access (admin vs operator) |
| **Day 5 (Sep 23)** | [ ] `frontend/src/pages/NewInspectionPage.jsx` — image upload (drag-drop), metadata form, pipeline trigger | [ ] `frontend/src/components/inspection/ImageUploader.jsx` — drag-drop component with preview + validation |
| **Day 6 (Sep 24)** | [ ] `frontend/src/pages/InspectionListPage.jsx` — inspections table, filter by status, search, pagination | [ ] `frontend/src/services/authService.js` + `inspectionService.js` — API call functions |

---

### Week 8 (Sep 25–Oct 1) — Inspection Detail, Review & Admin Pages

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Sep 25)** | [ ] `frontend/src/pages/InspectionDetailPage.jsx` — case detail view, verdict banner, evidence cards, pipeline timeline | [ ] `frontend/src/components/inspection/ImageCompare.jsx` + `HeatmapOverlay.jsx` — side-by-side viewer + heatmap overlay |
| **Day 2 (Sep 26)** | [ ] `frontend/src/components/inspection/VerdictBanner.jsx` + `EvidenceCard.jsx` + `TimelineView.jsx` | [ ] `frontend/src/components/review/ROIOverlay.jsx` — bounding box display on images |
| **Day 3 (Sep 28)** | [ ] `frontend/src/pages/HumanReviewPage.jsx` — review workbench, approve/reject/override, comment | [ ] `frontend/src/components/review/ReviewPanel.jsx` + `CommentBox.jsx` |
| **Day 4 (Sep 29)** | [ ] `frontend/src/pages/ProductCatalogPage.jsx` — golden reference upload, list, delete, FAISS sync | [ ] `frontend/src/pages/ROIEditorPage.jsx` — canvas pe ROI bounding boxes draw karo |
| **Day 5 (Sep 30)** | [ ] `frontend/src/pages/SettingsPage.jsx` — threshold tuning, policy rules, system config | [ ] `frontend/src/services/productService.js` + `reviewService.js` + `reportService.js` — API call functions |
| **Day 6 (Oct 1)** | [ ] Dono milke: sab pages backend se connect karo, API integration test karo | [ ] Dono milke: Integration test |

---

### Week 9 (Oct 2–7) — Analytics, Cloud Deployment & Final Polish

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Oct 2)** | [ ] `frontend/src/pages/AnalyticsPage.jsx` — charts layout, filters, date range picker | [ ] `frontend/src/components/analytics/FraudTrendChart.jsx` + `VendorRiskTable.jsx` + `DetectorAccuracyChart.jsx` |
| **Day 2 (Oct 3)** | [ ] `frontend/src/services/analyticsService.js` — analytics API calls | [ ] `frontend/src/hooks/useAuth.js` + `useInspection.js` + `useReview.js` + `useAnalytics.js` — custom hooks |
| **Day 3 (Oct 5)** | [ ] PDF download button integrate karo, CSV export add karo | [ ] `frontend/src/utils/formatters.js` + `validators.js` + `constants.js` — utility functions |
| **Day 4 (Oct 6)** | [ ] Responsive design fix karo (mobile + tablet), dark mode polish | [ ] UI polish — animations, transitions, loading states, empty states, error states |
| **Day 5 (Oct 7)** | [ ] `frontend/vercel.json` (Vercel Frontend) + `backend/render.yaml` (Render Backend) + `docker-compose.yml` Cloud Deployment setup | [ ] `.github/workflows/ci.yml` — GitHub Actions CI/CD pipeline setup + `docs/deployment.md` |
| **Day 6 (Oct 8)** | [ ] Dono milke: **PROJECT DONE** 🎉 — final demo, README update, git tag v1.0.0 | [ ] Dono milke: Final Demo & Release |

---

## 📊 Summary

| Phase | Duration | Dates | What | Workload Level |
|:---|:---|:---|:---|:---|
| **Sprint Phase 1: Heavy Backend** | Aug 10 – Aug 27 | 2.5 weeks | Core Setup + Models + Schemas + All API Routers + Shared Services + Pipeline Layer A | ⚡ **HIGH VELOCITY** (Pre-classes) |
| **Phase 2: Steady Pipeline** | Aug 28 – Sep 17 | 3 weeks | 9 Evidence Agents + Fusion + Debate + Causal Reasoning + Judge + Policy + End-to-End Tests | ☕ **STEADY PACE** (Post-classes) |
| **Phase 3: Frontend & Cloud** | Sep 18 – Oct 7 | 3 weeks | React Pages + Components + Analytics + Vercel + Render + CI/CD | ☕ **STEADY PACE** (Post-classes) |
| **Total** | **9 weeks** | Aug 7 – Oct 7 | **Complete Production App** | **Finished 8 Days Early!** |

---

## 👤 Work Split Summary

| Area | Anil | Disha |
|:---|:---|:---|
| **Core Setup** | config, security, middleware, main.py | database, logging, exceptions, migrations |
| **Models & Schemas** | user, inspection, review models & auth/inspection schemas | product, evidence, analytics models & product/report schemas |
| **Routes & Shared** | auth, products, inspections, reviews, reports, analytics, admin routers | llm_client, memory, evidence_store, tool_registry, knowledge_graph |
| **Pipeline Stages** | quality_check, authenticity, reference_match, roi_scheduler, evidence_fusion, causal_reasoning, policy_engine | debate, judge (+ paired testing on all stages) |
| **Agents** | base_agent, structural, component, connector, usage | ocr, label, material, manufacturing, vlm |
| **Services** | embedding, review_service, analytics_service | fraud_memory, reporting_service, notification |
| **Frontend Pages** | Login, Dashboard, NewInspection, InspectionList, InspectionDetail, HumanReview, Settings, Analytics | ProductCatalog, ROIEditor (+ all components, hooks, services) |
| **DevOps & Cloud** | Docker, Vercel (Frontend), Render (Backend), Makefile, end-to-end tests | CI/CD, docs/, test fixtures, test suites |

> **Note:** Har Saturday (Day 6) dono milke code review + integration test karenge.

---

## 📈 DAY-WISE PROGRESS TRACKER

> ✅ = Done | 🔄 = In Progress | ⬜ = Not Started
>
> Jab bhi koi task complete ho, uska checkbox `[ ]` ko `[x]` mein change kardo aur status emoji update kardo.

---

### ⚡ SPRINT PHASE (Aug 7 – Aug 27) — Pre-Classes

| # | Date | Who | File(s) | Task Description | Status |
|:--|:-----|:----|:--------|:-----------------|:------:|
| 1 | Aug 7 | Anil | `.gitignore`, `README.md`, `LICENSE`, `.env.example`, `Makefile`, folder structure | [x] Project repo + folder structure setup | ✅ |
| 2 | Aug 7 | Disha | `requirements.txt`, `venv/` | [x] Dependencies list + virtual environment | ✅ |
| 3 | Aug 8 | Anil | `core/config.py` | [x] Pydantic-settings environment config | ✅ |
| 4 | Aug 8 | Disha | `core/database.py` | [x] SQLAlchemy 2.0 async engine + session | ✅ |
| 5 | Aug 9 | Anil | `core/security.py` | [x] JWT tokens + Argon2/bcrypt password hashing | ✅ |
| 6 | Aug 9 | Disha | `core/exceptions.py` | [x] Custom HTTP error classes | ✅ |
| 7 | Aug 10 | Anil | `core/middleware.py`, `core/redis_client.py` | [ ] CORS + error handler + request logging + Upstash Redis | ⬜ |
| 8 | Aug 10 | Disha | `core/logging_config.py` | [ ] Structured JSON logging setup | ⬜ |
| 9 | Aug 11 | Anil | `app/main.py` | [ ] FastAPI app + middleware attach + startup/shutdown | ⬜ |
| 10 | Aug 11 | Disha | `alembic.ini`, `migrations/env.py` | [ ] Alembic migration setup | ⬜ |
| 11 | Aug 12 | Anil | `models/user.py`, `models/inspection.py`, `models/review.py` | [ ] User + Inspection + HumanReview + AuditLog tables | ⬜ |
| 12 | Aug 12 | Disha | `models/product.py`, `models/evidence.py`, `models/analytics.py` | [ ] GoldenReference + Evidence + FraudPattern + VendorScore tables | ⬜ |
| 13 | Aug 14 | Anil | `schemas/auth.py`, `schemas/inspection.py`, `schemas/review.py` | [ ] Auth + Inspection + Review Pydantic schemas | ⬜ |
| 14 | Aug 14 | Disha | `schemas/product.py`, `schemas/report.py` | [ ] Product + Report Pydantic schemas | ⬜ |
| 15 | Aug 15 | Anil | `migrations/versions/001_initial_tables.py`, `routers/auth.py` | [ ] Initial migration + Auth API (login/register/me) | ⬜ |
| 16 | Aug 15 | Disha | `shared/llm_client.py` | [ ] NVIDIA NIM wrapper (chat + vision via OpenAI SDK) | ⬜ |
| 17 | Aug 16 | Anil | `routers/products.py` | [ ] Product CRUD endpoints (upload, list, delete, FAISS sync) | ⬜ |
| 18 | Aug 16 | Disha | `shared/memory.py` | [ ] Working Memory class (per-inspection state) | ⬜ |
| 19 | Aug 17 | Anil | `routers/inspections.py` | [ ] POST /inspect, GET /inspections, GET /inspections/{id} | ⬜ |
| 20 | Aug 17 | Disha | `shared/evidence_store.py` | [ ] Append-only Evidence Store + audit trail | ⬜ |
| 21 | Aug 18 | Anil | `routers/reviews.py`, `routers/reports.py` | [ ] Review queue + verdict submit + PDF download endpoints | ⬜ |
| 22 | Aug 18 | Disha | `shared/tool_registry.py` | [ ] Tool Registry (tool name → function mapping) | ⬜ |
| 23 | Aug 19 | Anil | `routers/analytics.py`, `routers/admin.py` | [ ] Dashboard data + admin settings endpoints | ⬜ |
| 24 | Aug 19 | Disha | `shared/knowledge_graph.py` | [ ] Fraud Knowledge Graph (NetworkX based) | ⬜ |
| 25 | Aug 21 | Anil | `pipeline/state.py` | [ ] Pipeline TypedDict state definition | ⬜ |
| 26 | Aug 21 | Disha | `utils/image_utils.py` | [ ] Crop, resize, normalize, blur/brightness check | ⬜ |
| 27 | Aug 22 | Anil | `pipeline/stages/quality_check.py` | [ ] Stage 1: blur, lighting, resolution, duplicate, smart resize | ⬜ |
| 28 | Aug 22 | Disha | `utils/cv_utils.py` | [ ] OpenCV wrappers (histogram, edge, homography) | ⬜ |
| 29 | Aug 23 | Anil | `pipeline/stages/authenticity.py` | [ ] Stage 2: ELA, EXIF, screenshot detect, noise analysis | ⬜ |
| 30 | Aug 23 | Disha | `pipeline/stages/authenticity.py` (cont.) | [ ] Copy-move detection, lighting consistency, scoring | ⬜ |
| 31 | Aug 24 | Anil | `services/embedding_service.py` | [ ] CLIP embedding + FAISS index build/search/delete | ⬜ |
| 32 | Aug 24 | Disha | `utils/file_utils.py` | [ ] File I/O, path helpers, temp file cleanup | ⬜ |
| 33 | Aug 25 | Anil | `pipeline/stages/reference_match.py` | [ ] Stage 3: FAISS search, Part ID, angle verify, ROI load | ⬜ |
| 34 | Aug 25 | Disha | `data/roi_templates/` | [ ] 2-3 sample ROI template JSON files | ⬜ |
| 35 | Aug 26 | Anil | `pipeline/stages/roi_scheduler.py` | [ ] Stage 4: ROI → agent mapping, crop, parallel schedule | ⬜ |
| 36 | Aug 26 | Both | — | [ ] Stage 1-4 integration test (image upload → ROI crop) | ⬜ |
| 37 | Aug 27 | Anil | `pipeline/agents/base_agent.py` | [ ] Abstract base class for all agents | ⬜ |
| 38 | Aug 27 | Disha | `pipeline/agents/ocr_agent.py` | [ ] EasyOCR text extraction agent | ⬜ |

---

### ☕ NORMAL PHASE (Aug 28 – Oct 8) — Post-Classes

| # | Date | Who | File(s) | Task Description | Status |
|:--|:-----|:----|:--------|:-----------------|:------:|
| 39 | Aug 28 | Anil | `pipeline/agents/structural_agent.py` | [ ] SSIM score, JET heatmap, anomaly regions | ⬜ |
| 40 | Aug 28 | Disha | `pipeline/agents/label_agent.py` | [ ] Template matching, QC seals, logos check | ⬜ |
| 41 | Aug 29 | Anil | `pipeline/agents/component_agent.py` | [ ] Contour detection, capacitor/IC count, missing parts | ⬜ |
| 42 | Aug 29 | Disha | `pipeline/agents/material_agent.py` | [ ] HSV histogram, texture, non-OEM material detect | ⬜ |
| 43 | Aug 30 | Anil | `pipeline/agents/connector_agent.py` | [ ] Edge detection, pins, connector shape, damage | ⬜ |
| 44 | Aug 30 | Disha | `pipeline/agents/manufacturing_agent.py` | [ ] Solder quality, assembly marks, defects | ⬜ |
| 45 | Aug 31 | Anil | `pipeline/agents/usage_agent.py` | [ ] Wear patterns, scratches, discoloration | ⬜ |
| 46 | Aug 31 | Disha | `pipeline/agents/vlm_agent.py` | [ ] NVIDIA NIM Vision Model inspection | ⬜ |
| 47 | Sep 1 | Anil | — | [ ] Agent testing — sample ROI crops pe verify | ⬜ |
| 48 | Sep 1 | Disha | — | [ ] Agent testing & prompt tuning | ⬜ |
| 49 | Sep 2 | Both | — | [ ] All 9 agents unit test + edge cases | ⬜ |
| 50 | Sep 4 | Anil | `pipeline/stages/evidence_fusion.py` | [ ] Stage 6: multi-angle merge, confidence aggregation | ⬜ |
| 51 | Sep 4 | Disha | `pipeline/stages/debate.py` | [ ] Stage 7: multi-agent debate, LLM prompts | ⬜ |
| 52 | Sep 5 | Anil | `pipeline/stages/debate.py` (cont.) | [ ] Rounds logic, consensus, max rounds | ⬜ |
| 53 | Sep 5 | Disha | `pipeline/stages/evidence_fusion.py` (cont.) | [ ] Cross-angle matching, IoU dedup | ⬜ |
| 54 | Sep 7 | Anil | `pipeline/stages/causal_reasoning.py` | [ ] Stage 8: evidence chain, root cause, LLM narrative | ⬜ |
| 55 | Sep 7 | Disha | `pipeline/stages/judge.py` | [ ] Stage 9: verdict (Accept/Reject/Review), confidence | ⬜ |
| 56 | Sep 8 | Anil | `pipeline/stages/policy_engine.py` | [ ] Stage 10: configurable rules, escalation | ⬜ |
| 57 | Sep 8 | Disha | `services/fraud_memory_service.py` | [ ] Stage 12: permanent storage, similar case search | ⬜ |
| 58 | Sep 9 | Anil | `services/review_service.py` | [ ] Stage 11: human review logic, audit log | ⬜ |
| 59 | Sep 9 | Disha | `services/reporting_service.py` | [ ] Stage 13: ReportLab PDF, evidence embed | ⬜ |
| 60 | Sep 10 | Anil | `services/analytics_service.py` | [ ] Stage 14: fraud trends, vendor scores, stats | ⬜ |
| 61 | Sep 10 | Both | — | [ ] Stage 6-14 integration test | ⬜ |
| 62 | Sep 11 | Anil | `pipeline/workflow.py` | [ ] LangGraph StateGraph, nodes + edges | ⬜ |
| 63 | Sep 11 | Disha | `pipeline/workflow.py` (cont.) | [ ] Conditional edges (quality fail → stop, etc.) | ⬜ |
| 64 | Sep 12 | Anil | `routers/inspections.py` (update) | [ ] Pipeline trigger from POST /inspect | ⬜ |
| 65 | Sep 12 | Disha | `services/notification_service.py` | [ ] Alerts (review needed, quarantine triggered) | ⬜ |
| 66 | Sep 14 | Anil | `routers/admin.py` (update) | [ ] Threshold tuning, ROI upload, policy CRUD | ⬜ |
| 67 | Sep 14 | Disha | `migrations/versions/002_*.py`, `003_*.py` | [ ] Evidence store + fraud memory migrations | ⬜ |
| 68 | Sep 15 | Anil | — | [ ] Full pipeline E2E test (image → PDF report) | ⬜ |
| 69 | Sep 15 | Disha | `tests/conftest.py` | [ ] Test fixtures + test DB setup | ⬜ |
| 70 | Sep 16 | Anil | `tests/test_pipeline/` | [ ] Pipeline stage tests (quality, auth, ref, debate, judge, full) | ⬜ |
| 71 | Sep 16 | Disha | `tests/test_agents/` | [ ] Agent tests (ocr, label, component, structural, vlm) | ⬜ |
| 72 | Sep 17 | Anil | `tests/test_routers/`, `tests/test_services/` | [ ] Router + service tests | ⬜ |
| 73 | Sep 17 | Both | — | [ ] 🏁 **BACKEND DONE** — Full demo run | ⬜ |
| 74 | Sep 18 | Anil | `package.json`, `vite.config.js`, `index.html`, `main.jsx`, `App.jsx` | [ ] Vite + React project setup | ⬜ |
| 75 | Sep 18 | Disha | `src/index.css` | [ ] Global styles, design system, dark mode vars | ⬜ |
| 76 | Sep 19 | Anil | `context/AuthContext.jsx`, `context/ThemeContext.jsx`, `services/api.js` | [ ] Auth context + theme context + axios interceptors | ⬜ |
| 77 | Sep 19 | Disha | `components/common/Button,Modal,Card,Table,Badge,Loader,Toast` | [ ] Common UI components | ⬜ |
| 78 | Sep 21 | Anil | `pages/LoginPage.jsx` | [ ] Login/register form with JWT | ⬜ |
| 79 | Sep 21 | Disha | `components/layout/Sidebar,Header,PageWrapper,ProtectedRoute` | [ ] Layout components | ⬜ |
| 80 | Sep 22 | Anil | `pages/DashboardPage.jsx` | [ ] Dashboard — summary cards, recent inspections | ⬜ |
| 81 | Sep 22 | Disha | `routes/AppRoutes.jsx` | [ ] All routes + role-based access | ⬜ |
| 82 | Sep 23 | Anil | `pages/NewInspectionPage.jsx` | [ ] Image upload (drag-drop), metadata, pipeline trigger | ⬜ |
| 83 | Sep 23 | Disha | `components/inspection/ImageUploader.jsx` | [ ] Drag-drop component with preview + validation | ⬜ |
| 84 | Sep 24 | Anil | `pages/InspectionListPage.jsx` | [ ] Inspections table, filters, search, pagination | ⬜ |
| 85 | Sep 24 | Disha | `services/authService.js`, `inspectionService.js` | [ ] API call functions | ⬜ |
| 86 | Sep 25 | Anil | `pages/InspectionDetailPage.jsx` | [ ] Case detail, verdict banner, evidence cards, timeline | ⬜ |
| 87 | Sep 25 | Disha | `components/inspection/ImageCompare,HeatmapOverlay` | [ ] Side-by-side viewer + heatmap overlay | ⬜ |
| 88 | Sep 26 | Anil | `components/inspection/VerdictBanner,EvidenceCard,TimelineView` | [ ] Inspection detail sub-components | ⬜ |
| 89 | Sep 26 | Disha | `components/review/ROIOverlay.jsx` | [ ] Bounding box display on images | ⬜ |
| 90 | Sep 28 | Anil | `pages/HumanReviewPage.jsx` | [ ] Review workbench — approve/reject/override | ⬜ |
| 91 | Sep 28 | Disha | `components/review/ReviewPanel,CommentBox` | [ ] Review panel + comment box | ⬜ |
| 92 | Sep 29 | Anil | `pages/ProductCatalogPage.jsx` | [ ] Golden reference upload, list, delete, FAISS sync | ⬜ |
| 93 | Sep 29 | Disha | `pages/ROIEditorPage.jsx` | [ ] Canvas pe ROI bounding boxes draw | ⬜ |
| 94 | Sep 30 | Anil | `pages/SettingsPage.jsx` | [ ] Threshold tuning, policy rules, system config | ⬜ |
| 95 | Sep 30 | Disha | `services/productService,reviewService,reportService` | [ ] API call functions | ⬜ |
| 96 | Oct 1 | Both | — | [ ] All pages backend connect + API integration test | ⬜ |
| 97 | Oct 2 | Anil | `pages/AnalyticsPage.jsx` | [ ] Charts layout, filters, date range picker | ⬜ |
| 98 | Oct 2 | Disha | `components/analytics/FraudTrend,VendorRisk,DetectorAccuracy` | [ ] Analytics chart components | ⬜ |
| 99 | Oct 3 | Anil | `services/analyticsService.js` | [ ] Analytics API calls | ⬜ |
| 100 | Oct 3 | Disha | `hooks/useAuth,useInspection,useReview,useAnalytics` | [ ] Custom React hooks | ⬜ |
| 101 | Oct 5 | Anil | — | [ ] PDF download button + CSV export | ⬜ |
| 102 | Oct 5 | Disha | `utils/formatters,validators,constants` | [ ] Utility functions | ⬜ |
| 103 | Oct 6 | Anil | — | [ ] Responsive design (mobile + tablet) + dark mode polish | ⬜ |
| 104 | Oct 6 | Disha | — | [ ] UI polish — animations, transitions, loading/empty/error states | ⬜ |
| 105 | Oct 7 | Anil | `vercel.json`, `render.yaml`, `docker-compose.yml`, `Dockerfile` | [ ] Cloud deployment (Vercel + Render + Docker) | ⬜ |
| 106 | Oct 7 | Disha | `.github/workflows/ci.yml`, `docs/deployment.md` | [ ] CI/CD pipeline + deployment docs | ⬜ |
| 107 | Oct 8 | Both | — | [ ] 🎉 **PROJECT DONE** — Final demo, README update, git tag v1.0.0 | ⬜ |

---

### 📊 Progress Stats

| Metric | Count |
|:---|:---|
| **Total Tasks** | 107 |
| **Completed** | 6 / 107 |
| **Remaining** | 101 / 107 |
| **Progress** | ██░░░░░░░░░░░░░░░░░░ 5.6% |
| **Sprint Phase Tasks (Aug 7–27)** | 38 |
| **Normal Phase Tasks (Aug 28–Oct 8)** | 69 |

> **Kaise update karein?** Task complete hone pe:
> 1. `[ ]` ko `[x]` mein change karo
> 2. Status column mein `⬜` ko `✅` mein change karo
> 3. Bottom mein **Completed** count update karo aur progress bar badhao
