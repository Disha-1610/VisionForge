# VeriVision AI — MVP Pipeline Architecture

> Scoped MVP — 8 stages (Disha's split of ROI Scheduler vs. Evidence Execution adopted), 4 evidence agents, every tool/model on the free tier. Focus this round: **pipeline accuracy**, not feature breadth. The full 14-stage design remains the long-term roadmap.

---

## 1. Full System Diagram

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                                FRONTEND                                        │
├───────────────────────────────────────────────────────────────────────────────┤
│ • Authentication                                                                │
│ • Image Upload                                                                  │
│ • Inspection Dashboard                                                          │
│ • Explainable Fraud Report UI (with Approve/Override action)                   │
│ • Analytics Dashboard (vendor/location fraud breakdown, monthly trend)         │
└───────────────────────────────┬─────────────────────────────────────────────────┘
                                │ REST API
                                ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND - BUSINESS LOGIC                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  EXECUTION PIPELINE  (every model below is free-tier or fully local)          │
│                                                                                 │
│  IMAGE INPUT (Single / Multi-angle Images)                                    │
│                 │                                                              │
│                 ▼                                                              │
│  1. Image Intake & Quality Validation        — OpenCV (local)                 │
│                 ▼                                                              │
│  2. Image Authenticity Verification          — OpenCV + Pillow (local)        │
│                 ▼                                                              │
│  3. Reference Intelligence                   — CLIP + FAISS (local)           │
│                 ▼                                                              │
│  4. ROI Scheduler                            — pure logic (no model)          │
│                 ▼                                                              │
│  5. Evidence Execution — Specialized Agents  — EasyOCR, OpenCV,               │
│                                                  YOLO11n, NVIDIA NIM free VLM  │
│                 ▼                                                              │
│  6. Multi-View Evidence Fusion               — pure logic (no model)          │
│                 ▼                                                              │
│  7. AI Judge (verdict + root-cause reasoning) — NVIDIA NIM free-tier LLM      │
│                 ▼                                                              │
│  8. Policy Engine + Explainable Report        — code + ReportLab (local)      │
│                 ▼                                                              │
│        Human Approve / Override (single action, not a queue)                  │
│                                                                                 │
├───────────────────────────────────────────────────────────────────────────────┤
│  SHARED SERVICES  (every agent can Read / Write / Query these, anytime)       │
│                                                                                 │
│ • Working Memory        • Evidence Store        • LLM Client                   │
├───────────────────────────────────────────────────────────────────────────────┤
│  BUSINESS SERVICES                                                              │
│                                                                                 │
│ • Reporting Service (explainable report generation)                            │
│ • Analytics Service (vendor/location/monthly fraud aggregation)                │
└───────────────────────────────┬─────────────────────────────────────────────────┘
                                ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND - DATA LAYER                                 │
├───────────────────────────────────────────────────────────────────────────────┤
│ Golden Reference Repository                                                    │
│   ├── Image Storage      (actual golden image files)                          │
│   ├── Metadata Database  (info about every golden image)                      │
│   └── FAISS Index        (embeddings only, for similarity search)             │
│                                                                                 │
│ • Inspection History      (tagged with vendor + location at intake)           │
│ • Generated Reports                                                           │
│ • YOLO Weights            (component_detector.pt — fine-tuned, self-owned)    │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Tooling Stack — Free-Tier Only

Every stage below runs on a free-tier API or a fully local/open-source library. No paid keys required anywhere in this pipeline.

| Stage | Tool / Model | Cost | Notes |
|:---|:---|:---|:---|
| 1. Quality Validation | OpenCV (Laplacian blur, brightness histogram) | Free — local | No API, no rate limit |
| 2. Authenticity Verification | OpenCV + Pillow (ELA, EXIF via `exifread`) | Free — local | No API, no rate limit |
| 3. Reference Intelligence | CLIP (`open-clip-torch` or HF `clip-vit-base-patch32`) + FAISS | Free — local | Runs on CPU fine for MVP scale |
| 4. ROI Scheduler | Pure Python logic | Free | No model needed |
| 5a. OCR Agent | Primary: **PaddleOCR**, Secondary: **EasyOCR** | Free — local, open-source | High precision on tiny/stamped industrial serial numbers |
| 5b. Label Agent | OpenCV `cv2.matchTemplate` | Free — local | |
| 5c. Structural Agent | OpenCV SSIM + **YOLO11n (Ultralytics)** | Free — AGPL-3.0 | See Section 4, Stage 5 for detail |
| 5d. VLM Agent | Primary: NVIDIA NIM (**Nemotron Nano Omni** — `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`, verified)<br>Secondary: Groq (**Qwen 3.6 27B Vision** — `qwen/qwen3.6-27b`, verified) | Free — rate-limited | Primary on NVIDIA NIM, auto-fallback to Groq Qwen 3.6 27B if NIM is rate-limited or down |
| 6. Evidence Fusion | Pure math/logic | Free | No model needed |
| 7. AI Judge | Primary: Groq (**GPT-OSS 20B** — `openai/gpt-oss-20b`, verified active & ultra-fast)<br>Secondary: NVIDIA NIM (**Nemotron Super 120B** — `nvidia/nemotron-3-super-120b-a12b`, verified reasoning) | Free — rate-limited | Primary on Groq for ultra-fast response, auto-fallback to NVIDIA NIM Nemotron Super 120B |
| 8. Policy + Report | Code + ReportLab (PDF) | Free — local | |
| Analytics | SQL aggregation (GROUP BY) | Free | No model needed |

**Two things to design around, since they're free:**
- **Rate limits, not cost.** Groq & NVIDIA NIM free tiers are request-based. The `llm_client.py` wrapper retries with backoff and automatically handles primary/secondary failover (Groq `openai/gpt-oss-20b` primary for AI Judge, NVIDIA NIM `nvidia/nemotron-3-super-120b-a12b` fallback; NVIDIA NIM `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` primary for VLM Agent, Groq `qwen/qwen3.6-27b` fallback).
- **NVIDIA's trial terms** allow them to use prompts/images sent to the free endpoint to improve their models, and explicitly exclude production use. Fine for a hackathon/portfolio demo — just don't treat it as a production data-handling guarantee later.
- **YOLO's AGPL-3.0 license requires the project to stay open-source** if you use it without an Ultralytics Enterprise license. Since this is already an open-source GitHub portfolio project, this is a non-issue — just don't fork it into a closed-source product later without revisiting the license.

---

## 3. Component Classification

| Component | Pipeline Stage? | Shared Service? | Why? |
| --- | --- | --- | --- |
| Working Memory | ❌ No | ✅ Yes | Every stage reads/writes temporary inspection data. |
| Evidence Store | ❌ No | ✅ Yes | Evidence agents continuously store results; later stages read them. |
| LLM Client | ❌ No | ✅ Yes | Any stage (Judge, VLM Agent) can call it — not tied to one step. |

> **Deferred to roadmap:** Tool Registry and Fraud Knowledge Graph — useful at scale, not required to prove the pipeline works.

### Layer Breakdown

**A. Deterministic Processing Layer** (plain code / CV frameworks — no AI reasoning)
- Image Intake & Quality Validation — Blur Detection, Lighting Check, Resolution Check, Format Validation
- Image Authenticity Verification — ELA, EXIF Validation, basic tamper checks
- Reference Intelligence — CLIP Embeddings, FAISS Search, Golden Image Selection, ROI Template Loading
- ROI Scheduler — ROI Type → Agent mapping, parallel dispatch planning
- Multi-View Evidence Fusion — Merge detections, cross-angle matching, confidence aggregation
- Policy Engine — configurable-in-code rules mapping verdict → action

**B. AI Agent Layer**
- Specialized Evidence Agents — OCR, Label, **Structural (SSIM + YOLO11n object detection)**, VLM (4, down from 9)
- AI Judge — single LLM reasoning pass: resolves evidence, decides verdict, explains root cause (absorbs what were separately Debate + Causal Reasoning + Judge stages in the full design)

**C. Shared Runtime Services**
- Working Memory, Evidence Store, LLM Client

**D. Business Services**
- Reporting Service (Human Review is a single UI action on the report, not a separate service/queue)
- Analytics Service (vendor/location fraud breakdown, monthly trend)

---

## 4. Pipeline Stages

### 1. Image Intake & Quality Validation
*(Not an agent — fixed CV algorithms)*
**Tool:** OpenCV — free, local, no rate limit.

**Rules**
- Check whether every uploaded image is blurry (Laplacian variance) or has insufficient lighting (brightness histogram).
- Verify image detail is sufficient for reliable inspection (serial numbers, labels, connectors, scratches must be visible).
- Accept only supported formats (JPG, JPEG, PNG); reject corrupted files immediately.
- Detect duplicate images and ignore repeated uploads.
- Resize while preserving aspect ratio; crop excessive background without removing the object.
- If any check fails: stop the inspection, show the reason, suggest a retake.
- Continue only if all checks pass.

---

### 2. Image Authenticity Verification
*(Not an agent — deterministic image forensics)*
**Tool:** OpenCV + Pillow (ELA, EXIF) — free, local.

**Rules**
- Run Error Level Analysis (ELA) to check whether the image has been edited.
- Validate EXIF metadata; detect screenshots.
- Check image noise consistency and basic copy-move cloning.
- Generate an authenticity score.
- If authenticity is below the acceptable threshold: flag the case as suspicious, record the reason, continue the inspection while marking authenticity risk (do not hard-block — let the Judge weigh it).

---

### 3. Reference Intelligence
*(Not an agent — embedding search + retrieval)*
**Tool:** CLIP (open-source, local) + FAISS (open-source, local) — free, no API.

**Rules**
- Generate a CLIP embedding for every uploaded image.
- Search the reference database for the most similar golden image, restricted to the detected Part ID.
- Select the highest similarity match above the minimum similarity threshold; reject pairing if below it.
- Verify uploaded and reference images represent the same viewing angle.
- Load the correct ROI template for the matched part (regions, expected components, checkpoints).
- If no suitable reference exists: mark the case for manual review.

---

### 4. ROI Scheduler
*(Not an agent — pure scheduling logic, split out from Evidence Execution)*
**Tool:** None — pure Python.

**Rules**
- Read the ROI template for the matched golden reference.
- Identify the inspection type required for each ROI (Text, Label, Structural, general visual).
- Assign each ROI to exactly one of the 4 agents; route the same agent to multiple ROIs instead of duplicating.
- Group same-type ROIs into a single execution batch.
- Prioritize critical ROIs (serial numbers, security labels, QC seals) before non-critical ones.
- Produce an execution plan (ROI → agent mapping) and hand it to Stage 5 — the scheduler itself does not run any model.

```
Input: Golden Image + ROI Template + Inspection Image
        ↓
Read ROI Template → Map ROI Type → Assigned Agent → Output execution plan
```

| ROI Type | Agent |
|:---|:---|
| Text (serials, part numbers) | OCR Agent |
| Label, seal, logo | Label Agent |
| Component layout, PCB trace, physical structure | Structural Agent |
| General visual anomaly, anything not covered above | VLM Agent |

---

### 5. Evidence Execution — Specialized Agents
*(Agent stage — runs the execution plan produced by Stage 4, dispatches to the 4 agents in parallel)*

**Execution rules**
- Run independent agents in parallel where possible; respect the priority order from the scheduler.
- Crop the exact bounding box regions defined in the ROI template from both the **Golden Reference Image** and **Inspection Image**.
- Distribute only the cropped **Golden ROI** and **Inspection ROI** image pair to the assigned agent for comparison (e.g., OCR Agent receives only the small cropped text ROI, not the full image).
- Each agent is responsible for only its inspection domain and must not modify another agent's findings.
- Every agent returns: Evidence, Confidence, ROI, Explanation, Processing time.
- Agents must report failure rather than fabricate results; confidence values follow a consistent scale across agents.
- Store all findings in the Evidence Store.

**5a. OCR Agent** — Primary: **PaddleOCR** (industrial-grade precision on tiny/stamped serials & part numbers), Secondary: **EasyOCR** (lightweight fallback). Reads serials/part numbers from cropped text ROI, diffs against expected text.

**5b. Label Agent** — `cv2.matchTemplate` (free, local). Compares label/seal/logo regions against the golden template.

**5c. Structural Agent — where YOLO goes** — `OpenCV SSIM` + **YOLO11n (Ultralytics, free under AGPL-3.0)**.

This is the stage where object-level detection adds real accuracy, not just novelty:
- SSIM alone gives a single holistic similarity number for a region — it's sensitive to lighting and minor alignment shifts, and it can't tell you *what* is different, only *that* something is.
- YOLO adds a structured, per-object signal: it detects and counts individual components (capacitors, connectors, chips) in both the golden ROI and the inspection ROI, and reports **which specific component is missing, extra, or misplaced** — this is both more accurate (object presence/count is a stronger fraud signal than pixel similarity) and more explainable (the Judge and the final report can say "capacitor at position 3 is missing" instead of "structural similarity: 0.71").
- Combine both signals: SSIM catches general structural drift, YOLO catches discrete component-level tampering. Fusion (Stage 6) weighs them together.

**Getting a usable YOLO model without a paid dataset or paid compute:**
1. Annotate 15–20 of your own golden reference images with bounding boxes for the components that matter (capacitors, connectors, chips) — Roboflow's free tier covers annotation for a project this size.
2. Fine-tune `YOLO11n` (the nano variant — smallest, fastest, fits free compute) on that annotated set using a free Google Colab GPU session. A nano model on ~20 images trains in well under an hour.
3. Export the weights to `data/yolo_weights/component_detector.pt` and load them locally in `structural_agent.py` — no inference API, no ongoing cost.
4. Pretrained COCO-weights YOLO won't help here — COCO has no "capacitor" or "connector" class. The fine-tune step is what makes it useful, not the base model.
5. License: AGPL-3.0 is free as long as the repo stays open-source, which it already is.

**5d. VLM Agent** — Primary: NVIDIA NIM **Nemotron Nano Omni** (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`, verified active, 33B omni-modal reasoning, 262K context). Secondary / Fallback: Groq **Qwen 3.6 27B Vision** (`qwen/qwen3.6-27b`, verified active, 27B multimodal reasoning). Catches general visual anomalies the other 3 agents aren't specifically looking for; also the fallback when a region doesn't cleanly map to OCR/Label/Structural. Combined vision+reasoning means it can return a short explanation alongside the detection, not just a raw label.

---

### 6. Multi-View Evidence Fusion
*(Not an agent — mathematical aggregation)*
**Tool:** None — pure logic.

**Rules**
- Combine evidence from all available image angles; merge duplicate findings.
- Increase confidence when multiple angles confirm the same defect; reduce it when evidence conflicts.
- Weigh YOLO's discrete component-level findings alongside SSIM's holistic score from the Structural Agent — don't let one silently override the other.
- Ignore missing angles if they're optional.
- Preserve the original per-detector confidence before fusion.
- Record which angles contributed to each final conclusion.
- Prevent duplicate evidence from artificially inflating confidence.

---

### 7. AI Judge
*(Agent — single reasoning pass; absorbs Debate + Causal Reasoning + Judge from the full design)*
**Tool:** Primary: Groq free tier — **`openai/gpt-oss-20b`** (verified active & ultra-fast). Secondary / Fallback: NVIDIA NIM free tier — **`nvidia/nemotron-3-super-120b-a12b`** (124B MoE high-precision reasoning).

**Rules**
- Read all fused evidence in one context window, including YOLO's specific component-level findings.
- Where evidence conflicts, resolve it directly in the reasoning chain instead of running a multi-round debate — note which evidence was weighted higher and why.
- Build a cause-and-effect explanation connecting anomalies into a coherent fraud scenario; distinguish root cause from secondary effects.
- Reject conclusions unsupported by stored evidence; mark uncertain relationships explicitly.
- Produce one final decision: **Accept / Reject / Review**, with fraud probability, confidence, and category.

Example output:
```
Fraud Probability = 92%
Confidence = 96%
Category = Counterfeit Component
Root Cause = YOLO detected capacitor missing at ROI position 3 (golden: 4 detected, inspection: 3 detected),
             confirmed by SSIM drop (0.71) in the same region
```

> **Why merged:** a full multi-round debate loop is expensive to tune and hard to demo convincingly in a month. One well-prompted reasoning call that shows its work (which evidence it weighted, what it rejected and why) gives ~80% of the explainability value for a fraction of the engineering cost. Multi-agent debate stays on the roadmap for when the agent count and evidence volume actually need it.

---

### 8. Policy Engine + Explainable Report
*(Policy is deterministic code; report generation reads the Judge's output)*
**Tool:** Plain code + ReportLab (PDF) — free, local.

**Policy rules**
- Calculate Fraud Score, Confidence Score, Fraud Category from the Judge's output.
- Classify risk against hardcoded thresholds (configurable in code, not a UI, for MVP).
- Generate one operational action: **Accept, Retake, Quarantine, or Vendor Verification.**

```
if fraud_score > 90:
    quarantine()
elif confidence < 60:
    human_review()
else:
    accept()
```

**Report rules**
- Generate a report after every completed inspection with: Case ID, fraud score, category, evidence per agent (including YOLO's detected/expected component counts), root-cause explanation, recommended action, authenticity verdict.
- Display original images alongside annotated ROI overlays — including YOLO's bounding boxes.
- Show confidence per agent/detector.
- Generate identical reports when replaying stored evidence (reproducibility).

**Human action (not a separate stage)**
- The report page shows a single **Approve / Override** control.
- Any override is recorded against the Case ID with a reviewer comment.
- No separate review queue, dashboard, or escalation workflow for MVP.

---

## 5. Analytics Dashboard (Business Service)

*(Not a pipeline stage — reads from Inspection History after the fact, refreshed whenever the dashboard is opened. Runs independently of the per-inspection pipeline.)*
**Tool:** SQL aggregation — free, no model.

**Data requirement**
- Master `vendors` table (`id`, `name`, `site_name`, `code`) provides a clean predefined dropdown list for the New Inspection form (`GET /vendors`), preventing freeform typing typos.
- Every Inspection record captures `vendor_id` and `location` at intake time.

**Rules**
- **Total Inspections** — count of all inspections in the selected date range.
- **Total Fraud Cases** — count where Judge verdict = Reject or Policy action = Quarantine.
- **Fraud Rate** — fraud cases ÷ total inspections.
- **Vendor Breakdown** — inspections, fraud count, and fraud rate grouped by vendor, sorted by fraud rate descending.
- **Location Breakdown** — same, grouped by location/site.
- **Vendor Component-Risk Breakdown** — breakdown showing which specific fraud category/component (e.g. Counterfeit Capacitors, Label Tampering) each vendor is failing on most frequently (`GROUP BY vendor_id, fraud_category`).
- **Monthly Fraud Trend** — fraud case count per calendar month, for trend charting.
- **Top Offenders** — the single highest-fraud-rate vendor and the single highest-fraud-rate location, surfaced explicitly rather than buried in a sorted table.
- Aggregation runs as direct SQL queries against the `inspections` & `vendors` tables (`GROUP BY vendor_id`, `GROUP BY location`, `GROUP BY month`) — no separate analytics database needed at MVP scale.

**Endpoints**
```
GET /vendors                    → dropdown master list of vendors & sites
GET /analytics/summary          → total inspections, total fraud, fraud rate
GET /analytics/by-vendor        → vendor-wise breakdown, sorted by fraud rate
GET /analytics/by-location      → location-wise breakdown, sorted by fraud rate
GET /analytics/vendor-risk      → vendor x fraud component/category breakdown
GET /analytics/monthly-trend    → fraud count per month
```

**Still deferred (roadmap, not MVP):** detector-level accuracy tracking, human-override rate, tampering-trend-vs-physical-fraud split — these need history across model versions and aren't meaningful until the pipeline has been running a while.

---

## 6. Shared Services

### Working Memory
- One shared memory object per inspection.
- All stages read from and write to it; no duplicated fields across stages.

### Evidence Store
- Stores every agent's result: detector name, confidence, ROI, bounding box (including YOLO detections), timestamp.
- Append-only — never overwrite existing evidence; preserves a complete audit trail for the report.

### LLM Client
- Single wrapper around the chosen provider (chat + vision), used by the VLM Agent and the AI Judge.
- **VLM Agent Model Routing**: Primary NVIDIA NIM (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`, verified), Secondary Groq (`qwen/qwen3.6-27b`, verified).
- **AI Judge Model Routing**: Primary Groq (`openai/gpt-oss-20b`, verified active & sub-second response), Secondary NVIDIA NIM (`nvidia/nemotron-3-super-120b-a12b`, verified 124B MoE reasoning).
- Centralizes retries, timeouts, primary/secondary model failover, and prompt/response logging for debugging accuracy issues.

---

## 7. Golden Reference Repository (Data Layer)

```
Admin
  │
Upload Golden Images
  │
  ▼
Golden Reference Repository
  ├── Store Images     (actual image files)
  ├── Store Metadata   (info about every image)
  └── Build FAISS Index (embeddings only)
```

```
User uploads inspection image
        ↓
Generate embedding → Search FAISS → Retrieve Golden Image + Metadata → AI Agent Layer
```

**Deletion rule:** deleting a golden image must delete the file, its metadata, and its FAISS embedding together — otherwise you get orphan embeddings pointing at nothing.

---

## 8. Deferred to Roadmap (Full 14-Stage Design)

These are real, designed components — just not required to prove the core pipeline works. Cutting them was a scoping decision, not a capability gap:

- **Multi-Agent Debate** — merged into Judge's single reasoning pass for MVP
- **Fraud Memory & Continuous Learning** — permanent storage + similarity search across historical fraud cases
- **Fraud Knowledge Graph** — relationship graph across components, labels, OCR findings
- **Tool Registry** — dynamic capability routing for agents
- **Richer Analytics** — detector accuracy over time, human-override rate, tampering-vs-physical-fraud split (the basic vendor/location/monthly view is now in MVP scope — see Section 5)
- **5 additional evidence agents** — Component, Material, Connector, Manufacturing, Usage (YOLO's component detection now covers a good chunk of what the Component agent would have done)
- **Full human review workflow** — queue, escalation rules, multi-reviewer audit trail
- **YOLO on Label Agent** — extending object detection to seals/logos, once the component detector proves out

---

## 9. MVP Success Metric

The pipeline is considered validated when, on a curated test set of golden-vs-fraud image pairs, it produces:
- A measured precision/recall (not a guess)
- At least one documented failure case with a clear explanation of why the Judge got it wrong — and whether YOLO's component-level evidence helped or was overridden

This number — not stage count — is the artifact that should anchor any explanation of this project.