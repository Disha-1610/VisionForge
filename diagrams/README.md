# 📊 VisionForge AI — Archify Architecture & Process Diagrams

This directory houses the official suite of **7 interactive, standalone Archify diagrams** representing the production architecture, neural pipelines, telemetry sequences, data movement, and security topology of VisionForge AI.

Each diagram is delivered as a self-contained, interactive HTML application featuring theme switching (dark/light), pan/zoom canvas controls, focus chapters, relationship tracing, and vector export (SVG, PNG, WebP).

---

## 📑 Diagram Index

| # | Diagram Name | Type | Specification | Interactive HTML Viewer | System Scope & Focus |
|:---|:---|:---|:---|:---|:---|
| **01** | [**System Architecture**](01-system-architecture.html) | `architecture` | [`01-system-architecture.json`](01-system-architecture.json) | [`01-system-architecture.html`](01-system-architecture.html) | Complete multi-tier system topology: Operator HUD, FastAPI REST/SSE Gateway, LangGraph 8-stage state machine, local YOLO11n + OpenCV heuristics, PostgreSQL/SQLite persistence, and Groq LPU causal judge. |
| **02** | [**End-to-End Inspection Pipeline**](02-inspection-flow.html) | `workflow` | [`02-inspection-flow.json`](02-inspection-flow.json) | [`02-inspection-flow.html`](02-inspection-flow.html) | Complete 8-stage inspection journey from raw scan upload through 30ms defensive fast-fail gates (S1-S3), localized ROI cropping (S4), parallel agent swarm (S5), Anomaly Max-Pooling (S6), Groq causal judge (S7), deterministic policy (S8), and human review. |
| **03** | [**AI Forensic Agent Architecture**](03-ai-agent-architecture.html) | `architecture` | [`03-ai-agent-architecture.json`](03-ai-agent-architecture.json) | [`03-ai-agent-architecture.html`](03-ai-agent-architecture.html) | Internal mechanics of the 4 specialized agents (OCR, Label, Structural YOLO11n + SSIM, VLM), dual-provider VLM failover (Groq Qwen ↔ Gemini 3.5 Flash odd/even load balancing), and immutable evidence card storage. |
| **04** | [**Golden Reference & YOLO Verification**](04-golden-reference-yolo.html) | `workflow` | [`04-golden-reference-yolo.json`](04-golden-reference-yolo.json) | [`04-golden-reference-yolo.html`](04-golden-reference-yolo.html) | Blueprint retrieval via Open_CLIP ViT-B/32 512-dim visual embeddings & FAISS index, Stage 4 localized ROI cropping ($8\times$–$12\times$ scale normalization), dual YOLO11n component inference, and Hungarian bipartite delta matching. |
| **05** | [**Frontend ↔ Backend Sequence**](05-frontend-backend-sequence.html) | `sequence` | [`05-frontend-backend-sequence.json`](05-frontend-backend-sequence.json) | [`05-frontend-backend-sequence.html`](05-frontend-backend-sequence.html) | Asynchronous HTTP interaction timeline: `POST /api/v1/inspections` fast 201 acknowledgment, real-time Server-Sent Events (`GET /api/v1/inspections/{id}/stream`), live HUD stage updates, and forensic PDF download (`GET .../report/pdf`). |
| **06** | [**Evidence Data Movement**](06-evidence-dataflow.html) | `dataflow` | [`06-evidence-dataflow.json`](06-evidence-dataflow.json) | [`06-evidence-dataflow.html`](06-evidence-dataflow.html) | Data payload transformations: 4K RGB tensors decomposed into localized sub-region tensors, serialized into normalized JSON evidence cards, aggregated via Anomaly Max-Pooling math, and rendered into SHA-256 signed PDF certificates. |
| **07** | [**Data & Security Architecture**](07-data-security-architecture.html) | `architecture` | [`07-data-security-architecture.json`](07-data-security-architecture.json) | [`07-data-security-architecture.html`](07-data-security-architecture.html) | Zero-trust security model: OAuth2 password bearer JWT authentication with proactive token rotation, RBAC route guards (operator vs. admin), SQLAlchemy 2.0 relational models with foreign-key cascades, and append-only evidence logs. |

---

## 🚀 How to View the Diagrams

Each `.html` file is completely standalone with inline SVGs and bundled interactive scripts. No internet connection or web server is required.

### Option 1: Direct Browser Launch
Double-click any `.html` file in your file explorer, or launch via command line:
```bash
# On Windows PowerShell
Start-Process diagrams/01-system-architecture.html
Start-Process diagrams/02-inspection-flow.html
Start-Process diagrams/03-ai-agent-architecture.html
Start-Process diagrams/04-golden-reference-yolo.html
Start-Process diagrams/05-frontend-backend-sequence.html
Start-Process diagrams/06-evidence-dataflow.html
Start-Process diagrams/07-data-security-architecture.html
```

### Option 2: Live Local Preview via Archify
To inspect or live-edit any diagram specification:
```bash
node C:\Users\ANIL\.gemini\config\skills\archify\bin\archify.mjs preview <type> diagrams/<name>.json diagrams/<name>.html --quality showcase
```

---

## 🛠️ Verification & Quality Standard

All 7 diagrams have been formally verified with Archify's strict **Showcase Quality Profile** reporting:
- ✅ **9 of 9 deterministic artifact checks passed** (`single_svg`, `finite_svg`, `orthogonal_arrows`, `label_route_clearance`, `relationship_crossings`, `relationship_corridors`, `container_border_runs`, `route_rhythm`, `legend_clearance`)
- ✅ **0 composition errors** and **0 composition warnings**
- ✅ **Truthful alignment** with the actual VisionForge AI repository implementation and API contracts
