# Security Guide & Threat Analysis

This document explains how security, authentication, and access control work in VisionForge AI. It details what is implemented, how permissions are enforced, and where current security gaps exist.

Every vulnerability listed here is verified against the actual codebase and cross-referenced with [problems.md](../problems.md).

---

## 1. Quick Overview

VisionForge is designed as an on-premises factory workstation with optional cloud AI connectivity.

### Key Security Invariants
- **Password Hashing:** Passwords are hashed with **bcrypt** (12 work rounds). Plain-text passwords are never stored or logged.
- **Dual-Token JWT:** Users receive a short-lived **Access Token (30 mins)** and a longer-lived **Refresh Token (7 days)**.
- **Real-Time Role Checks:** Every protected request checks the user's role directly in the database. Changing a user's role takes effect immediately without waiting for token expiration.
- **Current Limitations:** Forensic evidence records are currently subject to database cascade deletion upon inspection removal, and audit reports are not yet digitally signed with cryptographic SHA-256 hashes. Both are tracked in [problems.md](../problems.md).

---

## 2. Authentication & Token Lifecycle

### Password Security
- When a user logs in via `POST /api/v1/auth/login`, the backend verifies their password against the stored bcrypt hash using `passlib.context.CryptContext` (`bcrypt` scheme).
- Passwords must be at least 8 characters long.

### Token Architecture

| Token Type | Lifespan | Transmission | Purpose |
|:---|:---|:---|:---|
| **Access Token** | 30 minutes | `Authorization: Bearer <token>` | Authorizes API calls |
| **Refresh Token** | 7 days | Request body in `POST /auth/refresh` | Obtains a new token pair without re-entering credentials |

Both tokens are signed with **HMAC-SHA256 (HS256)** using the server's `JWT_SECRET_KEY`.

```
[Client Login] ──► (POST /auth/login) ──► Validates bcrypt hash
                                                │
                 ┌──────────────────────────────┴─────────────────────────────┐
                 ▼                                                           ▼
       [30-Minute Access Token]                                    [7-Day Refresh Token]
     Sent on every HTTP Request                               Used to regenerate Access Token
```

> [!WARNING]
> The default secret key in development is `"change-me-in-production"`. In any shared or production environment, `JWT_SECRET_KEY` must be set to a secure, randomly generated 32+ character secret in `backend/.env`.

---

## 3. Role-Based Access Control (RBAC)

VisionForge defines **two user roles**:

1. **`operator`**: Line technicians and inspectors who upload hardware, monitor live inspections, review findings, and download PDF reports.
2. **`admin`**: Factory QA leads and system managers who configure Golden Blueprints, manage vendors, and inspect organization-wide analytics.

### Detailed Permissions Matrix

| Endpoint / Action | Method | Public | Operator | Admin |
|:---|:---:|:---:|:---:|:---:|
| User Registration (`/api/v1/auth/register`) | `POST` | ✅ | ✅ | ✅ |
| User Login (`/api/v1/auth/login`) | `POST` | ✅ | ✅ | ✅ |
| Refresh Token (`/api/v1/auth/refresh`) | `POST` | ✅ | ✅ | ✅ |
| Health Check (`/health`) | `GET` | ✅ | ✅ | ✅ |
| API Docs (`/docs`, `/redoc`) | `GET` | ✅ | ✅ | ✅ |
| **Live Inspection Progress Stream** (`/inspections/{id}/events`) | `GET` | ⚠️ *(Unprotected)* | ✅ | ✅ |
| Create Inspection / Upload Hardware | `POST` | ❌ | ✅ | ✅ |
| List / View Inspection Records | `GET` | ❌ | ✅ | ✅ |
| Review / Override Inspection Verdict | `POST` | ❌ | ✅ | ✅ |
| View / Download PDF Audit Reports | `GET` | ❌ | ✅ | ✅ |
| **Delete Inspection Report** (`/reports/{id}`) | `DELETE` | ❌ | ⚠️ *(Allowed)* | ✅ |
| List Vendors & Golden Blueprints | `GET` | ❌ | ✅ | ✅ |
| Create / Edit / Delete Vendors | `POST/PATCH/DELETE` | ❌ | ❌ | ✅ |
| Upload / Delete Golden Blueprints | `POST/DELETE` | ❌ | ❌ | ✅ |
| View Organization-Wide Analytics | `GET` | ❌ | *(Own only)* | ✅ *(All)* |

---

## 4. Network & Deployment Security

VisionForge is deployed on a local workstation or edge server on the factory floor:

### 1. Cross-Origin Resource Sharing (CORS)
- `CORS_ORIGINS` in `backend/.env` restricts browser-based requests to trusted hosts (default: `http://localhost:5173`, `http://localhost:3000`).
- **Important:** CORS only restricts requests made from web browsers. It does not block direct backend calls, curl scripts, or local network probes.

### 2. Cloudflare Quick Tunnel (Mobile Camera Pairing)
- When operators pair their smartphones via QR code, the frontend uses a Cloudflare Quick Tunnel (`trycloudflare.com`) to bypass local Wi-Fi isolation.
- **Security Note:** The tunnel exposes the local web server to the public internet via a random subdomain. When operating in high-security air-gapped environments, the tunnel should be disabled in favor of a private factory LAN Wi-Fi network.

### 3. Static File Access
- Image uploads and Golden Reference CAD images are stored under `data/inspection_uploads/` and `data/golden_references/`.
- In `main.py`, these folders are mounted as `/static/uploads` and `/static/golden`.
- **Gap:** These static directories do not currently enforce token verification. Anyone on the local network who knows or enumerates the file path can view uploaded PCB images.

---

## 5. Confirmed Vulnerabilities & Weak Points

The following real-world security vulnerabilities are documented and prioritized in [problems.md](../problems.md):

### 1. Privilege Escalation via Open Registration (Critical)
- **File:** `backend/app/routers/auth.py:30-49`
- **Issue:** The public registration endpoint accepts a `role` field directly in the JSON payload (`{"role": "admin"}`). Anyone on the network can register an Administrator account.
- **Fix:** Force all public registrations to `UserRole.OPERATOR`. Restrict admin creation to existing admins.

### 2. Live Telemetry Stream Lacks Authentication (High)
- **File:** `backend/app/routers/inspections.py:219-223`
- **Issue:** `GET /api/v1/inspections/{id}/events` does not require a login token. Anyone with an inspection UUID can monitor live pipeline stages and read fraud verdicts.
- **Fix:** Add `Depends(get_current_user)` to the route handler.

### 3. Missing Role Check on Report Deletion (High)
- **File:** `backend/app/routers/reports.py:406-422`
- **Issue:** `DELETE /api/v1/reports/{id}` requires a logged-in user, but does not check if the user is an Admin. Operators can delete failed inspection reports.
- **Fix:** Add `require_roles(UserRole.ADMIN)` to the route.

### 4. Path Traversal in Golden Reference Upload (High)
- **File:** `backend/app/routers/products.py:81-86`
- **Issue:** The `part_code` field is used to generate filenames without stripping directory traversal sequences (`../`).
- **Fix:** Sanitize the input string with a strict alphanumeric regex (`^[a-zA-Z0-9_-]+$`).

### 5. Insecure Default JWT Key & Seed Credentials (High)
- **File:** `backend/app/core/config.py:32`
- **Issue:** The default secret key is `change-me-in-production`, and default seed users (`admin@visionforge.ai` / `adminpassword123`) are documented publicly.
- **Fix:** Require custom environment variables in production and remove hardcoded seed credentials.

### 6. Unbounded Uploads & Missing Magic-Byte Validation (Medium)
- **File:** `backend/app/utils/file_utils.py:13-44`
- **Issue:** Files are checked only by extension (`.png`, `.jpg`). There is no file size limit or file-header (magic bytes) validation.
- **Fix:** Enforce a 15 MB file size cap and verify image headers with Pillow or `python-magic`.

---

## 6. Production Hardening Checklist

Before deploying VisionForge on a live manufacturing floor or connecting it to corporate networks, complete these 10 steps:

- [ ] **1. Disable Self-Assigned Roles:** Update `auth.py` so self-registration only grants the `operator` role.
- [ ] **2. Protect the SSE Stream:** Require authentication headers or query tokens on `/api/v1/inspections/{id}/events`.
- [ ] **3. Restrict Report Deletion:** Limit `DELETE /api/v1/reports/{id}` strictly to `admin` accounts.
- [ ] **4. Rotate JWT Secret:** Set `JWT_SECRET_KEY` to a cryptographically secure 64-character hex string.
- [ ] **5. Change Seed Passwords:** Change default passwords for `admin@visionforge.ai` and `operator@visionforge.ai`.
- [ ] **6. Enforce Upload Limits:** Limit image uploads to 15 MB each and validate magic bytes before saving.
- [ ] **7. Authenticate Static Files:** Replace public `/static/uploads` mounts with an authenticated image proxy route.
- [ ] **8. Disable Debug Mode:** Set `DEBUG=false` in `backend/.env`.
- [ ] **9. Restrict CORS:** Limit `CORS_ORIGINS` strictly to the local production frontend domain.
- [ ] **10. Enable Local Air-Gapped Mode:** If cloud access is restricted, enable local fallback mode to prevent cloud API retry delays.

---

*For technical architecture details, read [ARCHITECTURE.md](ARCHITECTURE.md). For the full engineering problem register, see [problems.md](../problems.md).*
