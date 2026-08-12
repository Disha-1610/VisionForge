# 📋 VeriVision AI — MVP Implementation Plan

> **Team:** Anil + Disha
> **Start:** 17 August 2026
> **Target End:** ~12 September 2026 (4 weeks)
> **Strategy:** Scoped MVP — 8-stage pipeline (Scheduler and Evidence Execution split, per Disha's update), 4 evidence agents, YOLO added to the Structural Agent. Every tool/model is free-tier or fully local — no paid keys anywhere. Focus is pipeline accuracy and explainable reports, not feature breadth.
> **Rule:** Backend first → Frontend → Deploy
> **Days:** Monday–Saturday (6 days/week)

---

## 📁 Project Structure

```
VeriVision-MVP/
├── .gitignore
├── README.md
├── docker-compose.yml
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
│   │       └── 001_initial_tables.py
│   │
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── security.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── product.py            # GoldenReference
│   │   │   ├── inspection.py         # includes verdict, review, vendor, location fields
│   │   │   └── evidence.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── inspection.py
│   │   │   ├── product.py
│   │   │   └── report.py
│   │   │
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── products.py           # golden reference upload
│   │   │   ├── inspections.py        # upload + trigger pipeline + approve/override
│   │   │   ├── reports.py            # report fetch (PDF/JSON)
│   │   │   └── analytics.py          # summary, by-vendor, by-location, monthly-trend
│   │   │
│   │   ├── pipeline/
│   │   │   ├── workflow.py           # LangGraph — wires all 8 stages
│   │   │   ├── state.py
│   │   │   │
│   │   │   ├── stages/
│   │   │   │   ├── quality_check.py       # Stage 1 — OpenCV, free/local
│   │   │   │   ├── authenticity.py        # Stage 2 — OpenCV+Pillow, free/local
│   │   │   │   ├── reference_match.py     # Stage 3 — CLIP+FAISS, free/local
│   │   │   │   ├── roi_scheduler.py       # Stage 4 — pure logic, no model
│   │   │   │   ├── evidence_execution.py  # Stage 5 — runs the 4 agents
│   │   │   │   ├── evidence_fusion.py     # Stage 6 — pure logic, no model
│   │   │   │   ├── judge.py               # Stage 7 — NVIDIA NIM free tier (DeepSeek-V3.2), Groq fallback
│   │   │   │   └── policy_engine.py       # Stage 8 — code + ReportLab
│   │   │   │
│   │   │   └── agents/
│   │   │       ├── base_agent.py
│   │   │       ├── ocr_agent.py           # EasyOCR, free/local
│   │   │       ├── label_agent.py         # OpenCV template matching, free/local
│   │   │       ├── structural_agent.py    # SSIM + YOLO11n component detection
│   │   │       └── vlm_agent.py           # NVIDIA NIM free tier (Nemotron Nano Omni), Groq fallback
│   │   │
│   │   ├── shared/
│   │   │   ├── memory.py             # Working Memory
│   │   │   ├── evidence_store.py
│   │   │   └── llm_client.py         # NVIDIA NIM primary, Groq free-tier fallback
│   │   │
│   │   ├── services/
│   │   │   ├── embedding_service.py  # CLIP + FAISS
│   │   │   ├── reporting_service.py
│   │   │   └── analytics_service.py  # vendor/location/monthly aggregation queries
│   │   │
│   │   └── utils/
│   │       ├── image_utils.py
│   │       ├── cv_utils.py
│   │       └── file_utils.py
│   │
│   └── tests/
│       ├── conftest.py
│       ├── test_pipeline/
│       └── test_agents/
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   │
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       │
│       ├── pages/
│       │   ├── LoginPage.jsx
│       │   ├── DashboardPage.jsx         # includes inspection list
│       │   ├── NewInspectionPage.jsx     # captures vendor + location at intake
│       │   ├── InspectionDetailPage.jsx  # report + verdict + approve/override
│       │   └── AnalyticsPage.jsx         # vendor/location fraud breakdown + monthly trend
│       │
│       ├── components/
│       │   ├── common/
│       │   ├── layout/
│       │   ├── inspection/
│       │   │   ├── ImageUploader.jsx
│       │   │   ├── ImageCompare.jsx
│       │   │   ├── ROIOverlay.jsx         # renders YOLO bounding boxes too
│       │   │   ├── EvidenceCard.jsx
│       │   │   └── VerdictBanner.jsx
│       │   └── analytics/
│       │       ├── FraudTrendChart.jsx
│       │       └── VendorLocationTable.jsx
│       │
│       ├── context/
│       │   └── AuthContext.jsx
│       │
│       ├── services/
│       │   ├── api.js
│       │   ├── authService.js
│       │   ├── inspectionService.js
│       │   ├── productService.js
│       │   └── analyticsService.js
│       │
│       └── routes/
│           └── AppRoutes.jsx
│
├── data/
│   ├── golden_images/
│   ├── inspection_uploads/
│   ├── roi_templates/
│   ├── faiss_index/
│   └── yolo_weights/
│       └── component_detector.pt     # YOLO11n, fine-tuned on your own golden images
│
└── docs/
    ├── VeriVision-AI-Pipeline-Architecture.md   # full pipeline design doc
    └── api_reference.md
```

---

## 🗓️ Week 1 (Aug 17–22) — Foundation (Backend Core)

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Aug 17)** | Repo create, `.gitignore`, `README.md`, folder structure, `requirements.txt` | DB models: `user.py`, `inspection.py` (+ vendor, location fields), `evidence.py`, `product.py` |
| **Day 2 (Aug 18)** | `core/security.py` — JWT token creation, password hashing (bcrypt) | `core/database.py` — async SQLAlchemy engine + Alembic init |
| **Day 3 (Aug 19)** | `schemas/auth.py` + `schemas/inspection.py` | `schemas/product.py` + `schemas/report.py` |
| **Day 4 (Aug 20)** | `routers/auth.py` (login/register/me) + `routers/products.py` (golden reference upload) | `routers/inspections.py` (skeleton) + `shared/evidence_store.py` |
| **Day 5 (Aug 21)** | `services/embedding_service.py` — CLIP + FAISS setup (local, free) | `shared/llm_client.py` — NVIDIA NIM wrapper + Groq free-tier fallback, `shared/memory.py` (working memory) |
| **Day 6 (Aug 22)** | Dono milke: auth + golden-reference upload flow end-to-end test | |

---

## 🗓️ Week 2 (Aug 24–29) — Pipeline Stages 1–5 + YOLO Fine-Tune

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Aug 24)** | Stage 1: `quality_check.py` — blur, lighting, format, resolution | Stage 2: `authenticity.py` — ELA, EXIF, basic tamper checks |
| **Day 2 (Aug 25)** | Stage 3: `reference_match.py` — FAISS search + ROI template loading | `data/roi_templates/` sample JSONs (2–3 parts) + `utils/image_utils.py` + **start YOLO dataset: annotate 15–20 golden images (capacitors, connectors, chips) on Roboflow free tier** |
| **Day 3 (Aug 26)** | Stage 4: `roi_scheduler.py` — ROI→agent mapping, execution plan | Stage 5: `evidence_execution.py` — runs the execution plan against the 4 agents + `agents/base_agent.py` + `agents/ocr_agent.py` |
| **Day 4 (Aug 27)** | `agents/label_agent.py` — template matching, seals, logos | `agents/structural_agent.py` — SSIM baseline + **finish YOLO annotation, fine-tune YOLO11n on free Colab GPU (nano model, <1hr on 20 images)** |
| **Day 5 (Aug 28)** | `agents/vlm_agent.py` — NVIDIA NIM free tier, Nemotron Nano Omni (vision+reasoning) | **Export YOLO weights to `data/yolo_weights/component_detector.pt`, integrate into `structural_agent.py`** — component count/presence comparison |
| **Day 6 (Aug 29)** | Dono milke: test Stages 1–5 end-to-end — upload → ROI evidence, verify YOLO detections on sample crops | |

---

## 🗓️ Week 3 (Aug 31–Sep 5) — Pipeline Stages 6–8 + Accuracy Testing

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Aug 31)** | Stage 6: `evidence_fusion.py` — multi-angle merge, weigh SSIM vs. YOLO signal | Stage 7: `judge.py` — prompt design (verdict + root cause), NVIDIA NIM free tier DeepSeek-V3.2 |
| **Day 2 (Sep 1)** | Stage 8: `policy_engine.py` — hardcoded rules → action | Stage 7 cont. — Judge testing/tuning on real cases |
| **Day 3 (Sep 2)** | Report generation (PDF/JSON) integration + `routers/analytics.py` | `services/reporting_service.py` + report schema + `services/analytics_service.py` (vendor/location/monthly aggregation) |
| **Day 4 (Sep 3)** | Dono milke: `pipeline/workflow.py` — wire all 8 stages via LangGraph | |
| **Day 5 (Sep 4)** | Dono milke: curate 20–30 golden-vs-fraud test image pairs, run full pipeline, log results (include YOLO detection accuracy separately from overall verdict accuracy) | |
| **Day 6 (Sep 5)** | Dono milke: fix bugs from accuracy run, write pytest for Judge, Fusion, Reference-match, Structural (YOLO) | |

---

## 🗓️ Week 4 (Sep 7–12) — Frontend + Deploy

| Day | Anil | Disha |
|:---|:---|:---|
| **Day 1 (Sep 7)** | Frontend setup, `LoginPage.jsx`, `services/api.js` | `DashboardPage.jsx` + `NewInspectionPage.jsx` (drag-drop upload) |
| **Day 2 (Sep 8)** | `InspectionDetailPage.jsx` — verdict banner, evidence cards | `ImageCompare.jsx` + `ROIOverlay.jsx` (renders YOLO bounding boxes) |
| **Day 3 (Sep 9)** | Dono milke: connect frontend ↔ backend, integration test | |
| **Day 4 (Sep 10)** | Approve/Override action on report page (replaces full review workflow) | `AnalyticsPage.jsx` + `FraudTrendChart.jsx` + `VendorLocationTable.jsx` |
| **Day 5 (Sep 11)** | Deploy — Vercel (frontend) + Render (backend), env config (NVIDIA NIM + Groq keys as free env vars) | `README.md` update, demo script prep |
| **Day 6 (Sep 12)** | Dono milke: **MVP DONE** 🎉 — final demo rehearsal, quick UI polish pass, accuracy numbers finalized for pitch | |

---

## 📊 Summary

| Phase | Duration | Dates | What |
|:---|:---|:---|:---|
| **Week 1: Foundation** | 6 days | Aug 17–22 | Core setup, models, schemas, auth, base shared services |
| **Week 2: Pipeline A + YOLO** | 6 days | Aug 24–29 | Stages 1–5, 4 evidence agents, YOLO11n fine-tune on own data |
| **Week 3: Pipeline B + Testing** | 6 days | Aug 31–Sep 5 | Stages 6–8, LangGraph wiring, accuracy benchmark |
| **Week 4: Frontend + Deploy** | 6 days | Sep 7–12 | 5 core pages, integration, Vercel + Render deploy |
| **Total** | **4 weeks** | Aug 17 – Sep 12 | **Working MVP, free-tier only, with measured accuracy** |

---

## 👤 Work Split Summary

| Area | Anil | Disha |
|:---|:---|:---|
| **Core Setup** | security, main.py, config | database, exceptions, migrations |
| **Models & Schemas** | user, inspection + auth/inspection schemas | product, evidence + product/report schemas |
| **Routers & Shared** | auth, products, inspections, reports, analytics | evidence_store, llm_client (NVIDIA NIM+Groq), memory |
| **Pipeline Stages** | quality_check, reference_match, roi_scheduler, evidence_fusion, policy_engine | authenticity, evidence_execution, judge |
| **Agents** | base_agent, label, vlm | ocr, structural (+ YOLO fine-tune) |
| **Services** | embedding_service | reporting_service, analytics_service |
| **Frontend** | Login, InspectionDetail, deploy (Vercel/Render) | Dashboard, NewInspection, Analytics, ImageCompare/ROIOverlay |
| **Testing** | pytest suite, workflow wiring | accuracy test set curation, bug fixes |

> **Note:** Har Saturday (Day 6) dono milke code review + integration test karenge.

---

## 🧠 Free-Tier Cheat Sheet (so no one accidentally reaches for a paid key)

| Need | Use | Not |
|:---|:---|:---|
| Text reasoning (Judge) | NVIDIA NIM free tier — DeepSeek-V3.2 (fallback: Groq — Llama 3.3 70B) | Paid OpenAI/Anthropic API |
| Vision reasoning (VLM Agent) | NVIDIA NIM free tier — Nemotron Nano Omni (fallback: Groq — Llama 4 Scout) | Paid GPT-4V / Claude vision |
| Image embeddings | Open-source CLIP, local | Paid embedding APIs |
| Object detection (Structural Agent) | YOLO11n, self fine-tuned, AGPL-3.0 (free — repo stays open-source) | Ultralytics Enterprise license |
| Dataset annotation | Roboflow free tier | Paid annotation tools |
| Model training | Google Colab free GPU (T4) | Paid Colab Pro / cloud GPU |
| OCR | EasyOCR, local | Paid OCR APIs |

---

## 📈 Progress Tracker

| Week | Day | Anil | Disha |
|:-----|:----|:-----|:------|
| W1 | D1 | | |
| W1 | D2 | | |
| W1 | D3 | | |
| W1 | D4 | | |
| W1 | D5 | | |
| W1 | D6 | | |
| W2 | D1 | | |
| W2 | D2 | | |
| W2 | D3 | | |
| W2 | D4 | | |
| W2 | D5 | | |
| W2 | D6 | | |
| W3 | D1 | | |
| W3 | D2 | | |
| W3 | D3 | | |
| W3 | D4 | | |
| W3 | D5 | | |
| W3 | D6 | | |
| W4 | D1 | | |
| W4 | D2 | | |
| W4 | D3 | | |
| W4 | D4 | | |
| W4 | D5 | | |
| W4 | D6 | | |