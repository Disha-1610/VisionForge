# ⚡ VisionForge AI — REST API & Telemetry Specification

> **Status:** Authoritative (Reflects Actual Implemented Codebase)  
> **Base URL:** `http://localhost:8000/api/v1`  
> **Interactive Documentation:** `http://localhost:8000/docs` (OpenAPI Swagger) & `http://localhost:8000/redoc`

---

## 📑 Table of Contents

- [1. Authentication & Security Headers](#1-authentication--security-headers)
- [2. Standard Error Response Schema](#2-standard-error-response-schema)
- [3. Authentication Endpoints (`/auth`)](#3-authentication-endpoints-auth)
- [4. Inspection & Telemetry Endpoints (`/inspections`)](#4-inspection--telemetry-endpoints-inspections)
- [5. Product & Golden Reference Endpoints (`/products`)](#5-product--golden-reference-endpoints-products)
- [6. Vendor Management Endpoints (`/vendors`)](#6-vendor-management-endpoints-vendors)
- [7. Audit Reports & PDF Endpoints (`/reports`)](#7-audit-reports--pdf-endpoints-reports)
- [8. Analytics & Metrics Endpoints (`/analytics`)](#8-analytics--metrics-endpoints-analytics)
- [9. System & Network Utility Endpoints (`/system`)](#9-system--network-utility-endpoints-system)
- [10. Server-Sent Events (SSE) Event Protocol](#10-server-sent-events-sse-event-protocol)

---

## 1. Authentication & Security Headers

All protected endpoints require an HTTP `Authorization` header containing a valid JSON Web Token (JWT):

```http
Authorization: Bearer <your_access_token>
```

- **Access Token Expiry:** 30 minutes.
- **Refresh Token Expiry:** 7 days.
- **Role-Based Access Control (RBAC):** Roles enforced via dependency injection:
  - `OPERATOR`: Standard factory operator (Inspections, views, approvals).
  - `ADMIN`: Full administrative control (Product management, vendor deletion, operator analytics).

---

## 2. Standard Error Response Schema

All unhandled exceptions and validation errors return a standardized JSON error body:

```json
{
  "detail": "Descriptive human-readable error message.",
  "error_code": "INVALID_CREDENTIALS",
  "timestamp": "2026-09-17T12:00:00Z"
}
```

### Common HTTP Status Codes
| Code | Status | Description |
|:---|:---|:---|
| `200` | OK | Request succeeded. |
| `201` | Created | Resource created successfully. |
| `204` | No Content | Resource deleted successfully. |
| `400` | Bad Request | Validation failure or invalid parameters. |
| `401` | Unauthorized | Missing, expired, or invalid JWT token. |
| `403` | Forbidden | Insufficient RBAC role permissions. |
| `404` | Not Found | Target resource does not exist. |
| `422` | Unprocessable Entity | Pydantic schema validation error. |

---

## 3. Authentication Endpoints (`/auth`)

### 3.1 Register User
- **Method / Path:** `POST /api/v1/auth/register`
- **Access Level:** Public
- **Request Body:**
  ```json
  {
    "email": "newoperator@visionforge.ai",
    "password": "SecurePassword123!",
    "full_name": "Jane Doe",
    "role": "OPERATOR"
  }
  ```
- **Response (`201 Created`):**
  ```json
  {
    "id": "usr_94a8e2b1",
    "email": "newoperator@visionforge.ai",
    "full_name": "Jane Doe",
    "role": "OPERATOR",
    "is_active": true,
    "created_at": "2026-09-17T10:15:00Z"
  }
  ```

### 3.2 Login
- **Method / Path:** `POST /api/v1/auth/login`
- **Access Level:** Public
- **Request Body:**
  ```json
  {
    "email": "operator@visionforge.ai",
    "password": "operatorpassword123"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsIn...",
    "token_type": "bearer",
    "expires_in": 1800,
    "user": {
      "id": "usr_102",
      "email": "operator@visionforge.ai",
      "full_name": "Line Operator 1",
      "role": "OPERATOR"
    }
  }
  ```

### 3.3 Refresh Token
- **Method / Path:** `POST /api/v1/auth/refresh`
- **Access Level:** Public
- **Request Body:**
  ```json
  {
    "refresh_token": "eyJhbGciOiJIUzI1NiIsIn..."
  }
  ```
- **Response (`200 OK`):** Returns new `access_token` and `refresh_token`.

### 3.4 Get Current User Profile
- **Method / Path:** `GET /api/v1/auth/me`
- **Access Level:** Authenticated (`OPERATOR` | `ADMIN`)
- **Response (`200 OK`):** Returns the current user profile object.

---

## 4. Inspection & Telemetry Endpoints (`/inspections`)

### 4.1 Ingest Hardware Image & Start Inspection
- **Method / Path:** `POST /api/v1/inspections`
- **Access Level:** Authenticated
- **Content-Type:** `multipart/form-data`
- **Form Parameters:**
  - `file` (File, required): Hardware image (`.jpg`, `.png`, `.webp`).
  - `product_id` (String, optional): Specific golden reference ID (if known).
  - `vendor_id` (String, optional): Target vendor ID.
  - `batch_number` (String, optional): Production batch / lot number.
  - `notes` (String, optional): Line operator notes.
- **Response (`201 Created`):**
  ```json
  {
    "inspection_id": "insp_77df3a01",
    "status": "PROCESSING",
    "image_url": "/static/uploads/insp_77df3a01.jpg",
    "created_at": "2026-09-17T11:00:00Z"
  }
  ```

### 4.2 List Inspections
- **Method / Path:** `GET /api/v1/inspections`
- **Query Parameters:** `skip` (int, default 0), `limit` (int, default 20), `status` (string), `verdict` (string).
- **Response (`200 OK`):**
  ```json
  {
    "total": 142,
    "items": [
      {
        "id": "insp_77df3a01",
        "batch_number": "LOT-2026-09A",
        "verdict": "REJECTED",
        "fraud_probability": 0.92,
        "status": "COMPLETED",
        "created_at": "2026-09-17T11:00:00Z"
      }
    ]
  }
  ```

### 4.3 Get Inspection Details & Evidence
- **Method / Path:** `GET /api/v1/inspections/{inspection_id}`
- **Response (`200 OK`):**
  ```json
  {
    "id": "insp_77df3a01",
    "status": "COMPLETED",
    "verdict": "REJECTED",
    "fraud_probability": 0.92,
    "confidence": 0.96,
    "root_cause_analysis": "Capacitor C12 missing; altered MCU silk-screen.",
    "product": {
      "id": "prod_atx_01",
      "name": "Industrial ATX Motherboard V1",
      "sku": "PCB-MCU-V2"
    },
    "evidence_items": [
      {
        "id": "ev_01",
        "agent_name": "structural_agent",
        "agent_type": "STRUCTURAL",
        "roi_name": "Power Stage",
        "anomaly_detected": true,
        "anomaly_score": 0.88,
        "description": "Missing capacitor C12"
      }
    ],
    "stage_latencies": {
      "quality_check": 0.028,
      "authenticity": 0.065,
      "reference_match": 0.185,
      "evidence_execution": 1.820,
      "judge": 0.460
    }
  }
  ```

### 4.4 Get Inspection Polling Status
- **Method / Path:** `GET /api/v1/inspections/{inspection_id}/status`
- **Response (`200 OK`):**
  ```json
  {
    "inspection_id": "insp_77df3a01",
    "status": "PROCESSING",
    "current_stage": 5,
    "current_stage_name": "Evidence Execution",
    "progress_pct": 62.5
  }
  ```

### 4.5 Real-Time Telemetry Stream (SSE)
- **Method / Path:** `GET /api/v1/inspections/{inspection_id}/events`
- **Response:** `text/event-stream` (See [Section 10](#10-server-sent-events-sse-event-protocol))

### 4.6 Approve / Override Inspection
- **Method / Path:** `POST /api/v1/inspections/{inspection_id}/approve`
- **Method / Path:** `POST /api/v1/inspections/{inspection_id}/override`
- **Request Body:**
  ```json
  {
    "override_verdict": "ACCEPTED",
    "reason": "Engineering change order ECO-492 permitted alternate capacitor manufacturer."
  }
  ```

---

## 5. Product & Golden Reference Endpoints (`/products`)

- `GET /api/v1/products` — List all registered golden reference blueprints.
- `GET /api/v1/products/{reference_id}` — Get single golden blueprint by ID.
- `POST /api/v1/products/upload` — Multipart upload of new golden reference image & trigger vector embedding indexing.
- `POST /api/v1/products` — Create golden blueprint metadata & ROI coordinates.
- `DELETE /api/v1/products/{reference_id}` — Delete reference blueprint (Admin only).

---

## 6. Vendor Management Endpoints (`/vendors`)

- `GET /api/v1/vendors` — List all supply-chain vendors with risk scores.
- `GET /api/v1/vendors/dropdown` — Lightweight vendor list for intake dropdowns.
- `GET /api/v1/vendors/{vendor_id}` — Get detailed vendor profile and historical inspection stats.
- `POST /api/v1/vendors` — Create new vendor record.
- `PATCH /api/v1/vendors/{vendor_id}` — Update vendor metadata or trust status.
- `DELETE /api/v1/vendors/{vendor_id}` — Delete vendor (Admin only).

---

## 7. Audit Reports & PDF Endpoints (`/reports`)

- `GET /api/v1/reports` — List historical inspection reports with pagination.
- `GET /api/v1/reports/{inspection_id}` — Get structured report JSON.
- `GET /api/v1/reports/{inspection_id}/pdf` — Stream / download compiled ReportLab PDF audit certificate (`application/pdf`).
- `DELETE /api/v1/reports/{inspection_id}` — Delete report record (Admin only).

---

## 8. Analytics & Metrics Endpoints (`/analytics`)

- `GET /api/v1/analytics/summary` — High-level KPI counters (Total inspections, fraud rate %, avg latency).
- `GET /api/v1/analytics/vendors` — Top high-risk vendor ranking.
- `GET /api/v1/analytics/locations` — Fraud incidence by manufacturing facility.
- `GET /api/v1/analytics/trend` — Monthly time-series of inspections and defect rates.
- `GET /api/v1/analytics/by-operator` — Breakdown of operator throughput and override rates (Admin only).

---

## 9. System & Network Utility Endpoints (`/system`)

### 9.1 Network Interface & Mobile Tunnel Discovery
- **Method / Path:** `GET /api/v1/system/network`
- **Access Level:** Public
- **Description:** Probes local network interfaces and cloud tunnel environment variables to supply the `DesktopGuardModal` with the reachability URL for mobile phone camera pairing.
- **Response (`200 OK`):**
  ```json
  {
    "local_ip": "192.168.1.145",
    "port": 5173,
    "public_url": "https://visionforge-mobile-tunnel.trycloudflare.com",
    "is_tunneled": true
  }
  ```

---

## 10. Server-Sent Events (SSE) Event Protocol

When streaming from `GET /api/v1/inspections/{inspection_id}/events`, the server emits strongly-typed event frames:

```
event: stage_start
data: {"stage": 1, "stage_name": "Quality Validation", "timestamp": "2026-09-17T11:00:00.100Z"}

event: stage_complete
data: {"stage": 1, "stage_name": "Quality Validation", "status": "PASSED", "duration_ms": 28, "details": {"blur_score": 248.5, "brightness": 134.2}}

event: stage_start
data: {"stage": 5, "stage_name": "Evidence Execution", "timestamp": "2026-09-17T11:00:00.320Z"}

event: agent_complete
data: {"agent": "structural_agent", "anomaly_detected": true, "finding": "Missing capacitor C12"}

event: pipeline_complete
data: {"inspection_id": "insp_77df3a01", "verdict": "REJECTED", "fraud_probability": 0.92, "report_url": "/api/v1/reports/insp_77df3a01/pdf"}
```

---

*For relational database schemas, consult [`docs/DATABASE.md`](DATABASE.md).*
