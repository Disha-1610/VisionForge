# VeriVision AI — MVP Pipeline Architecture

> Scoped-down version of the full 14-stage design — 7 stages, 4 evidence agents. Built to validate the core reasoning pipeline (accuracy + explainability) before investing in scale features. The full 14-stage design remains the long-term roadmap.

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
└───────────────────────────────┬─────────────────────────────────────────────────┘
                                │ REST API
                                ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND - BUSINESS LOGIC                               │
├───────────────────────────────────────────────────────────────────────────────┤
│  EXECUTION PIPELINE                                                            │
│                                                                                 │
│  IMAGE INPUT (Single / Multi-angle Images)                                    │
│                 │                                                              │
│                 ▼                                                              │
│  1. Image Intake & Quality Validation                                          │
│                 ▼                                                              │
│  2. Image Authenticity Verification                                            │
│                 ▼                                                              │
│  3. Reference Intelligence                                                     │
│                 ▼                                                              │
│  4. ROI Scheduler + Specialized Evidence Agents                                │
│                 ▼                                                              │
│  5. Multi-View Evidence Fusion                                                 │
│                 ▼                                                              │
│  6. AI Judge  (verdict + root-cause reasoning, single pass)                    │
│                 ▼                                                              │
│  7. Policy Engine + Explainable Report                                         │
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
│ • Inspection History                                                          │
│ • Generated Reports                                                           │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Classification

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
- Multi-View Evidence Fusion — Merge detections, cross-angle matching, confidence aggregation
- Policy Engine — configurable-in-code rules mapping verdict → action

**B. AI Agent Layer**
- ROI Scheduler — maps ROI Type → assigned agent
- Specialized Evidence Agents — OCR, Label, Structural, VLM (4, down from 9)
- AI Judge — single LLM reasoning pass: resolves evidence, decides verdict, explains root cause (absorbs what were separately Debate + Causal Reasoning + Judge stages in the full design)

**C. Shared Runtime Services**
- Working Memory, Evidence Store, LLM Client

**D. Business Services**
- Reporting Service (Human Review is a single UI action on the report, not a separate service/queue)

---

## 3. Pipeline Stages

### 1. Image Intake & Quality Validation
*(Not an agent — fixed CV algorithms)*

**Rules**
- Check whether every uploaded image is blurry or has insufficient lighting.
- Verify image detail is sufficient for reliable inspection (serial numbers, labels, connectors, scratches must be visible).
- Accept only supported formats (JPG, JPEG, PNG); reject corrupted files immediately.
- Detect duplicate images and ignore repeated uploads.
- Resize while preserving aspect ratio; crop excessive background without removing the object.
- If any check fails: stop the inspection, show the reason, suggest a retake.
- Continue only if all checks pass.

---

### 2. Image Authenticity Verification
*(Not an agent — deterministic image forensics)*

**Rules**
- Run Error Level Analysis (ELA) to check whether the image has been edited.
- Validate EXIF metadata; detect screenshots.
- Check image noise consistency and basic copy-move cloning.
- Generate an authenticity score.
- If authenticity is below the acceptable threshold: flag the case as suspicious, record the reason, continue the inspection while marking authenticity risk (do not hard-block — let the Judge weigh it).

---

### 3. Reference Intelligence
*(Not an agent — embedding search + retrieval)*

**Rules**
- Generate a CLIP embedding for every uploaded image.
- Search the reference database for the most similar golden image, restricted to the detected Part ID.
- Select the highest similarity match above the minimum similarity threshold; reject pairing if below it.
- Verify uploaded and reference images represent the same viewing angle.
- Load the correct ROI template for the matched part (regions, expected components, checkpoints).
- If no suitable reference exists: mark the case for manual review.

---

### 4. ROI Scheduler + Specialized Evidence Agents
*(Scheduler is not an agent; the 4 evidence agents are)*

**Scheduler rules**
- Read the ROI template for the matched golden reference.
- Identify the inspection type required for each ROI (Text, Label, Structural, general visual).
- Assign each ROI to exactly one of the 4 agents; route the same agent to multiple ROIs instead of duplicating.
- Group same-type ROIs into a single execution batch; run independent agents in parallel.
- Prioritize critical ROIs (serial numbers, security labels, QC seals) before non-critical ones.
- Distribute both the **Golden ROI** and the **Inspection ROI** to the assigned agent for comparison.

```
Input: Golden Image + ROI Template + Inspection Image
        ↓
Read ROI Template → Map ROI Type → Assigned Agent → Schedule execution
```

| ROI Type | Agent |
|:---|:---|
| Text (serials, part numbers) | OCR Agent |
| Label, seal, logo | Label Agent |
| Component layout, PCB trace, physical structure | Structural Agent |
| General visual anomaly, anything not covered above | VLM Agent |

**Agent rules (all 4)**
- Each agent is responsible for only its inspection domain and must not modify another agent's findings.
- Every agent returns: Evidence, Confidence, ROI, Explanation, Processing time.
- Agents must report failure rather than fabricate results; confidence values follow a consistent scale across agents.
- Store all findings in the Evidence Store.

---

### 5. Multi-View Evidence Fusion
*(Not an agent — mathematical aggregation)*

**Rules**
- Combine evidence from all available image angles; merge duplicate findings.
- Increase confidence when multiple angles confirm the same defect; reduce it when evidence conflicts.
- Ignore missing angles if they're optional.
- Preserve the original per-detector confidence before fusion.
- Record which angles contributed to each final conclusion.
- Prevent duplicate evidence from artificially inflating confidence.

---

### 6. AI Judge
*(Agent — single reasoning pass; absorbs Debate + Causal Reasoning + Judge from the full design)*

**Rules**
- Read all fused evidence in one context window.
- Where evidence conflicts, resolve it directly in the reasoning chain instead of running a multi-round debate — note which evidence was weighted higher and why.
- Build a cause-and-effect explanation connecting anomalies into a coherent fraud scenario; distinguish root cause from secondary effects.
- Reject conclusions unsupported by stored evidence; mark uncertain relationships explicitly.
- Produce one final decision: **Accept / Reject / Review**, with fraud probability, confidence, and category.

Example output:
```
Fraud Probability = 92%
Confidence = 96%
Category = Counterfeit Label
Root Cause = Label template mismatch (95% match failure) confirmed by OCR serial mismatch
```

> **Why merged:** a full multi-round debate loop is expensive to tune and hard to demo convincingly in a month. One well-prompted reasoning call that shows its work (which evidence it weighted, what it rejected and why) gives ~80% of the explainability value for a fraction of the engineering cost. Multi-agent debate stays on the roadmap for when the agent count and evidence volume actually need it.

---

### 7. Policy Engine + Explainable Report
*(Policy is deterministic code; report generation reads the Judge's output)*

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
- Generate a report after every completed inspection with: Case ID, fraud score, category, evidence per agent, root-cause explanation, recommended action, authenticity verdict.
- Display original images alongside annotated ROI overlays.
- Show confidence per agent/detector.
- Generate identical reports when replaying stored evidence (reproducibility).

**Human action (not a separate stage)**
- The report page shows a single **Approve / Override** control.
- Any override is recorded against the Case ID with a reviewer comment.
- No separate review queue, dashboard, or escalation workflow for MVP.

---

## 4. Shared Services

### Working Memory
- One shared memory object per inspection.
- All stages read from and write to it; no duplicated fields across stages.

### Evidence Store
- Stores every agent's result: detector name, confidence, ROI, bounding box, timestamp.
- Append-only — never overwrite existing evidence; preserves a complete audit trail for the report.

### LLM Client
- Single wrapper around the chosen provider (chat + vision) used by the VLM Agent and the Judge.
- Centralizes retries, timeouts, and prompt/response logging for debugging accuracy issues.

---

## 5. Golden Reference Repository (Data Layer)

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

## 6. Deferred to Roadmap (Full 14-Stage Design)

These are real, designed components — just not required to prove the core pipeline works. Cutting them was a scoping decision, not a capability gap:

- **Multi-Agent Debate** — merged into Judge's single reasoning pass for MVP
- **Fraud Memory & Continuous Learning** — permanent storage + similarity search across historical fraud cases
- **Fraud Knowledge Graph** — relationship graph across components, labels, OCR findings
- **Tool Registry** — dynamic capability routing for agents
- **Analytics Dashboard** — fraud trends, vendor risk, detector accuracy over time
- **5 additional evidence agents** — Component, Material, Connector, Manufacturing, Usage
- **Full human review workflow** — queue, escalation rules, multi-reviewer audit trail

---

## 7. MVP Success Metric

The pipeline is considered validated when, on a curated test set of golden-vs-fraud image pairs, it produces:
- A measured precision/recall (not a guess)
- At least one documented failure case with a clear explanation of why the Judge got it wrong

This number — not stage count — is the artifact that should anchor any explanation of this project.