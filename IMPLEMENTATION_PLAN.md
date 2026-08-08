# 📋 VeriVision AI v2 — Implementation Plan

> **Team:** Disha , Anil  
> **Start:** 7 August 2026  
> **End:** ~15 October 2026 (2.5 months)  
> **Rule:** Backend first (7 weeks) → Frontend (3 weeks)  
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
│       │   ├── test_quality_check.py
│       │   ├── test_authenticity.py
│       │   ├── test_reference_match.py
│       │   ├── test_debate.py
│       │   ├── test_judge.py
│       │   └── test_full_pipeline.py
│       ├── test_agents/
│       │   ├── test_ocr_agent.py
│       │   ├── test_label_agent.py
│       │   ├── test_component_agent.py
│       │   ├── test_structural_agent.py
│       │   └── test_vlm_agent.py
│       ├── test_routers/
│       │   ├── test_auth.py
│       │   ├── test_inspections.py
│       │   └── test_products.py
│       └── test_services/
│           ├── test_embedding.py
│           └── test_reporting.py
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
│       │   │   ├── Button.jsx
│       │   │   ├── Modal.jsx
│       │   │   ├── Card.jsx
│       │   │   ├── Table.jsx
│       │   │   ├── Badge.jsx
│       │   │   ├── Loader.jsx
│       │   │   └── Toast.jsx
│       │   ├── layout/
│       │   │   ├── Sidebar.jsx
│       │   │   ├── Header.jsx
│       │   │   ├── PageWrapper.jsx
│       │   │   └── ProtectedRoute.jsx
│       │   ├── inspection/
│       │   │   ├── ImageUploader.jsx
│       │   │   ├── ImageCompare.jsx
│       │   │   ├── HeatmapOverlay.jsx
│       │   │   ├── EvidenceCard.jsx
│       │   │   ├── VerdictBanner.jsx
│       │   │   └── TimelineView.jsx
│       │   ├── review/
│       │   │   ├── ReviewPanel.jsx
│       │   │   ├── ROIOverlay.jsx
│       │   │   └── CommentBox.jsx
│       │   └── analytics/
│       │       ├── FraudTrendChart.jsx
│       │       ├── VendorRiskTable.jsx
│       │       └── DetectorAccuracyChart.jsx
│       │
│       ├── hooks/
│       │   ├── useAuth.js
│       │   ├── useInspection.js
│       │   ├── useReview.js
│       │   └── useAnalytics.js
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
│       │   ├── reviewService.js
│       │   ├── reportService.js
│       │   └── analyticsService.js
│       │
│       ├── routes/
│       │   └── AppRoutes.jsx
│       │
│       └── utils/
│           ├── formatters.js
│           ├── validators.js
│           └── constants.js
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

## 🗓️ PHASE 1: BACKEND (Week 1–7)

---

### Week 1 (Aug 7–12) — Project Setup & Foundation

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1** | Repo create, `.gitignore`, `README.md`, `LICENSE`, `.env.example`, `Makefile`, poora folder structure banao | `requirements.txt` — sab dependencies list karo, `venv` setup karo |
| **Day 2** | `backend/app/core/config.py` — pydantic-settings se environment variables load karo | `backend/app/core/database.py` — SQLAlchemy 2.0 async engine + asyncpg PostgreSQL session setup karo |
| **Day 3** | `backend/app/core/security.py` — JWT token creation, password hashing (bcrypt) | `backend/app/core/exceptions.py` — custom error classes banao (NotFound, Unauthorized, ValidationError, etc.) |
| **Day 4** | `backend/app/core/middleware.py` — CORS, global error handler, request logging middleware + `backend/app/core/redis_client.py` — Upstash Redis connection setup (rate limiting + caching) | `backend/app/core/logging_config.py` — structured JSON logging setup karo |
| **Day 5** | `backend/app/main.py` — FastAPI app create karo, middleware attach karo, startup/shutdown events | `backend/alembic.ini` + `backend/migrations/env.py` — Alembic migration setup karo |
| **Day 6** | Dono milke: `backend/app/core/__init__.py` + sab `__init__.py` files banao, poora core/ test karo — server start hota hai, .env load hota hai, logging kaam karta hai |

---

### Week 2 (Aug 14–19) — Database Models & Schemas

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1** | `backend/app/models/__init__.py` + `user.py` — User table (id, email, password_hash, role, created_at) | `backend/app/models/product.py` — GoldenReference table (id, part_code, name, image_path, embedding, roi_template_path, etc.) |
| **Day 2** | `backend/app/models/inspection.py` — Inspection + InspectionImage tables | `backend/app/models/evidence.py` — Evidence + DetectorResult tables |
| **Day 3** | `backend/app/models/review.py` — HumanReview + AuditLog tables | `backend/app/models/analytics.py` — FraudPattern + VendorScore tables |
| **Day 4** | `backend/app/schemas/__init__.py` + `auth.py` — LoginRequest, RegisterRequest, TokenResponse | `backend/app/schemas/product.py` — ProductCreate, ProductResponse, ROITemplateSchema |
| **Day 5** | `backend/app/schemas/inspection.py` — InspectionCreate, InspectionResult, InspectionList | `backend/app/schemas/review.py` + `report.py` — ReviewSubmit, ReviewResponse, ReportMeta |
| **Day 6** | `backend/migrations/versions/001_initial_tables.py` — pehli migration generate karo, `alembic upgrade head` test karo | Dono milke: sab models + schemas review karo, migration test karo |

---

### Week 3 (Aug 21–26) — API Routes & Shared Services

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1** | `backend/app/routers/__init__.py` + `auth.py` — POST /login, POST /register, GET /me | `backend/app/shared/__init__.py` + `llm_client.py` — NVIDIA NIM wrapper banao (chat + vision dono via OpenAI SDK), connection test |
| **Day 2** | `backend/app/routers/products.py` — CRUD endpoints for golden references (upload, list, delete, cascade sync with FAISS) | `backend/app/shared/memory.py` — Working Memory class banao (per-inspection state store) |
| **Day 3** | `backend/app/routers/inspections.py` — POST /inspect (upload + trigger pipeline), GET /inspections (list), GET /inspections/{id} | `backend/app/shared/evidence_store.py` — Evidence Store banao (append-only, never overwrite, audit trail) |
| **Day 4** | `backend/app/routers/reviews.py` — GET /reviews (queue), POST /reviews/{id} (submit verdict) | `backend/app/shared/tool_registry.py` — Tool Registry banao (tool name → function mapping) |
| **Day 5** | `backend/app/routers/reports.py` — GET /reports/{id}/pdf (download) | `backend/app/shared/knowledge_graph.py` — Fraud Knowledge Graph banao (NetworkX based) |
| **Day 6** | `backend/app/routers/analytics.py` + `admin.py` — dashboard data + admin settings endpoints | Dono milke: sab routes Swagger UI pe test karo, shared services unit test karo |

---

### Week 4 (Aug 28–Sep 2) — Pipeline Layer A (Deterministic Stages)

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1** | `backend/app/pipeline/__init__.py` + `state.py` — Pipeline TypedDict state define karo | `backend/app/utils/__init__.py` + `image_utils.py` — crop, resize, normalize, blur check, brightness check |
| **Day 2** | `backend/app/pipeline/stages/__init__.py` + `quality_check.py` — Stage 1: blur, lighting, format, resolution, duplicate detection, smart resize, background crop | `backend/app/utils/cv_utils.py` — OpenCV wrappers (histogram, edge detection, homography, etc.) |
| **Day 3** | `backend/app/pipeline/stages/authenticity.py` — Stage 2: ELA, EXIF validation, screenshot detection, noise analysis | Authenticity cont. — copy-move detection, lighting consistency, authenticity score calculation |
| **Day 4** | `backend/app/services/__init__.py` + `embedding_service.py` — CLIP embedding generation + FAISS index build/search/delete | `backend/app/utils/file_utils.py` — file I/O, path helpers, temp file cleanup |
| **Day 5** | `backend/app/pipeline/stages/reference_match.py` — Stage 3: FAISS search, Part ID match, angle verification, ROI template loading, manufacturer params | `data/roi_templates/` — 2-3 sample ROI template JSON files banao (motherboard, label, chip) |
| **Day 6** | `backend/app/pipeline/stages/roi_scheduler.py` — Stage 4: ROI template read, ROI type → agent mapping, golden+target crop, parallel scheduling | Dono milke: Stage 1-4 individually test karo — image upload se ROI crop tak poora flow |

---

### Week 5 (Sep 4–9) — Pipeline Stage 5: Specialist Evidence Agents

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1** | `backend/app/pipeline/agents/__init__.py` + `base_agent.py` — Abstract base class (inspect(), get_evidence(), confidence scale) | `backend/app/pipeline/agents/ocr_agent.py` — EasyOCR text read, golden vs target char-level diff, mismatches report |
| **Day 2** | `backend/app/pipeline/agents/structural_agent.py` — SSIM score, JET heatmap generate, anomaly regions mark | `backend/app/pipeline/agents/label_agent.py` — Template matching, QC seals, logos, stickers check |
| **Day 3** | `backend/app/pipeline/agents/component_agent.py` — Contour detection, capacitors/ICs count, position compare, missing parts | `backend/app/pipeline/agents/material_agent.py` — Color histogram (HSV), surface texture, non-OEM material detect |
| **Day 4** | `backend/app/pipeline/agents/connector_agent.py` — Edge detection, pins check, connector shape match, damage detect | `backend/app/pipeline/agents/manufacturing_agent.py` — Solder quality, assembly marks, manufacturing defects |
| **Day 5** | `backend/app/pipeline/agents/usage_agent.py` — Wear patterns (scratches, discoloration, age signs) | `backend/app/pipeline/agents/vlm_agent.py` — NVIDIA NIM Vision Model (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`) visual inspection, semantic defect description |
| **Day 6** | Dono milke: sab 9 agents individually test karo — sample ROI crops pe run karke evidence output verify karo |

---

### Week 6 (Sep 11–16) — Pipeline Layer B & C (AI + Business Stages)

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1** | `backend/app/pipeline/stages/evidence_fusion.py` — Stage 6: multi-angle merge, duplicate removal, confidence aggregation | `backend/app/pipeline/stages/debate.py` — Stage 7: multi-agent debate, LLM prompts for argue/defend/challenge |
| **Day 2** | Debate cont. — rounds logic, consensus check, max rounds, accepted evidence output | Evidence Fusion cont. — cross-angle matching, IoU duplicate detection, angle contribution tracking |
| **Day 3** | `backend/app/pipeline/stages/causal_reasoning.py` — Stage 8: evidence chain, root cause vs secondary effects, LLM narrative | `backend/app/pipeline/stages/judge.py` — Stage 9: all evidence read, LLM verdict (Accept/Reject/Review), confidence + fraud probability |
| **Day 4** | `backend/app/pipeline/stages/policy_engine.py` — Stage 10: configurable rules, fraud score → action, escalation rules | `backend/app/services/fraud_memory_service.py` — Stage 12: permanent storage, index by part/vendor/site, similar case search |
| **Day 5** | `backend/app/services/review_service.py` — Stage 11: human review logic, approve/reject/override, audit log | `backend/app/services/reporting_service.py` — Stage 13: ReportLab PDF, evidence embed, causal chain, heatmaps |
| **Day 6** | `backend/app/services/analytics_service.py` — Stage 14: fraud trends, vendor scores, detector accuracy, tampering stats | Dono milke: Stage 6-14 individually test karo |

---

### Week 7 (Sep 18–23) — Pipeline Integration & Full Testing

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1** | `backend/app/pipeline/workflow.py` — LangGraph StateGraph, sab stages nodes mein connect, edges define | Workflow cont. — conditional edges (quality fail → stop, authenticity low → flag, policy → human review) |
| **Day 2** | `backend/app/routers/inspections.py` update — POST /inspect se pipeline trigger, results DB mein save | `backend/app/services/notification_service.py` — alerts (human review needed, quarantine triggered) |
| **Day 3** | `backend/app/routers/admin.py` update — threshold tuning, ROI template upload, policy rules CRUD | `backend/migrations/versions/002_add_evidence_store.py` + `003_add_fraud_memory.py` — additional migrations |
| **Day 4** | Full pipeline end-to-end test — image upload se PDF report tak poora flow | `backend/tests/conftest.py` — test fixtures + test DB setup |
| **Day 5** | `backend/tests/test_pipeline/` — test_quality_check.py, test_authenticity.py, test_reference_match.py, test_debate.py, test_judge.py, test_full_pipeline.py | `backend/tests/test_agents/` — test_ocr_agent.py, test_label_agent.py, test_component_agent.py, test_structural_agent.py, test_vlm_agent.py |
| **Day 6** | `backend/tests/test_routers/` — test_auth.py, test_inspections.py, test_products.py + `backend/tests/test_services/` — test_embedding.py, test_reporting.py | Dono milke: **Backend DONE** ✅ — poora pipeline demo run, sab APIs test, sab stages working |

---

## 🗓️ PHASE 2: FRONTEND (Week 8–10)

---

### Week 8 (Sep 25–30) — Frontend Setup & Core Pages

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1** | Vite + React setup — `package.json`, `vite.config.js`, `index.html`, `frontend/src/main.jsx`, `frontend/src/App.jsx`, folder structure, dependencies install | `frontend/src/index.css` — global styles, design system (colors, fonts, spacing, dark mode variables) |
| **Day 2** | `frontend/src/context/AuthContext.jsx` + `frontend/src/context/ThemeContext.jsx` + `frontend/src/services/api.js` — auth context, theme context, axios setup with interceptors | `frontend/src/components/common/Button.jsx`, `Modal.jsx`, `Card.jsx`, `Table.jsx`, `Badge.jsx`, `Loader.jsx`, `Toast.jsx` |
| **Day 3** | `frontend/src/pages/LoginPage.jsx` — login/register form with JWT | `frontend/src/components/layout/Sidebar.jsx`, `Header.jsx`, `PageWrapper.jsx`, `ProtectedRoute.jsx` |
| **Day 4** | `frontend/src/pages/DashboardPage.jsx` — main landing page, summary cards, recent inspections | `frontend/src/routes/AppRoutes.jsx` — sab routes define, role-based access (admin vs operator) |
| **Day 5** | `frontend/src/pages/NewInspectionPage.jsx` — image upload (drag-drop), metadata form, pipeline trigger | `frontend/src/components/inspection/ImageUploader.jsx` — drag-drop component with preview + validation |
| **Day 6** | `frontend/src/pages/InspectionListPage.jsx` — inspections table, filter by status, search, pagination | `frontend/src/services/authService.js` + `inspectionService.js` — API call functions |

---

### Week 9 (Oct 2–7) — Inspection Detail, Review & Admin Pages

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1** | `frontend/src/pages/InspectionDetailPage.jsx` — case detail view, verdict banner, evidence cards, pipeline timeline | `frontend/src/components/inspection/ImageCompare.jsx` + `HeatmapOverlay.jsx` — side-by-side viewer + heatmap overlay |
| **Day 2** | `frontend/src/components/inspection/VerdictBanner.jsx` + `EvidenceCard.jsx` + `TimelineView.jsx` | `frontend/src/components/review/ROIOverlay.jsx` — bounding box display on images |
| **Day 3** | `frontend/src/pages/HumanReviewPage.jsx` — review workbench, approve/reject/override, comment | `frontend/src/components/review/ReviewPanel.jsx` + `CommentBox.jsx` |
| **Day 4** | `frontend/src/pages/ProductCatalogPage.jsx` — golden reference upload, list, delete, FAISS sync | `frontend/src/pages/ROIEditorPage.jsx` — canvas pe ROI bounding boxes draw karo |
| **Day 5** | `frontend/src/pages/SettingsPage.jsx` — threshold tuning, policy rules, system config | `frontend/src/services/productService.js` + `reviewService.js` + `reportService.js` — API call functions |
| **Day 6** | Dono milke: sab pages backend se connect karo, API integration test karo |

---

### Week 10 (Oct 9–15) — Analytics, Polish & Final Testing

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1** | `frontend/src/pages/AnalyticsPage.jsx` — charts layout, filters, date range picker | `frontend/src/components/analytics/FraudTrendChart.jsx` + `VendorRiskTable.jsx` + `DetectorAccuracyChart.jsx` |
| **Day 2** | `frontend/src/services/analyticsService.js` — analytics API calls | `frontend/src/hooks/useAuth.js` + `useInspection.js` + `useReview.js` + `useAnalytics.js` — custom hooks |
| **Day 3** | PDF download button integrate karo, CSV export add karo | `frontend/src/utils/formatters.js` + `validators.js` + `constants.js` — utility functions |
| **Day 4** | Responsive design fix karo (mobile + tablet), dark mode polish | UI polish — animations, transitions, loading states, empty states, error states |
| **Day 5** | Full end-to-end testing — login se PDF download tak | `docker-compose.yml` + `backend/Dockerfile` + `frontend/Dockerfile` + `frontend/vercel.json` (Vercel) + `backend/render.yaml` (Render) |
| **Day 6** | `.github/workflows/ci.yml` — GitHub Actions CI/CD pipeline setup + `docs/deployment.md` | Dono milke: **PROJECT DONE** ✅ — final demo, README update, git tag v1.0.0 |

---

## 📊 Summary

| Phase | Duration | Weeks | What |
|:---|:---|:---|:---|
| **Phase 1: Backend** | Aug 7 – Sep 23 | 7 weeks | Core + Models + Routes + Pipeline (14 stages) + Shared Services + Tests |
| **Phase 2: Frontend** | Sep 25 – Oct 15 | 3 weeks | Pages + Components + API Integration + Analytics + Polish |
| **Total** | Aug 7 – Oct 15 | **10 weeks** | **Complete Production App** |

---

## 👤 Work Split Summary

| Area | Anil | Disha |
|:---|:---|:---|
| **Core Setup** | config, security, middleware, main.py | database, logging, exceptions, migrations |
| **Models** | user, inspection, review | product, evidence, analytics |
| **Routes** | auth, inspections, reviews, reports, admin, analytics | (shared services — llm, memory, evidence, tools, graph) |
| **Pipeline Stages** | quality_check, authenticity, reference_match, roi_scheduler, evidence_fusion, causal_reasoning, policy_engine | debate, judge (+ paired testing on all stages) |
| **Agents** | base_agent, structural, component, connector, usage | ocr, label, material, manufacturing, vlm |
| **Services** | embedding, review_service, analytics_service | fraud_memory, reporting_service, notification |
| **Frontend Pages** | Login, Dashboard, NewInspection, InspectionList, InspectionDetail, HumanReview, Settings, Analytics | ProductCatalog, ROIEditor (+ all components, hooks, services) |
| **DevOps & Cloud** | Docker, Vercel (Frontend), Render (Backend), Makefile, end-to-end tests | docs/, test fixtures, test suites |

> **Note:** Har Saturday (Day 6) dono milke code review + integration test karenge. Koi bhi stage individually test hona chahiye pehle, phir dono ka code merge hoga.

---

## ✅ File Coverage Checklist

Total unique files in plan: **~120 files**

| Category | Count | All Covered? |
|:---|:---|:---|
| Root config files (.gitignore, README, LICENSE, .env.example, Makefile, docker-compose.yml) | 6 | ✅ |
| Backend Core (config, database, security, exceptions, middleware, redis_client, logging, main.py) | 8 | ✅ |
| Backend Models (user, product, inspection, evidence, review, analytics) | 6 | ✅ |
| Backend Schemas (auth, product, inspection, review, report) | 5 | ✅ |
| Backend Routers (auth, inspections, products, reviews, reports, analytics, admin) | 7 | ✅ |
| Pipeline Stages (quality_check, authenticity, reference_match, roi_scheduler, evidence_fusion, debate, causal_reasoning, judge, policy_engine) | 9 | ✅ |
| Pipeline Agents (base + ocr, label, component, structural, material, connector, manufacturing, usage, vlm) | 10 | ✅ |
| Pipeline Core (workflow.py, state.py) | 2 | ✅ |
| Shared Services (memory, evidence_store, tool_registry, knowledge_graph, llm_client) | 5 | ✅ |
| Business Services (embedding, reporting, review, analytics, fraud_memory, notification) | 6 | ✅ |
| Utils (image_utils, cv_utils, file_utils) | 3 | ✅ |
| Migrations (alembic.ini, env.py, 3 version files) | 5 | ✅ |
| Backend Tests (conftest + pipeline tests + agent tests + router tests + service tests) | ~15 | ✅ |
| Frontend Pages (10 pages) | 10 | ✅ |
| Frontend Components (common 7 + layout 4 + inspection 6 + review 3 + analytics 3) | 23 | ✅ |
| Frontend Hooks (4) | 4 | ✅ |
| Frontend Context (Auth + Theme) | 2 | ✅ |
| Frontend Services (api + 6 domain services) | 7 | ✅ |
| Frontend Utils (formatters, validators, constants) | 3 | ✅ |
| Frontend Core (main.jsx, App.jsx, index.css, AppRoutes.jsx, index.html, vite.config.js, package.json) | 7 | ✅ |
| Dockerfiles (backend + frontend) | 2 | ✅ |
| Data folders (golden_images, inspection_uploads, heatmaps, reports, roi_templates, faiss_index) | 6 | ✅ |
| Docs (architecture, api_reference, deployment, contributing) | 4 | ✅ |
| `__init__.py` files (core, models, schemas, routers, pipeline, stages, agents, shared, services, utils) | 10 | ✅ |
