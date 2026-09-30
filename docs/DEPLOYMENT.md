# VisionForge AI — Industrial Edge Deployment Guide

> **Scope:** On-premises factory edge server and industrial workstation deployment for VisionForge AI.
> Explains hardware specs, factory floor network topology, service daemons, reverse proxy setup, and air-gapped offline operation.

---

## Table of Contents

1. [Why Edge Server Deployment?](#1-why-edge-server-deployment)
2. [Factory Floor Edge Architecture](#2-factory-floor-edge-architecture)
3. [Edge Hardware Specifications](#3-edge-hardware-specifications)
4. [Deployment Modes](#4-deployment-modes)
   - [Mode A: Production Edge Server (Linux / Ubuntu)](#mode-a-production-edge-server-linux--ubuntu)
   - [Mode B: Industrial PC (Windows 10/11 IoT or Enterprise)](#mode-b-industrial-pc-windows-1011-iot-or-enterprise)
   - [Mode C: Developer Bench Testing](#mode-c-developer-bench-testing)
5. [Reverse Proxy & SSE Streaming (Nginx)](#5-reverse-proxy--sse-streaming-nginx)
6. [Air-Gapped / Offline Cleanroom Mode](#6-air-gapped--offline-cleanroom-mode)
7. [Environment Configuration Reference](#7-environment-configuration-reference)
8. [Edge Storage & Data Persistence](#8-edge-storage--data-persistence)
9. [Troubleshooting Edge Deployments](#9-troubleshooting-edge-deployments)

---

## 1. Why Edge Server Deployment?

In real-world manufacturing plants, receiving docks, and electronics repair facilities, deploying VisionForge AI on an **On-Premises Edge Server or Industrial PC (IPC)** is preferred over a pure public-cloud deployment for four critical reasons:

| Edge Advantage | Factory Reality |
| :--- | :--- |
| ⚡ **Sub-Second Image Transfer** | 4K industrial board photographs are 20 MB to 40 MB each. Uploading these over public internet adds 5 to 10 seconds of network lag. On a factory Gigabit LAN, local transfer takes **under 50 milliseconds**. |
| 🛡️ **Hardware IP & Data Privacy** | Pre-production prototypes, unreleased motherboard revisions, and defense-grade electronics cannot be transmitted outside the factory firewall. Edge deployment ensures photos never leave the facility. |
| 🔌 **Air-Gapped Resiliency** | If factory internet connectivity drops, inspections **must not stop**. The local edge server runs YOLO11n, OpenCV, EasyOCR, and deterministic fallback logic 100% offline. |
| 📷 **Industrial Hardware Ingress** | Industrial macro cameras (Basler, FLIR, IDS) connect directly to the edge server via USB 3.0 Vision or dedicated GigE network ports. |

---

## 2. Factory Floor Edge Architecture

The edge server sits inside the local factory facility network (LAN), serving inspection terminals, operator tablets, and camera benches:

```text
       INSPECTION BENCH                               FACTORY ON-PREMISES EDGE SERVER
┌───────────────────────────────┐              ┌────────────────────────────────────────────────────────┐
│  Industrial Camera / Mobile   │              │  Reverse Proxy (Nginx / Caddy)                         │
│  Intake Workstation           │              │  • Port 80 / 443 (Local HTTPS)                         │
│  (Desktop Browser or Phone)   │              │  • Serves Pre-built React 19 Frontend SPA              │
└──────────────┬────────────────┘              │  • Proxies /api/v1 to Uvicorn (Buffering Off for SSE)  │
               │                               └──────────────────────────┬─────────────────────────────┘
               │ Local Gigabit LAN                                        │
               ▼                                                          ▼
┌───────────────────────────────┐              ┌────────────────────────────────────────────────────────┐
│  Operator Web Interface       │              │  FastAPI Application Daemon (Uvicorn Async)           │
│  http://192.168.1.50:5173     │◄────────────►│  • 8-Stage LangGraph Inspection Pipeline               │
│  (Real-Time SSE Telemetry)    │              │  • Local YOLO11n GPU/CPU Inference (component_detector)│
└───────────────────────────────┘              │  • Local OpenCV / ELA / EasyOCR Engines                │
                                               │  • Local FAISS Vector Index (Golden Blueprints)        │
                                               │  • Local SQLite / PostgreSQL Relational Database       │
                                               └──────────────────────────┬─────────────────────────────┘
                                                                          │ (Optional outbound egress)
                                                                          ▼
                                               ┌────────────────────────────────────────────────────────┐
                                               │  External Cloud LLM Gateway (Optional)                 │
                                               │  • Groq LPU (gpt-oss-20b) for text reasoning           │
                                               │  • Google Gemini 2.5 Flash for high-level VLM          │
                                               │  *Falls back automatically to local rules if offline*   │
                                               └────────────────────────────────────────────────────────┘
```

---

## 3. Edge Hardware Specifications

Depending on inspection volume and speed requirements, choose the appropriate hardware tier:

| Component | Minimum Specification (Standard Line) | Recommended Specification (High-Throughput) |
| :--- | :--- | :--- |
| **Processor** | Intel Core i5 / AMD Ryzen 5 (6 cores, AVX2) | Intel Core i7 / Xeon E-2300 or AMD Ryzen 7 (8+ cores) |
| **Memory (RAM)** | 16 GB DDR4 | 32 GB DDR4 / DDR5 |
| **Graphics (GPU)** | Integrated Intel UHD / AMD Vega (CPU inference) | NVIDIA RTX 3060 / 4060 / A2000 (6 GB+ VRAM, CUDA) |
| **Storage** | 256 GB NVMe SSD | 1 TB NVMe SSD (PCIe Gen 4) |
| **Networking** | 1x Gigabit Ethernet (1 GbE) | 2x Gigabit Ethernet (One for LAN, one for GigE Camera) |
| **Operating System** | Ubuntu Server 22.04 LTS or Windows 10/11 IoT | Ubuntu Server 24.04 LTS or Windows Server 2022 |

---

## 4. Deployment Modes

### Mode A: Production Edge Server (Linux / Ubuntu)

This is the standard deployment on an on-premises Linux server or rackmount edge node.

#### Step 1: Clone and Set Up System Dependencies
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git nginx libgl1 libglib2.0-0
git clone https://github.com/Disha-1610/VisionForge.git /opt/visionforge
cd /opt/visionforge
```

#### Step 2: Build Python Virtual Environment
```bash
cd /opt/visionforge/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 3: Configure Environment Variables
```bash
cp .env.example .env
nano .env
```
Ensure the following key settings are set:
```ini
ENVIRONMENT=production
DEBUG=False
JWT_SECRET_KEY=generate_a_secure_64_character_hex_key
DATABASE_URL=sqlite+aiosqlite:///data/visionforge.db
# Or PostgreSQL: postgresql+asyncpg://user:pass@localhost:5432/visionforge
```

#### Step 4: Build Frontend Production Assets
```bash
cd /opt/visionforge/frontend
npm install
npm run build
# Built static files are generated in /opt/visionforge/frontend/dist
```

#### Step 5: Configure Systemd Daemon Service
Create `/etc/systemd/system/visionforge.service`:
```ini
[Unit]
Description=VisionForge AI Inspection Engine
After=network.target

[Service]
Type=simple
User=visionforge
WorkingDirectory=/opt/visionforge/backend
ExecStart=/opt/visionforge/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
EnvironmentFile=/opt/visionforge/backend/.env

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable visionforge
sudo systemctl start visionforge
```

---

### Mode B: Industrial PC (Windows 10/11 IoT or Enterprise)

For factory workstations running industrial Windows:

1. **Prerequisites:** Install Python 3.11+, Node.js 20.19+, and Git.
2. **1-Click Factory Master Launcher:**
   Double-click or run from PowerShell:
   ```cmd
   cd C:\VisionForge
   run_visionforge.bat
   ```
   This script:
   - Frees busy ports (`8000`, `5173`).
   - Checks the Python and Node environments.
   - Starts the FastAPI backend daemon.
   - Starts the Vite web client.
   - Launches the factory dashboard automatically in the default browser.

3. **Background Daemon with NSSM (Optional Windows Service):**
   To run VisionForge automatically when the Industrial PC boots:
   ```powershell
   # Install backend as a Windows service using NSSM
   nssm install VisionForgeBackend "C:\VisionForge\backend\venv\Scripts\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"
   nssm set VisionForgeBackend AppDirectory "C:\VisionForge\backend"
   nssm start VisionForgeBackend
   ```

---

### Mode C: Developer Bench Testing

For offline lab verification or bench testing:
```bash
# Terminal 1: Backend
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`.

---

## 5. Reverse Proxy & SSE Streaming (Nginx)

When serving multiple operator tablets and inspection terminals on the factory LAN, place Nginx in front of VisionForge.

> [!IMPORTANT]
> VisionForge uses **Server-Sent Events (SSE)** on `GET /api/v1/inspections/{id}/events` for live progress streaming. Nginx buffering **must be disabled** for this endpoint, otherwise progress events will be held up until the stream closes.

Here is the production Nginx site configuration:

```nginx
server {
    listen 80;
    server_name 192.168.1.50; # Factory LAN IP

    # 1. Serve React Frontend SPA
    root /opt/visionforge/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # 2. Proxy REST API Requests
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 3. Critical: SSE Real-Time Telemetry Stream
    location /api/v1/inspections/*/events {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        
        # Disable buffering for live events
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
        
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    # 4. Upload Limits (Allow high-resolution 4K board images)
    client_max_body_size 50M;
}
```

---

## 6. Air-Gapped / Offline Cleanroom Mode

Many high-security manufacturing lines have zero external internet access. VisionForge is designed to run in a **completely air-gapped configuration**:

1. **Local Object Detection:** The fine-tuned YOLO11n weights (`backend/data/yolo_weights/component_detector.pt`, 5.2 MB) run locally using PyTorch and CPU/CUDA.
2. **Local Vector Search:** The FAISS vector database searches known-good blueprints on disk without connecting to any cloud API.
3. **Deterministic Forensic Judge:** When `GEMINI_API_KEY` and `GROQ_API_KEY` are empty or internet is blocked, the AI Judge stage automatically executes its deterministic rule evaluator in `backend/app/pipeline/stages/judge.py`:
   - Inspects component count differences (missing/extra).
   - Inspects OCR serial text differences.
   - Evaluates composite fraud probability.
   - Generates audit-ready root-cause explanations and recommendations locally.
4. **Local PDF Generation:** ReportLab generates complete PDF audit reports on local disk without external network requests.

---

## 7. Environment Configuration Reference

All settings live in `backend/.env`. Essential edge configuration parameters:

| Variable | Default Value | Recommended Edge Setting | Description |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | `production` | Enables production security mode |
| `DEBUG` | `True` | `False` | Disables debug logs and traceback exposure |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/visionforge.db` | SQLite or PostgreSQL | Local database connection string |
| `JWT_SECRET_KEY` | `change-me-in-production` | Strong random key | HS256 JWT signature secret |
| `UPLOAD_DIR` | `data/inspection_uploads` | `data/inspection_uploads` | Storage path for ingested photos |
| `REPORTS_DIR` | `data/reports` | `data/reports` | Storage path for generated PDF reports |
| `LLM_TIMEOUT_SECONDS` | `10.0` | `5.0` | Timeout before falling back to local rules |

---

## 8. Edge Storage & Data Persistence

All inspection data on the edge server is stored in `backend/data/`:

| Directory / File | Contents | Retention / Backup Recommendation |
| :--- | :--- | :--- |
| `data/visionforge.db` | SQLite relational database (users, vendors, inspections, evidence) | Daily backup to factory backup NAS |
| `data/inspection_uploads/` | Ingested hardware photos | Archive older scans (>90 days) |
| `data/golden_images/` | Golden reference photos for approved SKUs | Read-only; backed up with version control |
| `data/roi_templates/` | JSON files specifying inspection crops | Read-only; backed up with blueprints |
| `data/reports/` | Generated PDF audit certificates | Retain per factory regulatory policy |

---

## 9. Troubleshooting Edge Deployments

### 1. Operator cannot connect to edge server from factory tablet
- Check that the edge server firewall allows inbound connections on the HTTP/HTTPS port:
  ```bash
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  ```
- Ensure FastAPI is bound to `0.0.0.0` (all interfaces), not `127.0.0.1` (localhost only).

### 2. Live progress bar freezes during inspection
- Check Nginx reverse proxy configuration. Ensure `proxy_buffering off;` is configured for the `/events` endpoint as shown in [Section 5](#5-reverse-proxy--sse-streaming-nginx).

### 3. YOLO detection is slow on edge CPU
- Ensure OpenMP and AVX2 instruction sets are enabled on your CPU.
- If an NVIDIA GPU is available, install the matching PyTorch CUDA wheel (`pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121`).

---

*Related Documentation:*
- [System Architecture](ARCHITECTURE.md)
- [Inspection Pipeline](PIPELINE.md)
- [Strategic Roadmap](ROADMAP.md)
