<div align="center">

# 🔬 VisionForge AI

### **Autonomous Industrial Visual Forensics & Multi-Agent Hardware Fraud Detection**

*Stop counterfeit hardware, recycled silicon, and tampered electronics before they reach your customers.*

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Ultralytics YOLO11n](https://img.shields.io/badge/YOLO11n-Custom_Trained_8_Classes-00FFFF?style=flat-square&logo=yolo&logoColor=black)](docs/YOLO_MODEL.md)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)](https://pytorch.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph_8_Stages-FF6F00?style=flat-square&logo=langchain&logoColor=white)](docs/PIPELINE.md)

[![Groq LPU](https://img.shields.io/badge/Groq_LPU-gpt--oss--20b-F55036?style=flat-square&logo=groq&logoColor=white)](https://groq.com)
[![Google Gemini](https://img.shields.io/badge/Gemini_3.5_Flash-Multimodal_VLM-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![FAISS](https://img.shields.io/badge/FAISS-Vector_Search_3072D-00599C?style=flat-square&logo=meta&logoColor=white)](https://github.com/facebookresearch/faiss)
[![Pytest](https://img.shields.io/badge/Pytest-203_Tests_Passing-brightgreen?style=flat-square&logo=pytest&logoColor=white)](docs/TESTING.md)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary_All_Rights_Reserved-red.svg?style=flat-square)](LICENSE)

<br/><br/>

| ⚡ Inspection Speed | 🎯 Detection Accuracy | 🤖 Agent Architecture | 📊 Hardware Dataset | 🧪 Hermetic QA |
| :---: | :---: | :---: | :---: | :---: |
| **&lt; 4.0 Seconds**<br/><sub>Sub-second edge inference</sub> | **98.4% mAP@50**<br/><sub>Custom fine-tuned YOLO11n</sub> | **4 Swarm Agents + Judge**<br/><sub>OCR • Label • Structural • VLM</sub> | **4,448 Images / 59.7k Labels**<br/><sub>Motherboards • Batteries • RAM</sub> | **203 Passing Tests**<br/><sub>100% offline mocking</sub> |

<br/>

**[📖 Problem](#-the-problem--a-story-that-costs-billions)** •
**[💡 Solution](#-the-solution--visionforge-ai)** •
**[⚡ 4s Journey](#-the-journey-of-one-inspection-under-4-seconds)** •
**[🏗️ Architecture](#-system-architecture)** •
**[🔄 8-Stage Pipeline](#-the-8-stage-inspection-pipeline)** •
**[🤖 Agent Swarm](#-specialized-forensic-agent-swarm)** •
**[👁️ YOLO11n Model](#-custom-fine-tuned-yolo11n-detector)** •
**[🛠️ Tech Stack](#-modern-industrial-tech-stack)** •
**[🚀 Quick Start](#-quick-start)** •
**[📚 Docs Hub](#-complete-documentation-hub)**

</div>

---

## 📖 The Problem — A Story That Costs Billions

> *Imagine a Tuesday morning at a global electronics repair hub. A pallet of 500 replacement motherboards arrives from a third-party vendor. They look perfect. The serial stickers are crisp. The packaging is intact. A technician picks one up, installs it in a customer laptop, and ships it out. Two weeks later, the customer calls — the board is dead. It was a counterfeit. One board out of 500. But finding it manually? That would have taken a human inspector 4 hours with a magnifying glass, comparing each board against a reference photo, squinting at serial numbers, checking if a "0" was swapped for an "O".*

> *Now multiply that across 15 repair sites, 50 vendors, and 10,000 parts per month.*

This is not a hypothetical scenario. **This is the multi-billion-dollar reality of global electronics manufacturing and warranty supply chains today.**

### The Numbers That Keep Supply Chain Leaders Awake

| Statistic | Scale & Impact | Source / Benchmark |
|:---|:---:|:---|
| 🌐 **Global Counterfeit Trade** | **$467 Billion** annually | 2.3% of all global imports *(OECD)* |
| ⚡ **Electronics Sector Losses** | **$100+ Billion** per year | Recycled silicon, scraped dies, warranty fraud |
| 🏢 **Supply Chain Infiltration** | **47%** of companies hit | Impacted by counterfeit hardware in the last 2 years |
| 🛡️ **Defense & Aerospace Risk** | Up to **15%** of components | Counterfeit or remarked passives in critical systems |
| 📈 **Hardware Fraud Prevention Market**| **$54.6 Billion** by 2025 | Explosive demand for autonomous inspection tech |

### The Anatomy of Modern Hardware Fraud

Modern counterfeiters do not produce crude fakes. They deploy sophisticated industrial techniques:
- **Altered Serial Numbers & Lot Dates:** Laser-etched warranty strings where characters are subtly swapped — `A00-00` becomes `A00-0O` — concealing expired warranty dates or recycled silicon batches.
- **Harvested Silicon & Desoldered Passives:** Aged chips desoldered from e-waste circuit boards, polished with acid baths, and resold as factory-new components.
- **Ghost Decoupling Capacitors:** Cost-cutting omission of secondary power filter capacitors ($0402$ SMD size) that causes voltage surge blowouts months after purchase.
- **Counterfeit Holographic Seals:** Photocopied QC stamps and non-OEM stickers with microscopic hue shifts that pass a casual human glance but fail under spectral pixel analysis.
- **Industrial Battery Cell Fraud:** 6-cell laptop battery packs containing 4 low-capacity cells and 2 cement-filled dummy weight tubes.

**Manual inspection cannot scale. It cannot be consistent across shifts. And it cannot catch a single altered character in a serial number at 3 AM on a factory night shift.**

The industry needs an AI system that can see what humans miss — **automatically, consistently, and with audit-ready legal evidence.**

---

## 💡 The Solution — VisionForge AI

**VisionForge AI** is an industrial-grade, zero-trust hardware forensic platform. 

Instead of guessing from a single fallible prompt or relying on rigid legacy computer vision, VisionForge coordinates an **8-stage deterministic and AI-powered state machine** compiled with LangGraph:

```text
       DEFENSIVE CV GATES              VECTOR INTELLIGENCE             SPECIALIZED AI AGENTS               CAUSAL ARBITRATION
┌─────────────────────────────┐   ┌───────────────────────────┐   ┌─────────────────────────────┐   ┌───────────────────────────────┐
│ Stage 1: Quality Gate       │   │ Stage 3: Blueprint Match  │   │ Stage 5: Concurrent Swarm   │   │ Stage 7: AI Forensic Judge    │
│ • Laplacian blur (>100)     │   │ • 3072-dim Gemini / CLIP  │   │ • PaddleOCR Lot Verifier    │   │ • Groq LPU (gpt-oss-20b)      │
│ • Exposure bounds (40-220)  ├──►│ • FAISS vector retrieval  ├──►│ • OpenCV Template Matcher   ├──►│ • Causal root-cause reasoning │
│ Stage 2: Forensic ELA Gate  │   │ Stage 4: Priority Queue   │   │ • YOLO11n Component Counter │   │ Stage 8: Policy Engine        │
│ • Compression diff analysis │   │ • Micro-ROI segmentation  │   │ • Gemini/Groq Surface VLM   │   │ • Signed ReportLab PDF        │
└─────────────────────────────┘   └───────────────────────────┘   └─────────────────────────────┘   └───────────────────────────────┘
```

### Core Value Propositions
- ⚡ **Under 4-Second Total Inspection:** Local GPU/CPU execution combined with ultra-fast Groq LPU causal arbitration.
- 🎯 **Sub-Millimeter Anomaly Detection:** Custom fine-tuned **YOLO11n** model trained on 4,448 images detects missing capacitors, stolen ICs, and broken seals down to $12 \times 12$ pixels.
- 🛡️ **Non-Diluting Anomaly Max-Pooling:** A single missing power capacitor is **never** averaged away or diluted by 20 clean resistors.
- 📱 **Dual Intake Modalities:** Instant desktop drag-and-drop or smartphone camera pairing via an automated Cloudflare Quick Tunnel.
- 📄 **Legally Defensible Audit Proof:** Generates cryptographically hashed, timestamped ReportLab PDF audit certificates for warranty chargebacks.

---

## ⚡ The Journey of One Inspection (Under 4 Seconds)

Here is what happens in the system when an operator places a circuit board under the lens:

```mermaid
sequenceDiagram
    autonumber
    participant Op as 👷 Line Operator
    participant HUD as 🖥️ React 18 Workstation
    participant API as ⚡ FastAPI Gateway
    participant Graph as 🔄 LangGraph Engine
    participant Swarm as 🤖 Multi-Agent Swarm
    participant Judge as ⚖️ AI Forensic Judge
    participant PDF as 📄 ReportLab Engine

    Op->>HUD: Ingests 4K Hardware Photograph (Desktop or Smartphone QR)
    HUD->>API: POST /api/v1/inspections (Multipart Upload)
    API-->>HUD: 201 Created (inspection_id returned in 45ms)
    HUD->>API: Subscribes to Server-Sent Events (SSE Telemetry Stream)

    rect rgb(20, 25, 40)
        Note over Graph: 0.0s – 0.2s: Defensive Intake Gates
        Graph->>Graph: Stage 1: Laplacian blur check (142.5 > 100) & Exposure (118 in 40-220)
        Graph->>Graph: Stage 2: Error Level Analysis (ELA) verifies photo was not digitally edited
    end

    rect rgb(25, 35, 50)
        Note over Graph: 0.2s – 0.5s: Blueprint Match & ROI Scheduler
        Graph->>Graph: Stage 3: Generates 3072-dim embedding -> FAISS retrieves Golden Blueprint in 15ms
        Graph->>Graph: Stage 4: Segments board into prioritized micro-ROIs (Text, Labels, Structures)
    end

    rect rgb(30, 45, 60)
        Note over Swarm: 0.5s – 2.5s: Concurrent Multi-Agent Swarm Execution
        par Parallel Execution across Cropped ROIs
            Graph->>Swarm: OCR Agent: Extracts stamped serial numbers (PaddleOCR)
            Graph->>Swarm: Label Agent: Verifies QC hologram stamp geometry (NCC)
            Graph->>Swarm: Structural Agent: Counts capacitors & chips via YOLO11n + SSIM
            Graph->>Swarm: VLM Agent: Analyzes solder joints & burns (50/50 Gemini + Groq)
        end
        Swarm-->>Graph: Emits standardized Evidence Cards with localized bounding boxes
    end

    rect rgb(40, 25, 30)
        Note over Judge,PDF: 2.5s – 3.8s: Causal Arbitration & Audit Generation
        Graph->>Graph: Stage 6: Anomaly Max-Pooling calculates composite fraud probability (0.88)
        Graph->>Judge: Stage 7: Groq LPU (gpt-oss-20b) arbitrates root-cause in 420ms
        Judge-->>Graph: Verdict: REJECT | Reason: "Capacitor C12 missing on 12V power rail"
        Graph->>PDF: Stage 8: Commits immutable evidence & signs PDF audit certificate
    end

    Graph->>HUD: SSE: pipeline_complete (Verdict: REJECT, PDF URL)
    HUD-->>Op: Displays Crimson Alert Banner, Dual-Image Canvas & PDF Download
```

---

## 🏗️ System Architecture

VisionForge AI is decoupled into five distinct, enterprise-grade architectural tiers:

```mermaid
flowchart TD
    subgraph ClientTier["🖥️ Client Workstation Layer"]
        Desktop["React 18 Desktop HUD (localhost:5173)<br/>• Synchronized Dual-Image Canvas<br/>• Real-Time SSE Telemetry Stepper"]
        Mobile["Smartphone Camera Intake<br/>• WebRTC Viewfinder<br/>• Cloudflare Quick Tunnel QR Pairing"]
    end

    subgraph GatewayTier["⚡ API Gateway Layer (FastAPI :8000)"]
        Auth["JWT Dual-Token Security<br/>(30m Access / 7d Refresh / Proactive Timer)"]
        InspectRouter["Inspection Intake & State Router"]
        ProdRouter["Product Blueprint & Catalog Router"]
        ReportRouter["Audit Reports & PDF Stream Router"]
        SSEHub["Server-Sent Events (SSE) Broadcast Hub"]
    end

    subgraph EngineTier["🔄 LangGraph Inspection Pipeline Engine"]
        S1["1. Quality Gate (Laplacian Variance & Exposure)"]
        S2["2. Tamper Gate (Error Level Analysis ELA)"]
        S3["3. Blueprint Match (Dual Embeddings + FAISS)"]
        S4["4. ROI Priority Scheduler (Deterministic Queue)"]
        S5["5. Multi-Agent Swarm (Parallel Dispatch)"]
        S6["6. Anomaly Max-Pooling Fusion (Weighted Formula)"]
        S7["7. AI Forensic Judge (Groq LPU gpt-oss-20b)"]
        S8["8. Policy Engine (Industrial Governance & PDF)"]
    end

    subgraph SwarmTier["🤖 Specialized Forensic Swarm"]
        OCR["🔤 OCR Agent (PaddleOCR / EasyOCR)"]
        LBL["🏷️ Label Agent (OpenCV Template Matcher)"]
        YOLO["🧩 Structural Agent (YOLO11n + SSIM Drift)"]
        VLM["👁️ VLM Agent (50/50 Gemini 3.5 & Groq Qwen)"]
    end

    subgraph StorageTier["💾 Persistence & Vector Intelligence"]
        DB[(SQLAlchemy 2.0 Async<br/>SQLite Dev / PostgreSQL 16+ Prod)]
        FAISS[(FAISS Vector Index<br/>3072-dim Gemini & 512-dim CLIP)]
        Files[(File Storage Volume<br/>Uploads, Golden Images, PDF Certificates)]
    end

    ClientTier -->|REST & Multipart Upload| GatewayTier
    GatewayTier -->|Spawn Async Background Task| EngineTier
    EngineTier -.->|Stream Live Progress Events| SSEHub
    SSEHub -.->|Push Telemetry| ClientTier

    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8
    S3 <--> FAISS
    S5 --> SwarmTier
    SwarmTier --> S6
    S8 --> DB
    S8 --> Files
```

*For an exhaustive breakdown of system boundaries and failure states, read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).*

---

## 🔄 The 8-Stage Inspection Pipeline

```text
STAGE 1          STAGE 2          STAGE 3          STAGE 4          STAGE 5          STAGE 6          STAGE 7          STAGE 8
[Quality]  ──►  [Authenticity] ──► [Reference]  ──►  [Scheduler] ──►   [Swarm]    ──►   [Fusion]   ──►   [Judge]    ──►  [Policy]
Blur/Glare       Forensic ELA      FAISS Match      Micro-ROIs       4 Agents        Max-Pooling      Groq LPU         PDF Sign
```

| Stage | Name | Core Technology | Forensic Role & Capability | Failure / Fast-Fail Behavior |
|:---:|:---|:---|:---|:---|
| **1** | **Quality Gate** | OpenCV Laplacian ($\text{Var}(\nabla^2 I)$) | Rejects blurry photos ($<100$) and extreme glare ($>220$). | Fast-fails in 25ms $\to$ `RETAKE` prompt. |
| **2** | **Authenticity Gate** | Error Level Analysis (ELA) | Detects Photoshop clone-stamping and digital tampering. | Flags digital forgeries $\to$ `QUARANTINE`. |
| **3** | **Reference Match** | Gemini Embed / CLIP + FAISS | Matches hardware against Golden Blueprint in $<15\text{ms}$. | If similarity $<0.75 \to$ `UNKNOWN_HARDWARE`. |
| **4** | **ROI Scheduler** | Python Priority Queue | Segments board into prioritized micro-regions (Text, Seals, Parts). | Sorts safety labels and chips first. |
| **5** | **Evidence Swarm** | OCR, Template, YOLO11n, VLM | Runs 4 domain agents concurrently on localized image crops. | Robust crash containment per agent. |
| **6** | **Evidence Fusion** | Weighted Anomaly Max-Pooling | Fuses findings mathematically: single defect retains full impact. | Prevents dilution of critical missing parts. |
| **7** | **AI Forensic Judge** | Groq LPU (`gpt-oss-20b`) | Synthesizes cards into human-readable causal root-cause in 420ms. | Strict JSON contract with Gemini fallback. |
| **8** | **Policy Engine** | Python Logic + ReportLab | Maps score to operational policy (`ACCEPT`, `RETAKE`, `QUARANTINE`). | Generates signed, tamper-evident PDF. |

*For complete mathematical formulas, state dictionaries, and benchmarks, read [`docs/PIPELINE.md`](docs/PIPELINE.md).*

---

## 🤖 Specialized Forensic Agent Swarm

Rather than asking a single large model to inspect an entire circuit board, VisionForge routes localized crops to specialized micro-agents:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 🔤 OCR AGENT (PaddleOCR / EasyOCR)                                                               │
│ Expected: "STM32F407VGT6 - Lot 2408"  | Read: "STM32F407VGT6 - Lot 1802"                        │
│ Finding: Recycled silicon detected. Batch date code Y1802 (2018) does not match Y2408 (2024).   │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 🏷️ LABEL AGENT (OpenCV Normalized Cross-Correlation)                                             │
│ Target: QC Inspection Holographic Seal & Regulatory FCC/CE Stamps                                │
│ Finding: Seal perimeter shows paper tearing and glue residue. Photocopied non-OEM replacement.   │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 🧩 STRUCTURAL AGENT (Ultralytics YOLO11n + OpenCV SSIM)                                          │
│ Expected: 4 Nichicon Capacitors, 1 IC Chip | Detected: 3 Capacitors, 1 IC Chip                  │
│ Finding: CRITICAL DEFECT: Decoupling filter capacitor C12 is missing from 12V power stage.       │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 👁️ VLM AGENT (Google Gemini 3.5 Flash & Groq Qwen 3.8 Vision)                                    │
│ Target: Microscopic Solder Joints & Substrate Traces                                             │
│ Finding: Irregular flux residue and manual rework scratch marks observed on microcontroller pins. │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ⚖️ AI FORENSIC JUDGE (Groq LPU gpt-oss-20b)                                                      │
│ Arbitration: REJECT (Confidence: 96%) | Category: COMPONENT_HARVESTING                           │
│ Narrative: "Board exhibits multiple signs of counterfeit refurbishing: missing capacitor C12 on │
│ power rail, salvaged microcontroller with mismatched 2018 lot date code, and manual solder flux."│
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

*For base agent contracts, schema definitions, and conflict resolution, read [`docs/AI_AGENTS.md`](docs/AI_AGENTS.md).*

---

## 👁️ Custom Fine-Tuned YOLO11n Detector

VisionForge includes an authoritative, custom fine-tuned **Ultralytics YOLO11n** model (`backend/data/yolo_weights/component_detector.pt`) trained specifically on industrial hardware:

```mermaid
pie title Master Training Dataset Distribution (59,773 Total Annotations)
    "connector" : 27014
    "capacitor" : 14155
    "ic_chip" : 5998
    "battery_cell" : 4065
    "resistor" : 3591
    "screw" : 2932
    "gold_pin_connector" : 1528
    "seal" : 480
```

### The 8 Unified Hardware Classes
1. ⚡ **`capacitor`** (14,155 train labels) — Detects missing filter capacitors and blown cans.
2. 📏 **`resistor`** (3,591 train labels) — Verifies surface-mount pull-up resistors.
3. 🔲 **`ic_chip`** (5,998 train labels) — Identifies microcontrollers, power regulators, and BIOS EEPROMs.
4. 🔌 **`connector`** (27,014 train labels) — Checks PCIe, USB-C, SATA, Molex, and JST headers.
5. 🔩 **`screw`** (2,932 train labels) — Validates assembly retention and grounding screws.
6. 🛡️ **`seal`** (480 train labels) — Checks tamper-evident QC stickers and warranty seals.
7. 🔋 **`battery_cell`** (4,065 train labels) — Counts cylindrical and pouch cells in power packs.
8. 💾 **`gold_pin_connector`** (1,528 train labels) — Inspects RAM contact fingers and PCIe gold pins.

> 🧠 **The Scale Drift Solution:** On a full 4K board image resized to $640 \times 640$, a tiny $0402$ resistor is only $2 \times 1$ pixels. VisionForge's Stage 4 crops localized sub-regions (e.g. $260 \times 180$) *before* YOLO inference, expanding micro-components by **$8\times$ to $12\times$** for reliable detection.

*For model diagnostics, mAP curves, and training metrics, read [`docs/YOLO_MODEL.md`](docs/YOLO_MODEL.md).*  
*For dataset curation and 4,448-image corpus provenance, read [`docs/DATASET.md`](docs/DATASET.md).*

---

## 🛠️ Modern Industrial Tech Stack

VisionForge is built on modern, battle-tested technologies designed for reliability and speed:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       VISIONFORGE TECH STACK                                     │
├───────────────────────┬──────────────────────────────────────────────────────────────────────────┤
│ 🖥️ Frontend Client    │ React 18.3 • Vite 5.4 • Tailwind CSS 3.4 (Cyberpunk Tactical HUD)       │
│                       │ Lucide React Icons • Recharts Analytics • Axios Engine                   │
├───────────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ ⚡ Backend Services   │ FastAPI 0.115 • Python 3.11+ • Uvicorn ASGI • Pydantic v2                │
│                       │ LangGraph StateGraph • AsyncIO Concurrency Swarm                         │
├───────────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ 👁️ Vision & ML Models │ Ultralytics YOLO11n (2.6M params, PyTorch) • OpenCV 4.9                  │
│                       │ PaddleOCR (PP-OCRv4) • EasyOCR • OpenCLIP (ViT-B-32)                     │
├───────────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ 🤖 Cloud Intelligence │ Groq LPU (gpt-oss-20b & Qwen 3.8 27B Vision)                             │
│                       │ Google Gemini 3.5 Flash & Gemini Cloud Embeddings (3072-dim)             │
├───────────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ 💾 Data & Persistence │ SQLAlchemy 2.0 (Async) • SQLite 3 (Dev) / PostgreSQL 16+ (Prod)          │
│                       │ FAISS Vector Database • ReportLab Cryptographic PDF Engine               │
├───────────────────────┼──────────────────────────────────────────────────────────────────────────┤
│ 🚀 Ingress & Ops      │ Cloudflare Quick Tunnel (cloudflared) • Docker Compose • Pytest (203 T)  │
└───────────────────────┴──────────────────────────────────────────────────────────────────────────┘
```

---

## 🏭 Supported Hardware Blueprints

VisionForge comes pre-configured with industrial blueprints ready for testing:

```
📦 Pre-Indexed Golden Blueprints
 ├── 🖥️ Industrial ATX Motherboard V1 (SKU: PCB-MCU-V2)
 │    └── Inspects: STM32 MCU, 8x Nichicon capacitors, PCIe headers, QC seal
 ├── 🔋 Smart Lithium Battery Pack 48V (SKU: BAT-STD-V1)
 │    └── Inspects: 16x LFP cells, BMS balance connector, tamper-evident seal
 └── 💾 ECC DDR4 Server Memory 16GB (SKU: RAM-DDR4-V1)
      └── Inspects: BGA flash IC packages, SPD EEPROM chip, 288-pin gold fingers
```

---

## 🔑 Pre-Seeded Demonstration Accounts

The local database initializes automatically on startup with zero configuration required:

| Account Role | Email Address | Password | Permissions & Authority |
|:---|:---|:---|:---|
| 👑 **System Admin** | `admin@visionforge.ai` | `adminpassword123` | Full control: Upload blueprints, manage vendors, view supplier risk |
| 👷 **Line Operator** | `operator@visionforge.ai` | `operatorpassword123` | Operational access: Run inspections, review evidence, export PDFs |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+** installed and added to PATH
- **Node.js 18+** & **npm** installed
- Free API keys from [Google AI Studio](https://aistudio.google.com/) and [Groq Console](https://console.groq.com/)

---

### Option A: 1-Click Master Launcher (Windows)

VisionForge includes an automated batch orchestrator that verifies environments, clears busy ports, initializes database tables, and launches both servers:

```cmd
# 1. Clone the repository
git clone https://github.com/Disha-1610/VisionForge.git
cd VisionForge

# 2. Launch master runner
.\run_visionforge.bat
```

The script automatically:
1. Clears zombie processes on ports `8000` and `5173`.
2. Creates and activates the backend Python virtual environment.
3. Initializes the SQLite database and seeds default accounts and blueprints.
4. Starts the FastAPI backend on `http://localhost:8000`.
5. Starts the Vite React frontend on `http://localhost:5173`.
6. Opens your browser directly to the dashboard.

---

### Option B: Step-by-Step Manual Setup (macOS / Linux / Windows)

#### 1. Backend Setup
```bash
cd backend

# Create & activate virtual environment
python -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate

# Install Python requirements
pip install -r requirements.txt

# Create environment configuration
cp .env.example .env           # On Windows: copy .env.example .env
```

Edit `backend/.env` and paste your free API keys:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
JWT_SECRET_KEY=generate_a_random_64_character_hex_string
```

Start the FastAPI server (database seeds automatically on startup):
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- **API Endpoint:** `http://localhost:8000`
- **Interactive Swagger Docs:** `http://localhost:8000/docs`

#### 2. Frontend Setup
In a new terminal window:
```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite React workstation
npm run dev
```
- **Workstation HUD:** `http://localhost:5173`

---

## 📁 Repository Directory Structure

```
VisionForge/
├── backend/                       # FastAPI asynchronous backend server
│   ├── app/
│   │   ├── core/                  # Security (JWT, bcrypt), config, database sessions & seeds
│   │   ├── models/                # SQLAlchemy models (User, Vendor, Inspection, Evidence, etc.)
│   │   ├── pipeline/              # 8-stage LangGraph state machine orchestrator
│   │   │   ├── agents/            # Specialized agents (BaseAgent, OCR, Label, Structural, VLM)
│   │   │   ├── stages/            # Stage logic (Quality, Authenticity, Fusion, Judge, Policy)
│   │   │   ├── state.py           # InspectionState TypedDict definition
│   │   │   └── workflow.py        # LangGraph StateGraph builder & execution runner
│   │   ├── routers/               # REST API routers (auth, inspections, products, reports, analytics)
│   │   ├── schemas/               # Pydantic v2 validation schemas
│   │   ├── services/              # High-level services (analytics, embeddings, reporting)
│   │   ├── shared/                # Cross-cutting runtime (evidence_store, llm_client, memory)
│   │   └── utils/                 # Image math (Laplacian blur, ELA, SSIM, ROI templates)
│   ├── data/                      # SQLite database, golden blueprints, and PDF reports
│   └── tests/                     # Hermetic 23-module pytest test suite (203 tests)
├── frontend/                      # React 18 + Vite workstation SPA
│   ├── src/
│   │   ├── components/            # DualImageCanvas, PipelineProgress, EvidenceCards, Modals
│   │   ├── context/               # AuthContext (JWT rotation) & ToastContext
│   │   ├── hooks/                 # usePipelineSSE (real-time telemetry subscriber)
│   │   ├── pages/                 # Dashboard, NewInspection, InspectionDetail, Reports, Analytics
│   │   └── services/              # Axios API client & automatic 401 token refresh queue
│   └── scripts/                   # Cloudflare mobile tunnel bridge (tunnel.mjs)
├── visionforge-dataset/           # 4,448-image micro-electronic hardware training corpus
│   ├── data.yaml                  # Unified 8-class YOLO dataset definition
│   ├── train/                     # 3,393 training images & labels
│   ├── valid/                     # 715 validation images & labels
│   └── test/                      # 340 benchmark test images & labels
├── docs/                          # Comprehensive technical documentation suite (12 guides)
├── run_visionforge.bat            # 1-click Windows master launcher
├── start_backend.bat              # Standalone backend runner
└── start_frontend.bat             # Standalone frontend runner
```

---

## 🧪 Quality Assurance & Test Verification

VisionForge includes an automated test suite of **203 unit and integration tests** across 23 test modules:

```bash
cd backend
pytest -v
```

```text
============================= test session starts =============================
collected 203 items

tests/test_analytics_and_reports.py ........                             [  3%]
tests/test_auth.py .................                                     [ 12%]
tests/test_authenticity.py ........                                      [ 16%]
tests/test_base_agent.py ......                                          [ 19%]
tests/test_embedding_service.py ........                                 [ 23%]
tests/test_evidence_execution.py .......                                 [ 26%]
tests/test_evidence_fusion.py .........                                  [ 31%]
tests/test_evidence_store.py .....                                       [ 33%]
tests/test_image_utils.py ............                                   [ 39%]
tests/test_integration_stages_1_2_3.py .......                           [ 42%]
tests/test_judge_and_policy.py ...........                               [ 48%]
tests/test_label_agent.py ........                                       [ 52%]
tests/test_llm_client.py ........                                        [ 56%]
tests/test_ocr_agent.py ..........                                       [ 61%]
tests/test_pipeline_stages.py ..........                                 [ 66%]
tests/test_roi_scheduler.py ........                                     [ 70%]
tests/test_roi_templates.py .......                                      [ 73%]
tests/test_routers.py .................                                  [ 82%]
tests/test_structural_agent.py ........                                  [ 86%]
tests/test_structural_yolo.py .......                                    [ 89%]
tests/test_vlm_agent.py .........                                        [ 94%]
tests/test_week3_integration.py ......                                   [ 97%]
tests/test_workflow_langgraph.py ......                                  [100%]

============================= 203 passed in 12.45s =============================
```

> 💡 **Zero-Cost Offline Testing:** All cloud models are decoupled using dynamic mock fixtures in `conftest.py`. You can run the entire 203-test suite completely offline without incurring cloud API charges or requiring specialized GPU hardware.

*For complete test methodology and mock fixtures, read [`docs/TESTING.md`](docs/TESTING.md).*

---

## 🛣️ Strategic Engineering Roadmap

- [x] **Phase 1: Production Baseline (Completed & Verified)**
  - 8-stage LangGraph deterministic + AI pipeline
  - Custom fine-tuned 8-class YOLO11n component detector
  - Smartphone QR camera pairing via Cloudflare Quick Tunnel
  - Real-time Server-Sent Events (SSE) telemetry stream
  - AI Forensic Judge causal arbitration on Groq LPU (~420ms)
  - 203 automated test cases with 100% pass rate
- [ ] **Phase 2: Edge Acceleration & Hardware Integration (In Progress)**
  - Export YOLO11n to FP16 NVIDIA TensorRT engine for sub-5ms local inference
  - Python SDK bindings for Basler and FLIR GigE industrial macro cameras
  - Local quantized VLM (`Qwen2.5-VL-7B` INT4 via Ollama/vLLM) for air-gapped cleanrooms
  - Automated affine homography pre-alignment for angled board captures
- [ ] **Phase 3: Enterprise Supply Chain Mesh (Planned)**
  - PLC / OPC-UA industrial relay signaling for pneumatic conveyor reject arms
  - Global federated FAISS vector mesh synchronization across factory receiving bays
  - SAP and Siemens MES webhook integrations for automated supplier payment holds

*For the complete multi-horizon roadmap, read [`docs/ROADMAP.md`](docs/ROADMAP.md).*

---

## 📚 Complete Documentation Hub

VisionForge features an exhaustive 12-document technical specification suite:

| Document | Primary Focus & System Scope |
|:---|:---|
| 📐 [**System Architecture**](docs/ARCHITECTURE.md) | End-to-end system topology, LangGraph state machine, data flows, and trade-offs. |
| 🔄 [**Inspection Pipeline**](docs/PIPELINE.md) | Deep mathematical breakdown of all 8 inspection stages and Anomaly Max-Pooling. |
| 🤖 [**AI & Forensic Agents**](docs/AI_AGENTS.md) | Specifications for OCR, Label, Structural YOLO, and VLM agents + Groq AI Judge. |
| 👁️ [**YOLO11n Model Guide**](docs/YOLO_MODEL.md) | 8-class model architecture, scale drift analysis, loss curves, and diagnostic benchmarks. |
| 📊 [**Dataset Provenance**](docs/DATASET.md) | 4,448-image hardware corpus, data cleaning pipeline, and class distributions. |
| ⚡ [**REST API & Telemetry**](docs/API.md) | OpenAPI schemas, request/response contracts, and Server-Sent Events (SSE) protocol. |
| 🗄️ [**Database Architecture**](docs/DATABASE.md) | SQLAlchemy models, ER diagram, dual SQLite/Postgres portability, and append-only evidence. |
| 🖥️ [**Frontend Workstation HUD**](docs/FRONTEND.md) | React 18 component tree, synchronized canvas, Tailwind HUD tokens, and auth timers. |
| 🚀 [**Deployment & Operations**](docs/DEPLOYMENT.md) | Windows batch scripts, Cloudflare mobile pairing, Docker Compose, and troubleshooting. |
| 🧪 [**Testing & QA Suite**](docs/TESTING.md) | 23 Pytest test modules, hermetic offline mocking, and CI/CD quality gates. |
| 🛡️ [**Security & Threat Model**](docs/SECURITY.md) | Hardware counterfeit threat vectors, JWT rotation, RBAC, and SHA-256 PDF signatures. |
| 🗺️ [**Strategic Roadmap**](docs/ROADMAP.md) | 3-phase progression from MVP to edge TensorRT and factory robotics. |

---

## 🏆 Project Origin — From Dell FutureMind Hackathon Finalist to Production Architecture

VisionForge AI originated from a real-world industrial challenge presented at the **Dell FutureMind AI Hackathon (Grand Final 2026)**, where our team reached the national finals under the project name **VeriVision AI**:

### The Original Hackathon Inception — Team IDEAFORG-E


### Why We Completely Re-Architected the System
The original hackathon proof-of-concept (**VeriVision AI**) demonstrated the feasibility of visual inspection using a 5-agent linear pipeline with Open_CLIP ViT-B/32, ORB homography, full-image SSIM, EasyOCR, and NVIDIA NIM cloud microservices (`meta/llama-3.2-11b-vision-instruct`). However, when tested against realistic factory conditions, the prototype revealed critical engineering bottlenecks:
1. **Severe Latency & Rate Limits:** Relying on monolithic cloud VLM prompts took 8–12 seconds per scan and easily exceeded free-tier cloud quotas.
2. **Scale Drift & Defect Dilution:** Resizing 4K motherboard images to fit VLM context windows washed out tiny 0402-size resistors. Full-image SSIM averages diluted single missing capacitors into false "CLEAN" verdicts.
3. **Brittle Alignment:** Traditional ORB keypoint homography warped under slight camera perspective changes or PCB solder glare.
4. **No Custom Hardware Detector:** The prototype had no dedicated object detection model trained on electronic components.

Following the Grand Final, **Disha Nayak and Anil Pradhan** decided that a billion-dollar supply chain problem deserved more than an ephemeral hackathon script. Over weeks of continuous engineering, we completely discarded the naive prototype and rebuilt **VisionForge AI** from the ground up as an enterprise-grade autonomous forensic workstation.

### Engineering Evolution: Prototype vs. Enterprise Platform

| Architectural Dimension | 🥉 VeriVision AI (Hackathon Grand Final Prototype) | 🚀 VisionForge AI (Production Platform) |
|:---|:---|:---|
| **Pipeline Architecture** | 5-Agent linear state script (`workflow.py`) | **8-Stage LangGraph State Machine** with 30ms defensive fast-fail gates |
| **Component Detection** | None (heuristic CV / full-image VLM) | **Custom YOLO11n** (4,448 images, 8 hardware classes, 98.4% mAP@50) |
| **Micro-Scale Forensics** | Full-image SSIM (diluted anomaly scores) | **Stage 4 Localized ROI Scheduler** ($8\times$–$12\times$ zoom) + **Anomaly Max-Pooling** |
| **Inference Latency** | 8.0 – 12.0 seconds per inspection | **< 4.0 seconds** (sub-second on cached/fast-fail scans) |
| **Reasoning Engine** | Single cloud VLM prompt (`llama-3.2-11b-vision`) | **Groq LPU Causal Judge** (`gpt-oss-20b` in ~420ms) + Dual-Provider Failover |
| **Operator Interface** | Basic review workbench | **Tactical Cyberpunk HUD** (React 18, Dual-Image Canvas, SSE Telemetry) |
| **Persistence & Audit** | Basic SQLite database | **SQLAlchemy 2.0 ORM** (PostgreSQL/SQLite), append-only evidence, PDF certs |
| **Testing & Quality Gates**| 0 automated tests | **23 Pytest Test Modules (203 Passing Tests)** with hermetic offline mocking |

> *"Most hackathon projects die when the demo ends. For us, the Dell FutureMind AI Hackathon was simply Day 1. The original prototype had severe real-world limitations, but the industrial counterfeit problem was real and massive. We spent weeks completely re-architecting the system from the ground up to build what VisionForge AI is today: a production-ready, sub-4-second autonomous hardware forensics workstation."*  
> — **Disha Nayak & Anil Pradhan**

---

## 👥 Authors & Core Contributors

VisionForge AI was redesigned, engineered, and brought to production by:

| Contributor | Primary Focus & Core Responsibilities |
|:---|:---|
| **Disha Nayak** | **Full-Stack Engineering & Data Architecture**<br/>• **Frontend Workstation:** Architected the entire React 18 SPA, Tactical Cyberpunk HUD, Tailwind design system, synchronized dual-image comparator canvas (`DualImageCanvas.jsx`), ROI bounding box overlays, and analytics.<br/>• **Backend & APIs:** Developed complete FastAPI REST API routing (`/auth`, `/inspections`, `/products`, `/vendors`, `/reports`, `/analytics`), dual-token JWT authentication lifecycle with proactive token rotation, and real-time Server-Sent Events (SSE) telemetry.<br/>• **Database & Persistence:** Designed SQLAlchemy 2.0 relational models, dual-dialect PostgreSQL/SQLite compatibility, foreign key integrity constraints, database migrations, and forensic PDF certificate generation. |
| **Anil Pradhan** | **AI/ML, Computer Vision & Pipeline Engineering**<br/>• **Pipeline Architecture:** Designed and implemented the complete 8-stage LangGraph state machine orchestrator (`workflow.py`, `state.py`), 30ms defensive fast-fail gates, and mathematical Anomaly Max-Pooling algorithm.<br/>• **AI/ML & Object Detection:** Curated and cleaned the 4,448-image hardware corpus, unified the 8-class label space, and fine-tuned the Ultralytics YOLO11n component detector (`component_detector.pt`, 5.2 MB).<br/>• **Computer Vision & Agents:** Implemented OpenCV Laplacian blur, Error Level Analysis (ELA) forensics, FAISS vector retrieval, PaddleOCR lot code verifier, and AI Forensic Judge causal reasoning on Groq LPU (`gpt-oss-20b`).<br/>• **Quality Assurance & Testing:** Authored the hermetic 23-module automated Pytest test suite (203 passing tests) with zero-cost offline mocking. |

---

## 📄 License & Intellectual Property

Copyright (c) 2026 **Anil Pradhan & Disha Nayak**. All Rights Reserved.

VisionForge AI is a **proprietary and confidential personal engineering project**. No individual or organization has permission to copy, clone, reproduce, distribute, reverse-engineer, modify, or commercially exploit this software, its trained models, or its datasets without explicit prior written authorization. See **[LICENSE](LICENSE)** for the complete legal terms.

---

<div align="center">
  <sub>Built with ❤️ by Disha Nayak & Anil Pradhan for zero-trust industrial hardware integrity and transparent electronics supply chains.</sub>
</div>
