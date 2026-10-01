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

### Issue 1.1: Event Loop Starvation from Synchronous Computer Vision Algorithms
- **Classification**: Actual Bug | Architecture Weakness | Edge-Deployment Risk
- **Severity**: High
- **Location**: `backend/app/pipeline/stages/authenticity.py:113-352` (`_compute_ela`, `_detect_screenshot`, `_check_noise_consistency`, `_detect_copy_move`)
- **Problem**: 
  Forensic functions `_compute_ela()`, `_detect_screenshot()`, `_check_noise_consistency()`, and `_detect_copy_move()` are declared as `async def`, but contain purely CPU-intensive, synchronous operations: Pillow image re-saving, OpenCV contour discovery (`cv2.findContours`), Laplacian standard deviations, and nested $O(N \times M)$ block-comparison loops over raw NumPy pixel arrays. They never yield control (`await asyncio.sleep(0)`) or offload to a worker pool (`asyncio.to_thread` / `run_in_executor`).
- **Why it is a problem**: 
  In Python's `asyncio`, an `async def` function executes on the main thread's event loop. When a CPU-heavy algorithm executes synchronously inside `async def`, the entire Python process freezes until computation finishes.
- **Impact**: 
  While processing high-resolution inspection images (especially copy-move detection on multi-megapixel uploads), the entire FastAPI server halts. Concurrent HTTP requests, health checks (`/health`), SSE telemetry streams (`/events`), and database connection pools freeze or time out.
- **Recommended fix**: 
  Declare these computational functions as standard synchronous functions (`def`), and call them from the stage runner using `await asyncio.to_thread(_compute_ela, image_path)` or a dedicated `concurrent.futures.ProcessPoolExecutor` to isolate heavy computer vision algorithms from the web server event loop.

---

### Issue 1.2: Event Loop Blocking from Synchronous HTTP Network Requests
- **Classification**: Actual Bug | Architecture Weakness
- **Severity**: High
- **Location**: `backend/app/services/embedding_service.py:108` (`_generate_gemini_embedding`)
- **Problem**: 
  `_generate_gemini_embedding()` executes an external HTTP POST request using the synchronous `requests` library (`requests.post(url, json=payload, timeout=timeout)`) instead of an asynchronous HTTP client like `httpx.AsyncClient`.
- **Why it is a problem**: 
  `requests.post` blocks the running thread during DNS resolution, TLS handshake, and remote HTTP server response (with a timeout of up to 6.0 seconds).
- **Impact**: 
  If the Gemini API is slow or experiencing packet loss, the entire backend event loop hangs for up to 6 seconds per inspection image, causing systemic latency spikes across all API routes.
- **Recommended fix**: 
  Replace `requests.post()` with an asynchronous call using `httpx.AsyncClient().post()`, or reuse the shared `httpx.AsyncClient` from `LLMClient`.

---

### Issue 1.3: Unbounded In-Memory State Retention (WorkingMemory & EvidenceStore Heap Leak)
- **Classification**: Architecture Weakness | Edge-Deployment Risk
- **Severity**: High
- **Location**: `backend/app/shared/memory.py:176-204` (`WorkingMemoryRegistry`) & `backend/app/shared/evidence_store.py:51-140` (`EvidenceStore`)
- **Problem**: 
  `WorkingMemoryRegistry._store` is a Python dictionary `dict[UUID, WorkingMemory]` mapping inspection IDs to full in-memory working memory objects (including full stage histories, ROI plans, JSON dumps, and strings). `release(inspection_id)` is never called in production code (it is only invoked in two unit test files). Similarly, `EvidenceStore._by_inspection` and `_by_id` store every `EvidenceRecord` indefinitely, and `clear_inspection()` explicitly raises `EvidenceImmutableError`.
- **Why it is a problem**: 
  Every inspection processed by the server permanently leaks memory into global dictionary singletons.
- **Impact**: 
  On an edge server processing continuous inspections on a manufacturing line over days or weeks, RAM usage steadily climbs until the Linux kernel OOM (Out Of Memory) killer terminates the backend process.
- **Recommended fix**: 
  Implement an LRU or TTL eviction policy (e.g., retaining only the last 50 inspections in RAM or evicting 1 hour after pipeline completion), relying directly on PostgreSQL/SQLite persistence for historical retrieval.

---

### Issue 1.4: Redundant Model Instantiations in Evidence Execution
- **Classification**: Architecture Weakness | Edge-Deployment Risk
- **Severity**: Medium
- **Location**: `backend/app/pipeline/stages/evidence_execution.py:49-56, 343` (`get_default_agent_registry`)
- **Problem**: 
  In `run_evidence_execution()`, line 343 evaluates: `registry = agent_registry if agent_registry is not None else get_default_agent_registry()`. `get_default_agent_registry()` creates new instances of `StructuralAgent`, `OCRAgent`, `LabelAgent`, and `VLMAgent` on every single execution run. In `OCRAgent`, this invokes `easyocr.Reader(gpu=False)` and checks PaddleOCR. In `StructuralAgent`, it loads YOLO PyTorch weights from disk.
- **Why it is a problem**: 
  Heavy neural network runtimes should be loaded as long-lived singletons or process-level workers, not reinstantiated on every pipeline invocation.
- **Impact**: 
  Significant per-inspection CPU/memory thrashing and latency overhead during agent initialization, leading to intermittent spikes in memory allocation.
- **Recommended fix**: 
  Initialize the agent registry as a module-level singleton or load models during the application `lifespan` startup hook, injecting pre-warmed agent singletons into the execution stage.

---

### Issue 1.5: Unreleased Resources on Application Shutdown (`shutdown_llm_client`)
- **Classification**: Technical Debt | Missing Hardening
- **Severity**: Low
- **Location**: `backend/app/main.py:53-58` (`lifespan`) & `backend/app/shared/llm_client.py:982-987` (`shutdown_llm_client`)
- **Problem**: 
  `shutdown_llm_client()` is defined in `llm_client.py` to close the underlying persistent `httpx.AsyncClient` pool cleanly, but `main.py`'s `lifespan` shutdown handler only executes `await engine.dispose()`, neglecting to call `shutdown_llm_client()`.
- **Why it is a problem**: 
  HTTP connection pools and underlying sockets remain open during shutdown until forcefully terminated by the OS.
- **Impact**: 
  Resource leakage and socket warnings (`unclosed client session`) during backend restarts or graceful shutdown signals.
- **Recommended fix**: 
  Call `await shutdown_llm_client()` inside the shutdown phase of the FastAPI `lifespan` context manager in `backend/app/main.py`.

---

### Issue 1.6: PaddleOCR Imported Without Dependency Entry
- **Classification**: Technical Debt | Documentation Inconsistency
- **Severity**: Low
- **Location**: `backend/app/pipeline/agents/ocr_agent.py:20-25`
- **Problem**: 
  The OCR agent attempts to import PaddleOCR first and falls back to EasyOCR if the import fails. PaddleOCR is not listed in `backend/requirements.txt`, meaning in any standard deployment PaddleOCR is absent and the fallback silently runs every time.
- **Recommended fix**: 
  Either declare PaddleOCR in `requirements.txt` or standardize EasyOCR as the explicit, unified OCR engine and remove dead PaddleOCR import logic.

---

## 2. API & Backend Routing

### Issue 2.1: Live Progress Stream Missing Final Verdict in In-Memory Generator
- **Classification**: Actual Bug | Frontend Blocker
- **Severity**: Medium
- **Location**: `backend/app/routers/inspections.py:241-246`
- **Problem**: 
  When an inspection finishes, the SSE endpoint `GET /api/v1/inspections/{id}/events` checks the in-memory state. When `prog.get("status") in ("completed", "failed")`, it builds:
  ```python
  final_payload = {
      "event": "verdict",
      "status": prog.get("status"),
      "inspection_id": str(inspection_id),
      "detail": prog.get("detail"),
  }
  ```
  It completely omits `verdict` and `policy_action`! (Notice that the database fallback branch at lines 257-264 *does* include them).
- **Why it is a problem**: 
  The frontend listens for the `verdict` SSE event and reads `data.verdict` and `data.policy_action`. When resolving from the standard in-memory path, both fields are `undefined`, causing the HUD to show a blank result card instead of the Crimson/Emerald verdict banner.
- **Recommended fix**: 
  Standardize the final payload dictionary in both branches to always include `verdict: prog.get("verdict")` and `policy_action: prog.get("policy_action")`.

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

### Issue 2.8: Desktop Guard Modal LAN IP Fallback Returns 401 Unauthorized
- **Classification**: Actual Bug | Mobile Intake Handoff
- **Severity**: Medium
- **Location**: `frontend/src/components/inspection/DesktopGuardModal.jsx:38` & `backend/app/routers/system.py:36`
- **Problem**: 
  `DesktopGuardModal.jsx` executes a bare `fetch('/api/v1/system/network')` without passing a JWT bearer token. `GET /api/v1/system/network` requires `Depends(get_current_user)`.
- **Why it is a problem**: 
  The request fails with HTTP 401 Unauthorized. The modal then falls back to `window.location.href` (`localhost:5173`), generating an unreachable QR code for smartphones on the factory Wi-Fi.
- **Recommended fix**: 
  Use the authenticated `apiClient` or make `GET /api/v1/system/network` a public endpoint (since returning the LAN IP of the dev machine carries no sensitive data).

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

### Issue 4.1: Stage 5 VLM Concurrency Storm Hits Free-Tier Rate Limits (429)
- **Classification**: Operational Bottleneck | Reliability
- **Severity**: High
- **Location**: `backend/app/pipeline/stages/evidence_execution.py:404-446`
- **Problem**: 
  In Step 6 of `evidence_execution.py`, the stage queries all structural ROIs and simultaneously blasts multimodal calls to cloud models (Gemini 2.5 Flash / Groq Qwen 27B) using `asyncio.gather(*vlm_tasks)`.
- **Why it is a problem**: 
  Groq free tier limits Qwen 27B Vision to ~30 RPM, and Gemini free tier has a 15 RPM cap. If an inspection board contains 5 structural components, 5 VLM calls fire in the same second, exhausting free quotas in 1–2 inspections.
- **Impact**: 
  Operators encounter immediate `429 Too Many Requests` errors on subsequent inspections.
- **Recommended fix**: 
  1. Only run VLM validation on ROIs where YOLO or SSIM reported an anomaly, drift, or low confidence (selective VLM).
  2. Throttle concurrent VLM calls with a dedicated semaphore (`asyncio.Semaphore(2)`).

---

### Issue 4.2: Concurrency & GPU Memory Exhaustion from Unpooled Model Inference
- **Classification**: Architecture Weakness | Edge-Deployment Risk
- **Severity**: High
- **Location**: `backend/app/pipeline/stages/evidence_execution.py:352-383` (`run_evidence_execution`)
- **Problem**: 
  In `run_evidence_execution()`, tasks within a batch execute concurrently using `asyncio.gather(*tasks)` bounded only by an in-flight semaphore of 4. However, if multiple inspections are submitted at the same time, each inspection creates its own semaphore. If 3 inspections run concurrently, 12 concurrent ML agent tasks run in parallel.
- **Why it is a problem**: 
  Edge servers typically have constrained GPU VRAM (e.g., 8GB–16GB on an NVIDIA RTX/Orin) or CPU cores. Concurrently invoking multiple PyTorch/YOLO/OCR tasks across threads triggers CUDA Out-Of-Memory errors.
- **Impact**: 
  The process crashes with `CUDA out of memory`, failing all active inspections.
- **Recommended fix**: 
  Implement a global process-wide queue or global concurrency semaphore for GPU/neural model inference (e.g., `MAX_CONCURRENT_INFERENCES = 2`), shared across all active inspections.

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

### Issue 4.4: Rigid Hardcoded Anomaly Scoring in Evidence Fusion
- **Classification**: Architecture Weakness
- **Severity**: Low
- **Location**: `backend/app/pipeline/stages/evidence_fusion.py:136-140` (`_extract_agent_anomaly_score`)
- **Problem**: 
  In `evidence_fusion.py`, `missing_components` returns a hardcoded anomaly score of `0.95` and `extra_components` returns `0.90`, regardless of which component is affected (e.g., a critical microprocessor vs an optional jumper or unpopulated debug header).
- **Why it is a problem**: 
  Different PCB components carry different risk profiles in industrial manufacturing.
- **Impact**: 
  An unpopulated non-critical capacitor triggers the same severe fraud probability as a missing primary IC.
- **Recommended fix**: 
  Incorporate component weights from `ROITemplate.regions[i].critical` or `severity` attributes to calculate proportional anomaly scores.

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

### Issue 6.1: Stuck Inspections Following Process Crash or Power Loss
- **Classification**: Edge-Deployment Risk | Actual Bug
- **Severity**: Critical
- **Location**: `backend/app/main.py:26-58` (`lifespan`) & `backend/app/routers/inspections.py:43-60` (`_run_pipeline_background`)
- **Problem**: 
  When an inspection starts, its database status is set to `PENDING` and then `PROCESSING` inside an in-process `BackgroundTasks` runner. If the edge server suffers a power failure, kernel crash, or Docker restart while an inspection is running, the in-process task dies. Upon restart, `main.py` has no reconciliation logic to inspect the database for incomplete inspections.
- **Why it is a problem**: 
  The database status of interrupted inspections remains `PROCESSING` or `PENDING` indefinitely.
- **Impact**: 
  Factory operators see inspections permanently stuck in "Processing" on the frontend dashboard. Reports cannot be generated or approved for those cases.
- **Recommended fix**: 
  In `main.py`'s `lifespan` startup hook, execute a recovery query:
  `UPDATE inspections SET status = 'failed', error_message = 'Process terminated unexpectedly during inspection' WHERE status IN ('pending', 'processing')`.

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

The ten most urgent issues to remediate for production-readiness, ranked by real-world operational and security severity:

1. **Privilege Escalation on Open Registration (`POST /auth/register`)**
   - *Fix*: Remove `role` from `UserRegister`; force new accounts to `OPERATOR`.
2. **Missing Verdict in Live SSE Final Stream (`/inspections/{id}/events`)**
   - *Fix*: Pass `verdict` and `policy_action` in in-memory completion payload to prevent blank frontend cards.
3. **Catastrophic In-Memory SQLite Fallback (`sqlite+aiosqlite:///:memory:`)**
   - *Fix*: Require a persistent file path (`data/visionforge.db`) instead of ephemeral in-memory databases with `NullPool`.
4. **Stuck "PROCESSING" Inspections Across Server Restarts**
   - *Fix*: Add a startup reconciliation query in `lifespan` that marks interrupted inspections as `failed`.
5. **Event Loop Freezing from Synchronous Forensics (ELA / Copy-Move)**
   - *Fix*: Offload CPU-heavy CV algorithms to `asyncio.to_thread`.
6. **VLM Concurrency Rate Limit Storm (Stage 5)**
   - *Fix*: Run VLM only on suspicious/anomalous ROIs instead of all structural ROIs; add a concurrency semaphore.
7. **Unbounded RAM Leak in WorkingMemory & EvidenceStore**
   - *Fix*: Implement an LRU eviction cache for in-memory registries to avoid edge OOM crashes.
8. **Unauthenticated Public Access to Static Uploads (`/static/uploads`)**
   - *Fix*: Protect image delivery routes behind JWT bearer token checks.
9. **Path Traversal in Golden Reference Upload**
   - *Fix*: Sanitize `part_code` with strict regex and enforce path confinement.
10. **Storage Leak from Orphaned Images & PDFs on Record Deletion**
    - *Fix*: Add `shutil.rmtree()` and `unlink()` handlers to inspection and reference deletion routes.
