# VisionForge Comprehensive Engineering, Security & Edge Audit

This document is the unified, authoritative register of all confirmed problems, architectural weaknesses, security vulnerabilities, and edge-deployment risks in the **VisionForge** repository.

Every issue listed here is verified against the active codebase with exact file paths, line ranges, root-cause explanations, and actionable remediation guidelines. All previously resolved issues (such as the closed SSE session crash, vector dimension mismatch fallback, and the missing review endpoint) have been pruned.

---

## Table of Contents
1. [Architecture & Code Quality](#1-architecture--code-quality)
2. [API & Backend Routing](#2-api--backend-routing)
3. [Database & Storage Layer](#3-database--storage-layer)
4. [AI, Computer Vision & Multimodal Swarm](#4-ai-computer-vision--multimodal-swarm)
5. [Security & Access Control](#5-security--access-control)
6. [Factory Edge Server & Operational Reliability](#6-factory-edge-server--operational-reliability)
7. [Priority Action Matrix (Top 10 Remediations)](#7-priority-action-matrix-top-10-remediations)

---

## 1. Architecture & Code Quality

### Issue 1.1: Event Loop Starvation from Synchronous Computer Vision Algorithms [RESOLVED]
- **Classification**: Actual Bug | Architecture Weakness | Edge-Deployment Risk
- **Severity**: High
- **Status**: ✅ **RESOLVED**
- **Location**: `backend/app/pipeline/stages/authenticity.py:113-375` (`_compute_ela`, `_validate_exif`, `_detect_screenshot`, `_check_noise_consistency`, `_detect_copy_move`)
- **Resolution**: 
  All CPU-intensive algorithms (ELA JPEG re-saving, OpenCV contour discovery, EXIF extraction, Laplacian noise variance, and block-wise clone detection) have been extracted into synchronous `_sync` worker functions and invoked from the asynchronous pipeline stage using `await asyncio.to_thread(...)`. This completely offloads heavy CPU/NumPy calculations to worker threads, preventing event loop freezes and keeping FastAPI health checks and SSE telemetry streams responsive under high-resolution workloads.

---

### Issue 1.2: Event Loop Blocking from Synchronous HTTP Network Requests [RESOLVED]
- **Classification**: Actual Bug | Architecture Weakness
- **Severity**: High
- **Status**: ✅ **RESOLVED**
- **Location**: `backend/app/services/embedding_service.py:108` (`_generate_gemini_embedding`), `backend/app/pipeline/stages/reference_match.py:61-64`, `backend/app/routers/products.py:91`
- **Resolution**: 
  1. Synchronous `requests.post()` was replaced with `httpx.post()` in `embedding_service.py`.
  2. Embedding generation calls in `reference_match.py` (`generate_embedding_for_index` and `generate_embedding`) are wrapped in `await asyncio.to_thread(...)`.
  3. Product reference indexing in `products.py` route handler is also executed via `await asyncio.to_thread(...)`, eliminating event loop blocks during vector embedding creation.

---

### Issue 1.3: Unbounded In-Memory State Retention (WorkingMemory & EvidenceStore Heap Leak) [RESOLVED]
- **Classification**: Architecture Weakness | Edge-Deployment Risk
- **Severity**: High
- **Status**: ✅ **RESOLVED**
- **Location**: `backend/app/shared/memory.py:176-204` (`WorkingMemoryRegistry`) & `backend/app/shared/evidence_store.py:51-140` (`EvidenceStore`)
- **Resolution**: 
  1. Implemented bounded LRU/FIFO capacity limits (`max_size=100`) in `WorkingMemoryRegistry`. When capacity is reached, the oldest inspection state is evicted from memory.
  2. Implemented capacity eviction (`max_inspections=100`) in `EvidenceStore`. When saturated, the oldest inspection and all its child evidence records and sequence counters are pruned from heap memory, delegating historical audit retention to the persistent database.

---

### Issue 1.4: Redundant Model Instantiations in Evidence Execution [RESOLVED]
- **Classification**: Architecture Weakness | Edge-Deployment Risk
- **Severity**: Medium
- **Status**: ✅ **RESOLVED**
- **Location**: `backend/app/pipeline/stages/evidence_execution.py:49-65, 367` (`get_default_agent_registry`)
- **Resolution**: 
  `get_default_agent_registry()` now caches instantiated agents (`OCRAgent`, `LabelAgent`, `StructuralAgent`, `VLMAgent`) in a module-level singleton `_DEFAULT_AGENT_REGISTRY`. YOLO PyTorch weights and EasyOCR models are instantiated only once per worker lifecycle, eliminating redundant model loading delays and RAM spikes on subsequent inspections.

---

### Issue 1.5: Unreleased Resources on Application Shutdown (`shutdown_llm_client`) [RESOLVED]
- **Classification**: Technical Debt | Missing Hardening
- **Severity**: Low
- **Status**: ✅ **RESOLVED**
- **Location**: `backend/app/main.py:70-75` (`lifespan`) & `backend/app/shared/llm_client.py:982-987` (`shutdown_llm_client`)
- **Resolution**: 
  Added `await shutdown_llm_client()` within the shutdown sequence of FastAPI's `lifespan` context manager in `main.py`, gracefully releasing persistent HTTP connection pools and client sockets.

---

## 2. API & Backend Routing

### Issue 2.1: Live Progress Stream Missing Final Verdict in In-Memory Generator [RESOLVED]
- **Classification**: Actual Bug | Frontend Blocker
- **Severity**: Medium
- **Status**: ✅ **RESOLVED**
- **Location**: `backend/app/routers/inspections.py:241-248`
- **Resolution**: 
  The in-memory pipeline completion branch of the SSE event generator (`stream_inspection_events`) now directly extracts and includes `"verdict": prog.get("verdict")` and `"policy_action": prog.get("policy_action")` in the final `verdict` event payload. When the pipeline finishes, the frontend `usePipelineSSE` hook immediately captures the verdict and policy action, rendering the Emerald/Crimson decision HUD banner without requiring manual page refresh or resulting in undefined cards.

---

### Issue 2.2: Missing Authentication on Real-Time Stage Event Stream
- **Classification**: Security Risk | Actual Bug
- **Severity**: High
- **Location**: `backend/app/routers/inspections.py:219-223` (`stream_inspection_events`)
- **Problem**: 
  Unlike all other inspection endpoints (`get_inspection`, `list_inspections`, `get_inspection_status`), `GET /api/v1/inspections/{inspection_id}/events` does not include `current_user: User = Depends(get_current_user)`.
- **Why it is a problem**: 
  Any client on the network that knows or scans for an inspection UUID can connect to the event stream without an authorization header.
- **Impact**: 
  Unauthenticated disclosure of live inspection telemetry, detailed forensic findings, error logs, and fraud verdicts.
- **Recommended fix**: 
  Add `current_user: User = Depends(get_current_user)` to `stream_inspection_events` (supporting token verification via query parameter if EventSource browser clients cannot send custom Authorization headers).

---

### Issue 2.3: Unbounded File Uploads (No Maximum File Size Limit / DoS Risk)
- **Classification**: Security Risk | Edge-Deployment Risk
- **Severity**: High
- **Location**: `backend/app/routers/inspections.py:62-105` (`create_inspection`) & `backend/app/utils/file_utils.py:29-44` (`save_upload_file`)
- **Problem**: 
  `create_inspection` accepts up to 6 images via multipart form data. In `save_upload_file`, chunks are read and written to disk in a loop (`while chunk := await upload_file.read(DEFAULT_CHUNK_SIZE)`) with no maximum file size check or cumulative payload limit.
- **Why it is a problem**: 
  A malfunctioning camera stream or malicious client can upload gigabyte-sized files in an upload request.
- **Impact**: 
  Can rapidly fill the host filesystem, resulting in disk exhaustion (`ENOSPC`), corrupting the local SQLite/PostgreSQL database, and crashing the edge host.
- **Recommended fix**: 
  Enforce a strict per-image size limit (e.g., maximum 15MB per file) and a cumulative inspection limit (e.g., 50MB total) inside `save_upload_file`, aborting with HTTP 413 (Payload Too Large) if exceeded.

---

### Issue 2.4: Silent Exceptions in Global Exception Handler Without Traceback Logging
- **Classification**: Missing Hardening | Edge-Deployment Risk
- **Severity**: Medium
- **Location**: `backend/app/core/exceptions.py:43-48` (`generic_exception_handler`)
- **Problem**: 
  The catch-all exception handler `generic_exception_handler` catches `Exception` and returns a JSON response `{"detail": "Internal server error"}` with HTTP 500 status code, but does not call `logger.exception(exc)`.
- **Why it is a problem**: 
  Unhandled exceptions produce no stack trace in application logs.
- **Impact**: 
  In an edge environment without interactive debugging tools, troubleshooting intermittent 500 errors is virtually impossible because the failure causes are completely obscured.
- **Recommended fix**: 
  Add `logger.exception("Unhandled server exception on %s %s: %s", request.method, request.url, exc)` inside `generic_exception_handler` prior to returning the 500 JSON response.

---

### Issue 2.5: Full Table In-Memory Loading for Analytics Aggregations
- **Classification**: Architecture Weakness | Edge-Deployment Risk
- **Severity**: Medium
- **Location**: `backend/app/services/analytics_service.py:60-108, 207-249` (`get_summary_metrics`, `get_trend`)
- **Problem**: 
  `get_summary_metrics` and `get_trend` query `select(Inspection)` and call `result.scalars().all()` or `result.all()`, loading every inspection row in the database into Python memory. Aggregation (total counts, fraud rates, averages) is calculated using Python list comprehensions and loops.
- **Why it is a problem**: 
  ORM models with JSON columns (`working_memory`) consume considerable memory when loaded in bulk.
- **Impact**: 
  As inspection history grows past thousands of records, querying the analytics dashboard causes heavy database serialization latency and high memory spikes on the edge server.
- **Recommended fix**: 
  Rewrite analytics aggregations using SQL aggregate functions (`func.count()`, `func.sum()`, `func.avg()`, `func.date_trunc()` / `strftime()`) so the database engine performs the computation and returns a single summary row.

---

### Issue 2.6: Unhandled Foreign Key Violation on Vendor Deletion
- **Classification**: Actual Bug | Missing Hardening
- **Severity**: Medium
- **Location**: `backend/app/routers/vendors.py:97-108` (`delete_vendor`)
- **Problem**: 
  `DELETE /api/v1/vendors/{vendor_id}` attempts `await db.delete(vendor)` directly. In `models/inspection.py`, `Inspection.vendor_id` has `ForeignKey("vendors.id", ondelete="RESTRICT")`.
- **Why it is a problem**: 
  Deleting a vendor that has associated inspection records violates database foreign key constraints.
- **Impact**: 
  SQLAlchemy raises an `IntegrityError` which triggers an unhandled HTTP 500 Internal Server Error instead of a descriptive HTTP 400 or 409 error informing the user that inspections are attached to this vendor.
- **Recommended fix**: 
  Check whether associated inspections exist (`select(func.count(Inspection.id)).where(Inspection.vendor_id == vendor_id)`), or catch `IntegrityError` and raise `HTTPException(status_code=409, detail="Cannot delete vendor with existing inspections")`.

---

### Issue 2.7: Request Fields Silently Accepted but Never Stored
- **Classification**: Schema Inconsistency | Technical Debt
- **Severity**: Low
- **Location**: `backend/app/schemas/vendor.py:39`, `backend/app/routers/vendors.py:88-90`, `backend/app/schemas/product.py:13`
- **Problem**: 
  - `PATCH /api/v1/vendors/{id}` accepts `is_active`. The `vendors` table has no `is_active` column in `models/vendor.py`. The handler sets it via `setattr` which is never persisted to the DB.
  - `GoldenReference` schema defines a `vendor_id` field, but the `golden_references` database model does not have a `vendor_id` foreign key or column.
- **Impact**: 
  API callers receive a 200 OK response believing changes were saved, but values are silently lost.
- **Recommended fix**: 
  Add `is_active` to `Vendor` model, or remove the fields from the respective Pydantic schemas.

---

### Issue 2.8: Desktop Guard Modal LAN IP Fallback Returns 401 Unauthorized [RESOLVED]
- **Classification**: Actual Bug | Mobile Intake Handoff
- **Severity**: Medium
- **Status**: ✅ **RESOLVED**
- **Location**: `frontend/src/components/inspection/DesktopGuardModal.jsx:38` & `backend/app/routers/system.py:35-38`
- **Resolution**: 
  1. `GET /api/v1/system/network` was updated to be a public endpoint without `current_user` dependency, allowing unauthenticated network topology discovery during device pairing.
  2. `DesktopGuardModal.jsx` now passes Bearer tokens if available in `localStorage`.
  The modal successfully resolves the host's actual Wi-Fi/LAN IP address and generates functional QR codes for smartphone pairing on factory subnets.

---

### Issue 2.9: Dual Error Response Shapes
- **Classification**: Inconsistency | Client Parsing Risk
- **Severity**: Low
- **Location**: `backend/app/core/exceptions.py`
- **Problem**: 
  Custom exception handlers return `{"detail": "String error message"}`, but FastAPI / Pydantic validation errors return `{"detail": [{"loc": [...], "msg": "..."}]}`.
- **Impact**: 
  Frontend Axios interceptors and mobile clients must write conditional parsing logic to extract error messages safely.
- **Recommended fix**: 
  Add a custom `RequestValidationError` handler in `exceptions.py` that normalizes validation errors into a consistent JSON envelope.

---

### Issue 2.10: Swagger UI "Authorize" Modal Flow Mismatch
- **Classification**: Documentation / DevEx Bug
- **Severity**: Low
- **Location**: `backend/app/core/security.py:22` & `backend/app/schemas/auth.py`
- **Problem**: 
  `security.py` uses `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`. OpenAPI assumes an `application/x-www-form-urlencoded` payload with `username` and `password`. But `auth.py` expects a JSON body with `email` and `password`.
- **Impact**: 
  Developers testing APIs via the interactive Swagger UI (`/docs`) cannot authenticate using the "Authorize" button.
- **Recommended fix**: 
  Accept both Form and JSON data in the login endpoint, or configure OpenAPI security schemes with a custom HTTP Bearer auth scheme.

---

## 3. Database & Storage Layer

### Issue 3.1: In-Memory SQLite Fallback with NullPool Causes Immediate Table Loss
- **Classification**: Actual Bug | Edge-Deployment Risk
- **Severity**: Critical
- **Location**: `backend/app/core/database.py:60-98` (`_build_engine`)
- **Problem**: 
  If the primary PostgreSQL connection fails, `_build_engine()` falls back to `sqlite+aiosqlite:///:memory:` with `poolclass=NullPool`. In SQLite, an in-memory database (`:memory:`) with `NullPool` creates a completely new, empty in-memory database on every connection checkout.
- **Why it is a problem**: 
  Tables created during `init_db()` in the startup connection are instantly destroyed when that connection closes. Subsequent API requests check out a new connection to a completely empty SQLite database.
- **Impact**: 
  Any API endpoint attempting to read or write data immediately throws `sqlite3.OperationalError: no such table: users`.
- **Recommended fix**: 
  If SQLite is used, specify a persistent disk path (`sqlite+aiosqlite:///data/visionforge.db`), or use `sqlite+aiosqlite:///:memory:?cache=shared` with `StaticPool` for testing. Never fall back to ephemeral `:memory:` with `NullPool`.

---

### Issue 3.2: Orphaned Image and Report Files on Record Deletion
- **Classification**: Actual Bug | Edge-Deployment Risk
- **Severity**: High
- **Location**: `backend/app/routers/reports.py:406-422` (`delete_report`) & `backend/app/routers/products.py:144-166` (`delete_golden_reference`)
- **Problem**: 
  `delete_report` executes `await db.delete(inspection)` which removes the database row and cascades to `evidence`, but does not delete the directory `data/inspection_uploads/<inspection_id>/` or the PDF file `inspection.report_path`. Similarly, `delete_golden_reference` leaves `ref.image_path` on disk.
- **Why it is a problem**: 
  Filesystem storage and database state become inconsistent; disk files remain orphaned permanently.
- **Impact**: 
  On edge appliances with restricted disk space, deleting test or expired inspections from the UI does not free disk space, leading to progressive disk exhaustion.
- **Recommended fix**: 
  Add cleanup logic to delete the associated directory (`shutil.rmtree(inspection_dir, ignore_errors=True)`) and files (`Path(pdf_path).unlink(missing_ok=True)`) upon database record deletion.

---

### Issue 3.3: Incompatible Alembic Migration with Non-PostgreSQL Dialects
- **Classification**: Architecture Weakness | Technical Debt
- **Severity**: Medium
- **Location**: `backend/migrations/versions/001_initial_tables.py:19-115` (`upgrade`)
- **Problem**: 
  The initial Alembic migration explicitly imports and uses PostgreSQL-specific types: `postgresql.UUID(as_uuid=True)`, `postgresql.ARRAY(sa.String())`, `postgresql.JSONB()`, and PostgreSQL enum types. Additionally, columns `status` and `error_message` are missing from the `inspections` table definition in the migration.
- **Why it is a problem**: 
  If an edge installation runs on SQLite, Alembic fails with syntax errors because `postgresql.ARRAY` and PostgreSQL enum types are unsupported in SQLite.
- **Impact**: 
  Database migrations cannot run on SQLite-based edge servers, breaking automated schema upgrades.
- **Recommended fix**: 
  Use SQLAlchemy cross-dialect abstractions (such as `.with_variant()`, generic `sa.JSON()`, and `sa.String()` for UUIDs/arrays on SQLite) in migration files, matching the models in `app/models/`.

---

### Issue 3.4: Dual Schema Creation (Base.metadata.create_all Bypassing Alembic)
- **Classification**: Technical Debt | Architecture Weakness
- **Severity**: Low
- **Location**: `backend/app/core/database.py:169-171` (`init_db`)
- **Problem**: 
  `init_db()` invokes `await conn.run_sync(Base.metadata.create_all)` on application startup.
- **Why it is a problem**: 
  `create_all` creates database tables without writing an initial revision record to Alembic's `alembic_version` table.
- **Impact**: 
  Running `alembic upgrade head` on an existing database will fail with table-already-exists errors.
- **Recommended fix**: 
  Use Alembic as the single source of truth for database schema management, or run programmatic migrations (`alembic.command.upgrade`) during startup rather than raw `create_all`.

---

### Issue 3.5: Foreign Key Constraints Not Enforced on SQLite
- **Classification**: Data Integrity Bug
- **Severity**: Medium
- **Location**: `backend/app/core/database.py`
- **Problem**: 
  In SQLite, foreign key enforcement is disabled by default. The engine setup never issues `PRAGMA foreign_keys=ON`.
- **Impact**: 
  Deleting vendors or records during development leaves orphaned foreign keys without raising integrity errors, hiding bugs that only appear in production PostgreSQL.
- **Recommended fix**: 
  Add a connection event listener (`@event.listens_for(engine.sync_engine, "connect")`) that executes `PRAGMA foreign_keys=ON` whenever the dialect is SQLite.

---

### Issue 3.6: Evidence Table Cascade Delete Violates Forensic Audit Standard
- **Classification**: Compliance & Audit Defect
- **Severity**: Medium
- **Location**: `backend/app/models/evidence.py:27`, `backend/app/models/inspection.py:146`
- **Problem**: 
  The relationship between `inspections` and `evidence` is configured with `ondelete="CASCADE"`. Deleting an inspection deletes all associated evidence rows.
- **Why it is a problem**: 
  VisionForge documentation claims that evidence records form an immutable, append-only audit trail. Cascade deletion violates this governance invariant.
- **Recommended fix**: 
  Remove `CASCADE` and enforce soft-deletion or prevent hard deletion of inspection records that have completed audits.

---

## 4. AI, Computer Vision & Multimodal Swarm

### Issue 4.1: Stage 5 VLM Concurrency Storm Hits Free-Tier Rate Limits (429) [RESOLVED]
- **Classification**: Operational Bottleneck | Reliability
- **Severity**: High
- **Status**: ✅ **RESOLVED**
- **Location**: `backend/app/pipeline/stages/evidence_execution.py:75-81, 439-477`
- **Resolution**: 
  1. Throttled concurrent VLM multimodal requests using a dedicated semaphore `get_vlm_semaphore(2)` to limit concurrent API calls.
  2. Implemented round-robin load balancing alternating between Groq (Qwen 27B Vision) on even indices and Gemini (Gemini Flash) on odd indices.
  3. Integrated automatic offline fallback mode (`enable_offline_fallback: True`) to gracefully absorb transient 429 rate limit exceptions without failing the inspection pipeline.

---

### Issue 4.2: Concurrency & GPU Memory Exhaustion from Unpooled Model Inference [RESOLVED]
- **Classification**: Architecture Weakness | Edge-Deployment Risk
- **Severity**: High
- **Status**: ✅ **RESOLVED**
- **Location**: `backend/app/pipeline/stages/evidence_execution.py:50, 67-73, 376` (`get_global_inference_semaphore`)
- **Resolution**: 
  Replaced per-inspection local semaphores with a process-wide inference semaphore singleton (`get_global_inference_semaphore(max_concurrency=4)`). All active inspections share this unified concurrency pool, preventing simultaneous multi-inspection PyTorch/YOLO/OCR inference spikes from exhausting edge VRAM or triggering CUDA OOM crashes.

---

### Issue 4.3: Silent Failure on FAISS Index Synchronization During Product Deletion
- **Classification**: Actual Bug | Technical Debt
- **Severity**: Low
- **Location**: `backend/app/routers/products.py:158-162` (`delete_golden_reference`)
- **Problem**: 
  When a golden reference is deleted, the code attempts to remove it from FAISS with `except Exception: pass`.
- **Why it is a problem**: 
  If removing the vector or saving the updated index to disk fails, the error is swallowed silently.
- **Impact**: 
  The FAISS index on disk remains out-of-sync with the database. Stage 3 (Reference Match) may continue returning references that have been deleted from the database.
- **Recommended fix**: 
  Log the failure with `logger.error()` and raise an HTTP 500 or roll back the deletion if vector index synchronization fails.

---

### Issue 4.4: Rigid Hardcoded Anomaly Scoring in Evidence Fusion [RESOLVED]
- **Classification**: Architecture Weakness
- **Severity**: Low
- **Status**: ✅ **RESOLVED**
- **Location**: `backend/app/pipeline/stages/evidence_fusion.py:136-152` (`_extract_agent_anomaly_score`) & `backend/app/pipeline/stages/evidence_execution.py:275-279`
- **Resolution**: 
  1. Updated `evidence_execution.py` to forward region metadata (`priority`, `critical`, `severity`) into each generated evidence record.
  2. In `evidence_fusion.py`, `_extract_agent_anomaly_score` evaluates ROI criticality dynamically: non-critical or normal priority components scale anomaly scores proportionally (0.75 for missing, 0.70 for extra, 0.65 for mismatch) while critical components trigger full forensic alerts (0.95/0.90/0.85). This prevents false-positive fraud classification for non-critical PCB jumpers/capacitors.

---

## 5. Security & Access Control

### Issue 5.1: Unauthenticated Privilege Escalation to Admin via Open Registration
- **Classification**: Security Risk | Actual Bug
- **Severity**: Critical
- **Location**: `backend/app/routers/auth.py:30-49` (`register`) & `backend/app/schemas/auth.py:14-19` (`UserRegister`)
- **Problem**: 
  `POST /api/v1/auth/register` is an unauthenticated public route. The request schema `UserRegister` defines `role: UserRole = Field(default=UserRole.OPERATOR)`. The route handler directly creates a user with `role=body.role` without verifying the caller's identity or role.
- **Why it is a problem**: 
  Any user or external attacker on the network can send `{"email": "attacker@corp.local", "password": "...", "full_name": "...", "role": "admin"}` and obtain a full Administrator account.
- **Impact**: 
  Complete compromise of access controls: the attacker can manage users, delete audit reports, modify golden reference templates, and override verdicts.
- **Recommended fix**: 
  Remove `role` from `UserRegister`, hardcoding new self-registered users to `UserRole.OPERATOR`, or require `require_roles(UserRole.ADMIN)` on endpoints that can create Admin accounts.

---

### Issue 5.2: Insecure Default JWT Secret Key
- **Classification**: Security Risk | Missing Hardening
- **Severity**: High
- **Location**: `backend/app/core/config.py:32` (`JWT_SECRET_KEY`)
- **Problem**: 
  `Settings` sets `JWT_SECRET_KEY: str = "change-me-in-production"`.
- **Why it is a problem**: 
  If the application is deployed without explicitly providing a secure `JWT_SECRET_KEY` in environment variables or `.env`, the server signs tokens using a well-known static string.
- **Impact**: 
  An attacker can forge valid JWT tokens with `sub: <admin_uuid>` and `role: "admin"`, completely bypassing authentication.
- **Recommended fix**: 
  In non-development environments, validate on startup that `JWT_SECRET_KEY != "change-me-in-production"` and that it meets minimum entropy requirements (at least 32 random characters), raising a fatal startup error if insecure.

---

### Issue 5.3: Path Traversal Vulnerability in Golden Reference Upload
- **Classification**: Security Risk
- **Severity**: High
- **Location**: `backend/app/routers/products.py:81-86` (`upload_golden_reference`)
- **Problem**: 
  In `upload_golden_reference`:
  ```python
  clean_code = part_code.strip().upper()
  dest_filename = f"{clean_code.lower().replace('-', '_')}_{ref_id.hex[:8]}{ext}"
  dest_path = golden_dir / dest_filename
  ```
  `part_code` is a user-controlled form string. While hyphens are replaced, path separators (`/` and `\`) and directory traversal sequences (`..`) are not stripped or validated.
- **Why it is a problem**: 
  Passing `part_code = "../../some_dir/malicious"` allows the resolved path `dest_path` to escape `golden_dir`.
- **Impact**: 
  Arbitrary file write across the filesystem wherever the process user has write permissions.
- **Recommended fix**: 
  Sanitize `part_code` using a strict regex (e.g. `^[a-zA-Z0-9_-]+$`), or use `Path(dest_filename).name` and verify that `dest_path.resolve().is_relative_to(golden_dir.resolve())`.

---

### Issue 5.4: Unauthenticated Public Exposure of Static Uploads
- **Classification**: Security Risk
- **Severity**: High
- **Location**: `backend/app/main.py:90-98` (`app.mount("/static/uploads", ...)`)
- **Problem**: 
  `main.py` mounts `/static/uploads` and `/static/golden` directly using FastAPI's `StaticFiles`.
- **Why it is a problem**: 
  `StaticFiles` bypasses FastAPI route authentication dependencies. Anyone with network access can browse and download all uploaded inspection images and proprietary golden engineering reference designs without providing a JWT bearer token.
- **Impact**: 
  Severe confidentiality breach in corporate / OEM manufacturing environments where PCB schematics, serial markings, and part layouts are trade secrets or covered by NDAs.
- **Recommended fix**: 
  Serve static assets through authenticated streaming endpoints that verify `current_user` credentials, or use a reverse proxy (e.g. Nginx) with internal authentication subrequests (`X-Accel-Redirect`).

---

### Issue 5.5: Missing Authorization on Inspection Report Deletion
- **Classification**: Security Risk
- **Severity**: High
- **Location**: `backend/app/routers/reports.py:406-422` (`delete_report`)
- **Problem**: 
  `DELETE /api/v1/reports/{inspection_id}` depends only on `current_user: User = Depends(get_current_user)`. Any authenticated user with `OPERATOR` role can call this endpoint.
- **Why it is a problem**: 
  In an industrial quality assurance setting, operators should not have the authority to unilaterally delete audit reports or tamper with inspection records.
- **Impact**: 
  Malicious or negligent operators can delete failed inspections to hide defect rates or falsify compliance metrics.
- **Recommended fix**: 
  Enforce admin-only authorization: `_user: User = Depends(require_roles(UserRole.ADMIN))`.

---

### Issue 5.6: Stateless Refresh Tokens Without Revocation Mechanism
- **Classification**: Security Risk | Missing Hardening
- **Severity**: Medium
- **Location**: `backend/app/core/security.py:46-53` & `backend/app/routers/auth.py:74-112` (`refresh_token`)
- **Problem**: 
  Refresh tokens are issued as stateless JWTs valid for 7 days. There is no database table, revocation store, or token-family tracking for issued refresh tokens.
- **Why it is a problem**: 
  If a user's token is compromised, logging out or changing a password cannot revoke the active refresh token. It remains valid for 7 days unless the user's account is explicitly marked `is_active = False`.
- **Impact**: 
  An attacker who obtains a refresh token retains persistence even after user session termination.
- **Recommended fix**: 
  Store refresh token IDs (jti) in a database table or Redis cache with rotation and revocation on logout.

---

### Issue 5.7: File Extension-Only Validation Without Magic Byte Inspection
- **Classification**: Security Risk | Missing Hardening
- **Severity**: Medium
- **Location**: `backend/app/utils/file_utils.py:13-26` (`validate_image_extension`)
- **Problem**: 
  `validate_image_extension` checks only the file extension suffix in the filename (`.jpg`, `.jpeg`, `.png`). It does not verify the initial magic bytes of the file content.
- **Why it is a problem**: 
  A non-image file (e.g. HTML with script tags, shell scripts, or binary executables) can be uploaded with a `.png` extension.
- **Impact**: 
  When served statically via `/static/uploads`, this can lead to stored Cross-Site Scripting (XSS) or mime-sniffing vulnerabilities in browser clients.
- **Recommended fix**: 
  Inspect the first 32 bytes of uploaded files using `python-magic` or verify headers with Pillow (`Image.open(buf).verify()`) before saving.

---

## 6. Factory Edge Server & Operational Reliability

### Issue 6.1: Stuck Inspections Following Process Crash or Power Loss [RESOLVED]
- **Classification**: Edge-Deployment Risk | Actual Bug
- **Severity**: Critical
- **Status**: ✅ **RESOLVED**
- **Location**: `backend/app/main.py:50-61` (`lifespan`)
- **Resolution**: 
  In `main.py`'s `lifespan` startup hook, an automated reconciliation query runs immediately after database initialization:
  `UPDATE inspections SET status = 'failed', error_message = 'Pipeline execution interrupted by server restart or power loss' WHERE status IN ('pending', 'processing')`.
  Any dangling background pipeline tasks killed by host restarts, container crashes, or power disruptions are promptly marked as failed, unblocking the dashboard and allowing operators to immediately re-inspect boards.

---

### Issue 6.2: External Network Probing Fails in Air-Gapped / Isolated OT Networks
- **Classification**: Edge-Deployment Risk
- **Severity**: Medium
- **Location**: `backend/app/routers/system.py:20-33` (`_get_lan_ip`)
- **Problem**: 
  `_get_lan_ip()` probes an external internet IP `("8.8.8.8", 80)` via UDP socket to determine the local machine's LAN IP address.
- **Why it is a problem**: 
  Edge manufacturing environments are often deployed on air-gapped Operational Technology (OT) networks with strict egress firewalls and no default route to public DNS (8.8.8.8).
- **Impact**: 
  The socket connection fails or raises an error, falling back to `"localhost"`. When mobile tablet inspection stations scan the QR code to pair with the server, the QR code contains `http://localhost:5173`, making it unreachable from external tablets on the LAN.
- **Recommended fix**: 
  Allow the LAN IP or hostname to be explicitly configured via `settings.HOST_IP` or `settings.BASE_URL`, falling back to standard interface enumeration (`netifaces` or scanning non-loopback network interfaces).

---

### Issue 6.3: Unhandled External Cloud AI Dependency in Edge Deployments
- **Classification**: Edge-Deployment Risk | Architecture Weakness
- **Severity**: Medium
- **Location**: `backend/app/core/config.py:40-52` & `backend/app/shared/llm_client.py:270-385`
- **Problem**: 
  The system architecture relies on cloud LLM APIs (Gemini and Groq) for Stage 7 (AI Judge) and Stage 5d (VLM). If `GEMINI_API_KEY` or `GROQ_API_KEY` is configured on an edge appliance with an unstable or intermittent factory internet uplink, requests will repeatedly incur retry backoffs (up to 8 seconds each) before falling back.
- **Why it is a problem**: 
  Industrial edge inspection lines require deterministic cycle times (< 4 seconds per unit). Repeated network timeouts and retries blow through cycle time budgets.
- **Impact**: 
  Inspection throughput on the production line degrades significantly when cloud internet connectivity drops.
- **Recommended fix**: 
  Introduce an explicit `settings.OFFLINE_MODE = True` flag that bypasses all cloud API calls immediately without attempting retries, routing directly to local OpenCLIP, local YOLO, and rule-based deterministic judge evaluation.

---

### Issue 6.4: Basic Logging Without Log Rotation or Structural Observability
- **Classification**: Edge-Deployment Risk | Missing Hardening
- **Severity**: Low
- **Location**: `backend/app/main.py:17-20` (`logging.basicConfig`)
- **Problem**: 
  Logging is configured via standard `logging.basicConfig(level=logging.INFO)` outputting plain text to stdout. There is no file logging, size rotation (`RotatingFileHandler`), or structured JSON logging.
- **Why it is a problem**: 
  When running directly on edge servers or inside Docker containers without external log aggregators, container stdout logs can grow unbounded until the disk fills up.
- **Impact**: 
  Disk exhaustion from unrotated container logs and difficulty parsing events during post-incident investigations.
- **Recommended fix**: 
  Configure a `RotatingFileHandler` with a maximum size (e.g. 50MB) and backup count (e.g. 5 files), or configure Docker's `json-file` log driver with `max-size: "50m"`.

---

## 7. Priority Action Matrix (Top 10 Remediations)

The ten most urgent issues ranked by real-world operational and security severity, along with current resolution status:

1. **Privilege Escalation on Open Registration (`POST /auth/register`)**
   - *Fix*: Remove `role` from `UserRegister`; force new accounts to `OPERATOR`.
2. **Missing Verdict in Live SSE Final Stream (`/inspections/{id}/events`)** — ✅ **RESOLVED**
   - *Fix*: Standardized in-memory completion payload to pass `verdict` and `policy_action` preventing blank frontend HUD cards.
3. **Catastrophic In-Memory SQLite Fallback (`sqlite+aiosqlite:///:memory:`)**
   - *Fix*: Require a persistent file path (`data/visionforge.db`) instead of ephemeral in-memory databases with `NullPool`.
4. **Stuck "PROCESSING" Inspections Across Server Restarts** — ✅ **RESOLVED**
   - *Fix*: Executed startup reconciliation query in `lifespan` that marks interrupted inspections as `failed`.
5. **Event Loop Freezing from Synchronous Forensics (ELA / Copy-Move)** — ✅ **RESOLVED**
   - *Fix*: Extracted synchronous algorithms and offloaded CPU-heavy CV computations to `asyncio.to_thread`.
6. **VLM Concurrency Rate Limit Storm (Stage 5)** — ✅ **RESOLVED**
   - *Fix*: Throttled VLM calls via `get_vlm_semaphore(2)` with 50/50 round-robin Groq/Gemini load balancing and offline fallback.
7. **Unbounded RAM Leak in WorkingMemory & EvidenceStore** — ✅ **RESOLVED**
   - *Fix*: Implemented bounded capacity and LRU eviction policies across `WorkingMemoryRegistry` and `EvidenceStore`.
8. **Unauthenticated Public Access to Static Uploads (`/static/uploads`)**
   - *Fix*: Protect image delivery routes behind JWT bearer token checks.
9. **Path Traversal in Golden Reference Upload**
   - *Fix*: Sanitize `part_code` with strict regex and enforce path confinement.
10. **Storage Leak from Orphaned Images & PDFs on Record Deletion**
    - *Fix*: Add `shutil.rmtree()` and `unlink()` handlers to inspection and reference deletion routes.
