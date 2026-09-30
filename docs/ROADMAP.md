# VisionForge AI — Strategic Engineering Roadmap

> **Scope:** Development progression of VisionForge AI from current verified baseline to on-premises edge acceleration and factory automation.

---

## 1. Executive Summary & Current State

VisionForge AI is currently operating at **Phase 1 (Production Baseline)**. The system is deployed as an on-premises factory edge server and developer workstation, featuring a verified 8-stage deterministic state machine, fine-tuned hardware object detector, and 100% offline automated test coverage.

| System Dimension | Current Baseline (Phase 1) | Target (Phase 2: Edge Acceleration) |
| :--- | :--- | :--- |
| **Orchestration** | 8-Stage LangGraph state machine | 8-Stage with automated perspective alignment |
| **Component Detection** | Ultralytics YOLO11n (PyTorch CPU/CUDA, 5.2 MB) | TensorRT / ONNX Runtime FP16 (<10ms edge inference) |
| **Camera Ingress** | Browser drag-and-drop & smartphone QR tunnel | Direct GenICam / GigE camera stream (Basler / FLIR) |
| **Reasoning Engine** | Groq LPU + Gemini 2.5 Flash + Local Rule Fallback | Hybrid Cloud + Local Quantized VLM (`Qwen2.5-VL-7B`) |
| **Deployment Target** | Factory Edge PC / Workstation (Windows/Linux) | Industrial Edge Server / NVIDIA Jetson Orin IPC |
| **Test Verification** | **214 passing automated tests** across 23 test modules | Comprehensive CI pipeline with hardware integration tests |

---

## 2. Phase 1: Production Baseline (Completed & Verified)

All capabilities below are implemented, verified in code, and covered by automated tests:

- [x] **8-Stage LangGraph Workflow:** Complete pipeline graph passing structured `WorkingMemory` state with deterministic stage ordering and failure isolation.
- [x] **Defensive Intake Quality Gate:** Laplacian variance blur filter ($>100$) and greyscale exposure bounds ($40 - 220$) fast-failing unreadable photos.
- [x] **Forensic Authenticity Analysis:** Error Level Analysis (ELA), 4x4 grid noise consistency, screenshot detection, and 16x16 cloned block detection.
- [x] **Vector Blueprint Matching:** FAISS index searching pre-indexed reference embeddings (Gemini 3072-dim with OpenCLIP 512-dim local fallback).
- [x] **Micro-ROI Scheduler:** Prioritized batching of micro-regions (Text, Labels, Structures, Visual surfaces) preventing small component scale drift.
- [x] **Specialist Agent Swarm:** Concurrent execution of EasyOCR (text), OpenCV Normalized Cross-Correlation (labels), YOLO11n + SSIM (structures), and VLM surface analysis.
- [x] **Non-Diluting Evidence Fusion:** Weighted anomaly blending ($65\%$ weighted average + $35\%$ worst finding) with $0.75$ critical defect override.
- [x] **Resilient Multi-Model LLM Gateway:** Unified client with Groq LPU primary, Gemini Flash fallback, $0\text{ms}$ fast-fail circuit breaking ($>15\text{s}$ cooldown), and self-healing regex JSON repair.
- [x] **Deterministic Offline Fallback Judge:** 100% offline rule evaluator guaranteeing an actionable verdict even with zero internet connectivity.
- [x] **Industrial Policy Engine:** Deterministic mapping to operational governance (`ACCEPT`, `RETAKE`, `QUARANTINE`, `VENDOR_VERIFICATION`).
- [x] **Audit Reporting:** Defense-grade ReportLab PDF generation with component matrices and printed chain-of-custody sign-off tables.
- [x] **Real-Time Workstation HUD:** React 19 SPA with synchronized dual-image comparator canvas, Server-Sent Events (SSE) telemetry, and mobile tunnel pairing.
- [x] **Test Verification:** 214 tests passing in $\sim 11 - 17$ seconds with zero cloud dependencies.

---

## 3. Phase 2: Edge Acceleration & Hardware Integration (In Progress)

Phase 2 focuses on hardening the on-premises factory edge server, reducing inference latency, and integrating directly with factory camera hardware.

### 2.1 TensorRT & ONNX Runtime Export
* **Current:** YOLO11n runs in native PyTorch (`component_detector.pt`).
* **Goal:** Export the 8-class model to FP16 ONNX and an NVIDIA TensorRT engine.
* **Impact:** Reduces component detection inference time on industrial edge GPUs (such as NVIDIA Jetson Orin or RTX A2000) from $\sim 15 - 25\text{ms}$ down to **sub-8ms**.

### 2.2 Direct Industrial Camera Ingress (GenICam / USB3 / GigE)
* **Current:** Images are uploaded via web browser or smartphone QR tunnel.
* **Goal:** Direct Python SDK bindings for industrial machine vision cameras:
  - **Basler Pylon SDK** (USB 3.0 Vision & GigE Vision)
  - **FLIR Spinnaker SDK** (High-resolution industrial CMOS sensors)
* **Impact:** Eliminates manual upload step. Placing a PCB in the intake jig automatically triggers optical capture and starts the inspection.

### 2.3 Air-Gapped Local VLM (Cleanroom Operation)
* **Current:** Surface inspection and judge reasoning call Groq or Gemini cloud APIs, falling back to deterministic rules if offline.
* **Goal:** Integrate a lightweight, quantized local vision-language model (such as `Qwen2.5-VL-7B` INT4 via Ollama or vLLM) hosted directly on the Edge Server.
* **Impact:** Delivers rich semantic root-cause explanations in high-security, zero-internet cleanroom facilities without external data egress.

### 2.4 Automated Perspective Homography (Anti-Tilt Alignment)
* **Current:** Cropping coordinates assume the board is placed roughly parallel to the camera.
* **Goal:** An automated affine/homography alignment step between Stage 3 (Reference Match) and Stage 4 (ROI Scheduler) using OpenCV feature matching.
* **Impact:** Automatically de-skews and aligns boards placed at slight angles on the inspection tray.

### 2.5 Dedicated Multi-Reviewer Queue
* **Current:** Operators approve or override inspections directly on the detail page.
* **Goal:** A dedicated review queue page with role-based review workflows and SLA tracking for parts held under `VENDOR_VERIFICATION`.

---

## 4. Phase 3: Factory Automation & Enterprise MES (Future Horizon)

Phase 3 connects VisionForge from an inspection workstation into the broader factory automation network.

### 3.1 PLC & Pneumatic Reject Relay
* **Objective:** Direct integration with factory sorting hardware via **OPC-UA**, **Modbus TCP**, or industrial digital I/O relays.
* **Behavior:** When an inspection receives a `QUARANTINE` policy action from Stage 8, the edge server pulses a 24V PLC relay to actuate a pneumatic diverter arm, automatically routing the defective part into a locked quarantine bin.

### 3.2 Enterprise MES & ERP Integration
* **Objective:** Standardized webhook and REST connectors for manufacturing execution systems:
  - **SAP S/4HANA Supply Chain:** Automatic goods receipt block and supplier debit memo trigger.
  - **Siemens Opcenter MES:** Defect lot logging and serial tracking.

### 3.3 Multi-Site Reference Blueprint Mesh
* **Objective:** Centralized catalog management allowing a quality engineering team to publish new Golden Blueprints (images and ROI JSONs) from headquarters, automatically synchronizing FAISS indices across edge servers at worldwide assembly plants.

---

## 5. Summary of Architecture Milestones

```text
┌──────────────────────────────────────┐
│  Phase 1: Production Baseline        │  ◄── COMPLETED & VERIFIED
│  • 8-Stage LangGraph pipeline        │      (214 tests passing, real YOLO11n,
│  • EasyOCR, Template, YOLO, VLM      │       React 19 HUD, ReportLab PDF)
│  • Resilient multi-model gateway     │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  Phase 2: Edge Acceleration          │  ◄── IN PROGRESS / NEAR-TERM
│  • TensorRT FP16 YOLO export         │      (Industrial Edge deployment,
│  • Industrial GigE / Basler ingress  │       local VLM cleanroom option,
│  • Perspective homography alignment  │       de-skewing alignment)
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  Phase 3: Factory Automation         │  ◄── FUTURE HORIZON
│  • PLC / Modbus pneumatic diverter   │      (Conveyor sorting robotics,
│  • SAP / Siemens MES webhooks        │       multi-site blueprint sync)
│  • Enterprise supply chain mesh      │
└──────────────────────────────────────┘
```

---

*Related Documentation:*
- [System Architecture](ARCHITECTURE.md)
- [Edge Deployment Guide](DEPLOYMENT.md)
- [Inspection Pipeline](PIPELINE.md)
