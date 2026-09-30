# VisionForge Backend Comprehensive Engineering & Security Audit

This document provides a systematic, code-verified audit of the **VisionForge backend repository**. Every reported issue is identified directly from the active codebase with verified file locations, impact analysis, and specific remediation guidelines.

---

## 1. Architecture & Code Quality

### Issue 1.1: Event Loop Starvation from Synchronous Computer Vision & Forensic Algorithms
- **Classification**: Actual Bug | Architecture Weakness | Edge-Deployment Risk
- **Severity**: High
- **Location**: `backend/app/pipeline/stages/authenticity.py:113-352` (`_compute_ela`, `_detect_screenshot`, `_check_noise_consistency`, `_detect_copy_move`)
- **Problem**: 
  Forensic functions `_compute_ela()`, `_detect_screenshot()`, `_check_noise_consistency()`, and `_detect_copy_move()` are declared as `async def`, but contain purely CPU-intensive, synchronous operations: Pillow image re-saving, OpenCV contour discovery (`cv2.findContours`), Laplacian standard deviations, and nested O(N×M) block-comparison loops over raw NumPy pixel arrays. They do not yield control (`await asyncio.sleep(0)`) or offload to a worker pool (`asyncio.to_thread` / `run_in_executor`).
- **Why it is a problem**: 
  In Python's `asyncio`, an `async def` function runs on the main thread's event loop. When a CPU-heavy algorithm executes synchronously inside `async def`, the entire Python process freezes until computation finishes.
- **Impact**: 
  While processing high-resolution inspection images (especially copy-move detection on multi-megapixel uploads), the entire FastAPI server halts. Concurrent HTTP requests, health checks (`/health`), WebSockets, SSE stage streams (`/events`), and database connection keeps-alive will freeze or time out.
- **Recommended fix**: 
  Declare these computational functions as standard synchronous functions (`def`), and call them from the stage runner using `await asyncio.to_thread(_compute_ela, image_path)` or a dedicated `concurrent.futures.ProcessPoolExecutor` to isolate heavy computer vision algorithms from the web server event loop.

---

### Issue 1.2: Event Loop Blocking from Synchronous HTTP Network Requests
- **Classification**: Actual Bug | Architecture Weakness
- **Severity**: High
- **Location**: `backend/app/services/embedding_service.py:108` (`_generate_gemini_embedding`)
- **Problem**: 
  `_generate_gemini_embedding()` makes an external HTTP POST request using the synchronous `requests` library (`requests.post(url, json=payload, timeout=timeout)`) instead of an asynchronous HTTP client like `httpx.AsyncClient`.
- **Why it is a problem**: 
  `requests.post` is completely synchronous and blocks the thread while waiting for DNS resolution, TLS handshake, and remote HTTP server response (with a timeout of up to 6.0 seconds).
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
  Every inspection processed by the server permanently leaks memory into the global dictionary singletons.
- **Impact**: 
  On an edge server processing continuous inspections on a manufacturing line over days or weeks, RAM usage steadily climbs until the Linux kernel OOM (Out Of Memory) killer kills the backend process.
- **Recommended fix**: 
  Implement an LRU or time-to-live (TTL) eviction policy (e.g. keeping only the last 100 inspections in RAM or evicting 1 hour after pipeline completion), or rely directly on PostgreSQL/SQLite persistence rather than holding all historical records in process memory.

---

### Issue 1.4: Redundant Model Instantiations in Evidence Execution
- **Classification**: Architecture Weakness | Edge-Deployment Risk
- **Severity**: Medium
- **Location**: `backend/app/pipeline/stages/evidence_execution.py:49-56, 343` (`get_default_agent_registry`)
- **Problem**: 
  In `run_evidence_execution()`, line 343 evaluates: `registry = agent_registry if agent_registry is not None else get_default_agent_registry()`. `get_default_agent_registry()` creates new instances of `StructuralAgent`, `OCRAgent`, `LabelAgent`, and `VLMAgent` on every single execution run. In `OCRAgent`, this invokes `easyocr.Reader(gpu=False)` and checks PaddleOCR. In `StructuralAgent`, it loads YOLO PyTorch weights.
- **Why it is a problem**: 
  Heavy ML models and neural network runtimes should be loaded as long-lived singletons or process-level workers, not reinstantiated on every pipeline invocation.
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

## 2. API & Backend

### Issue 2.1: [RESOLVED] Closed Database Session Used in Long-Lived StreamingResponse (SSE Generator Crash)
- **Status**: ✅ **Resolved** (Fixed in `routers/inspections.py`: Removed injected `db` dependency from `stream_inspection_events`; generator now instantiates short-lived sessions via `AsyncSessionLocal()` and emits periodic keep-alive pings).
- **Classification**: Actual Bug
- **Severity**: Critical
- **Location**: `backend/app/routers/inspections.py:220-284` (`stream_inspection_events`)
- **Problem**: 
  The SSE endpoint `GET /api/v1/inspections/{inspection_id}/events` injects `db: AsyncSession = Depends(get_db)`. In FastAPI, `get_db` is an async generator with `finally: await session.close()`. The route handler returns a `StreamingResponse(event_generator())`. FastAPI exits the dependency context as soon as the `StreamingResponse` object is returned, causing `session.close()` to execute immediately. When `event_generator()` later executes line 251: `result = await db.execute(select(Inspection)...)`, it operates on a closed session.
- **Why it is a problem**: 
  SQLAlchemy sessions cannot execute queries once closed.
- **Impact**: 
  Whenever an inspection's in-memory state is missing or already purged (e.g. status polling after initial intake or fallback to database query), the SSE stream throws `sqlalchemy.exc.InvalidRequestError: Cannot use session after close` or `InterfaceError`, breaking live frontend event streaming.
- **Recommended fix**: 
  Do not inject `db` as a request dependency into `stream_inspection_events`. Instead, use `db_session_ctx()` or instantiate a dedicated short-lived session inside the generator loop only when a database read is required.

---

### Issue 2.2: Missing Authentication on Real-Time Stage Event Stream
- **Classification**: Security Risk | Actual Bug
- **Severity**: High
- **Location**: `backend/app/routers/inspections.py:220` (`stream_inspection_events`)
- **Problem**: 
  Unlike all other inspection endpoints (`get_inspection`, `list_inspections`, `get_inspection_status`), `GET /api/v1/inspections/{inspection_id}/events` does not include `current_user: User = Depends(get_current_user)`.
- **Why it is a problem**: 
  Any client on the local network that knows or scans for an inspection UUID can connect to the event stream without an authorization header.
- **Impact**: 
  Unauthenticated disclosure of live inspection telemetry, detailed forensic findings, error logs, and fraud verdicts.
- **Recommended fix**: 
  Add `current_user: User = Depends(get_current_user)` to `stream_inspection_events` (or support token verification via query parameter if EventSource browser clients cannot send Authorization headers).

---

### Issue 2.3: Unbounded File Uploads (No Maximum File Size Limit / DoS Risk)
- **Classification**: Security Risk | Edge-Deployment Risk
- **Severity**: High
- **Location**: `backend/app/routers/inspections.py:62-105` (`create_inspection`) & `backend/app/utils/file_utils.py:29-44` (`save_upload_file`)
- **Problem**: 
  `create_inspection` accepts up to 6 images via multipart form data. In `save_upload_file`, chunks are read and written to disk in a loop (`while chunk := await upload_file.read(DEFAULT_CHUNK_SIZE)`) with no maximum file size check or cumulative payload limit.
- **Why it is a problem**: 
  A malfunctioning camera stream or malicious user can send gigabyte-sized files in an upload request.
- **Impact**: 
  Can rapidly fill the host filesystem, resulting in disk exhaustion (`ENOSPC`), corrupting the local SQLite/PostgreSQL database, and crashing the host server.
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

## 3. Database & Storage

### Issue 3.1: In-Memory SQLite Fallback with NullPool Causes Immediate Data Loss and Table Missing Errors
- **Classification**: Actual Bug | Edge-Deployment Risk
- **Severity**: Critical
- **Location**: `backend/app/core/database.py:60-98` (`_build_engine`)
- **Problem**: 
  If the primary PostgreSQL connection fails or drivers are missing, `_build_engine()` falls back to `sqlite+aiosqlite:///:memory:` with `poolclass=NullPool`. In SQLite, an in-memory database (`:memory:`) with `NullPool` creates a completely new, empty in-memory database on every single connection/session checkout.
- **Why it is a problem**: 
  Tables created during `init_db()` in the startup connection are instantly destroyed when that connection closes. Subsequent API requests check out a new connection to a completely empty SQLite database.
- **Impact**: 
  Any API endpoint attempting to read or write data immediately throws `sqlite3.OperationalError: no such table: users` or `no such table: inspections`. If edge operators expect fallback operation, the system fails completely, and any transient data is lost on restart.
- **Recommended fix**: 
  If an edge deployment uses SQLite, specify a persistent disk path (e.g. `sqlite+aiosqlite:///data/visionforge.db`), or use `sqlite+aiosqlite:///:memory:?cache=shared` with a static pool if strictly in testing mode. Do not silently fallback to an ephemeral `:memory:` database in production/development without a persistent file backing.

---

### Issue 3.2: Orphaned Image and Report Files on Record Deletion
- **Classification**: Actual Bug | Edge-Deployment Risk
- **Severity**: High
- **Location**: `backend/app/routers/reports.py:406-422` (`delete_report`) & `backend/app/routers/products.py:144-166` (`delete_golden_reference`)
- **Problem**: 
  `delete_report` executes `await db.delete(inspection)` which deletes the database row and cascades to `evidence`, but does not delete the directory `data/inspection_uploads/<inspection_id>/` or the PDF file `inspection.report_path`. Similarly, `delete_golden_reference` deletes the `GoldenReference` row, but leaves `ref.image_path` on disk.
- **Why it is a problem**: 
  Filesystem storage and database state become inconsistent; disk files remain orphaned permanently.
- **Impact**: 
  On edge appliances with restricted disk space, deleting test or expired inspections from the UI does not free disk space, eventually leading to disk exhaustion.
- **Recommended fix**: 
  Add cleanup logic to delete the associated directory (`shutil.rmtree(inspection_dir, ignore_errors=True)`) and files (`Path(pdf_path).unlink(missing_ok=True)`) upon database record deletion.

---

### Issue 3.3: Incompatible Alembic Migration with Non-PostgreSQL Dialects
- **Classification**: Architecture Weakness | Technical Debt
- **Severity**: Medium
- **Location**: `backend/migrations/versions/001_initial_tables.py:19-115` (`upgrade`)
- **Problem**: 
  The initial Alembic migration explicitly imports and uses PostgreSQL-specific types: `postgresql.UUID(as_uuid=True)`, `postgresql.ARRAY(sa.String())`, `postgresql.JSONB()`, and PostgreSQL enum types.
- **Why it is a problem**: 
  If an edge installation runs on SQLite (or if migrations are executed against SQLite during testing or edge setups), Alembic fails with syntax and dialect errors because `postgresql.ARRAY` and PostgreSQL enum types are unsupported in SQLite.
- **Impact**: 
  Database migrations cannot run on SQLite-based edge servers, breaking continuous deployment and automated schema upgrades.
- **Recommended fix**: 
  Use SQLAlchemy cross-dialect abstractions (such as `.with_variant()`, generic `sa.JSON()`, and `sa.String()` for UUIDs/arrays on SQLite) in migration files, matching the models in `app/models/`.

---

### Issue 3.4: Dual Schema Creation (Base.metadata.create_all Bypassing Alembic)
- **Classification**: Technical Debt | Architecture Weakness
- **Severity**: Low
- **Location**: `backend/app/core/database.py:169-171` (`init_db`)
- **Problem**: 
  `init_db()` invokes `await conn.run_sync(Base.metadata.create_all)` on every application startup.
- **Why it is a problem**: 
  `create_all` creates database tables without writing an initial revision record to Alembic's `alembic_version` table.
- **Impact**: 
  Running `alembic upgrade head` on an existing database will fail with table-already-exists errors, preventing clean migration workflows in production environments.
- **Recommended fix**: 
  Use Alembic as the single source of truth for database schema management, or run programmatic migrations (`alembic.command.upgrade`) during startup rather than raw `create_all`.

---

### Issue 3.5: Missing Composite Database Indexes for Filtered Queries
- **Classification**: Architecture Weakness | Technical Debt
- **Severity**: Low
- **Location**: `backend/app/models/inspection.py:60-142` (`Inspection`)
- **Problem**: 
  The `inspections` table has single-column indexes on `vendor_id`, `status`, and `created_at`, but lacks composite indexes for common filter combinations: `(created_by, created_at)` used by operator RBAC queries and `(vendor_id, status)` used by inspection list filtering.
- **Why it is a problem**: 
  The database planner must perform index scans followed by filter steps or table scans as data volume grows.
- **Impact**: 
  Slow response times for inspection listing and analytics dashboards on large datasets.
- **Recommended fix**: 
  Define `__table_args__` on `Inspection` with composite indexes:
  `Index("ix_inspections_created_by_created_at", "created_by", "created_at")` and `Index("ix_inspections_vendor_status", "vendor_id", "status")`.

---

## 4. AI / CV Pipeline

### Issue 4.1: [RESOLVED] Vector Dimension Mismatch Crash During Cloud-to-Local Fallback
- **Status**: ✅ **Resolved** (Fixed in `stages/reference_match.py`: Query vectors now use `generate_embedding_for_index()`, matching the active index space, and unhandled dimension mismatch exceptions are caught cleanly to flag for review).
- **Classification**: Actual Bug | Edge-Deployment Risk
- **Severity**: High
- **Location**: `backend/app/pipeline/stages/reference_match.py:59, 73` (`run_reference_match`) & `backend/app/services/embedding_service.py:122-138, 291-300` (`generate_embedding`, `search`)
- **Problem**: 
  In `reference_match.py`, the query vector is generated using `embedding_service.generate_embedding()`, which attempts to call Gemini (dim=3072) and falls back to OpenCLIP (dim=512) on failure. If the FAISS index was previously built using Gemini (dim=3072), but Gemini subsequently times out or is unreachable, `generate_embedding()` returns a 512-dimensional vector. When `embedding_service.search(query_embedding)` is called, `self._validate_dim()` raises an `EmbeddingDimensionMismatch` exception. Line 73 in `reference_match.py` is outside the try/except block.
- **Why it is a problem**: 
  The exception is unhandled and immediately causes Stage 3 to crash.
- **Impact**: 
  An intermittent network hiccup to Gemini will not cleanly degrade to local search; it causes an unhandled exception that fails the entire inspection pipeline.
- **Recommended fix**: 
  In `reference_match.py`, generate embeddings using `embedding_service.generate_embedding_for_index()`, which guarantees that the generated embedding matches the dimension of the currently loaded index. Catch `EmbeddingDimensionMismatch` in `run_reference_match` and degrade gracefully to manual review.

---

### Issue 4.2: Concurrency & GPU Memory Exhaustion from Unpooled Model Inference
- **Classification**: Architecture Weakness | Edge-Deployment Risk
- **Severity**: High
- **Location**: `backend/app/pipeline/stages/evidence_execution.py:352-383` (`run_evidence_execution`)
- **Problem**: 
  In `run_evidence_execution()`, tasks within a batch are executed concurrently using `asyncio.gather(*tasks)` bounded only by a local `asyncio.Semaphore(4)`. However, if multiple inspections are submitted at the same time, each inspection creates its own semaphore of 4. If 3 inspections run concurrently, 12 concurrent ML agent tasks run in parallel.
- **Why it is a problem**: 
  Edge servers typically have constrained GPU VRAM (e.g. 8GB-16GB on an NVIDIA RTX/Orin) or CPU cores. Concurrently invoking multiple PyTorch/YOLO/OCR inference tasks across threads triggers CUDA Out-Of-Memory errors or massive CPU context switching.
- **Impact**: 
  The process crashes with `CUDA out of memory` or `RuntimeError: DataLoader worker killed by signal`, failing all in-flight inspections.
- **Recommended fix**: 
  Implement a global process-wide queue or global concurrency semaphore for GPU/neural model inference (e.g. `MAX_CONCURRENT_INFERENCES = 2`), shared across all active inspections.

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

## 5. Security

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

### Issue 5.4: Unauthenticated Public Exposure of Inspection Uploads and Golden Reference Images
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
  Serve static assets through authenticated streaming endpoints (e.g. `GET /api/v1/inspections/{id}/images/{image_name}`) that verify `current_user` credentials, or use a reverse proxy (e.g. Nginx) with internal authentication subrequests (`X-Accel-Redirect`).

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

## 6. Reliability for EDGE / SERVER Deployment

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
  Industrial edge inspection lines require deterministic cycle times (e.g. < 5 seconds per unit). Repeated network timeouts and retries blow through cycle time budgets.
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

## Top 10 Problems

The ten most critical problems in the VisionForge backend repository that should be prioritized for remediation:

1. **Privilege Escalation on Open Registration (`POST /auth/register`)**
   - *Location*: `backend/app/routers/auth.py:30-49`
   - *Risk*: Anyone on the network can create an administrator account by specifying `"role": "admin"` in the request body.
2. **Database Session Premature Close in SSE Stream (`/inspections/{id}/events`)**
   - *Location*: `backend/app/routers/inspections.py:220-284`
   - *Risk*: The dependency session closes when `StreamingResponse` returns, causing queries on the closed session during live streaming to crash.
3. **Catastrophic In-Memory SQLite Fallback (`sqlite+aiosqlite:///:memory:`)**
   - *Location*: `backend/app/core/database.py:60-98`
   - *Risk*: `NullPool` creates a new in-memory database on every connection; tables vanish immediately after startup and all data is lost.
4. **Stuck "PROCESSING" Inspections Across Server Restarts**
   - *Location*: `backend/app/main.py:26-58` & `backend/app/routers/inspections.py:43-60`
   - *Risk*: Inspections interrupted by server restart or power loss remain permanently in `PROCESSING` status with no startup recovery hook.
5. **Event Loop Blocking by Synchronous Computer Vision Algorithms**
   - *Location*: `backend/app/pipeline/stages/authenticity.py:113-352`
   - *Risk*: Heavy OpenCV/NumPy calculations run directly on the asyncio event loop, freezing all concurrent HTTP requests and health checks.
6. **Vector Dimension Mismatch Crash on Gemini -> OpenCLIP Fallback**
   - *Location*: `backend/app/pipeline/stages/reference_match.py:59, 73` & `backend/app/services/embedding_service.py:122-138`
   - *Risk*: When Gemini API fails, generating 512-dim vectors against a 3072-dim FAISS index throws an unhandled exception that aborts the pipeline.
7. **Unbounded Heap Leak in In-Memory WorkingMemory & EvidenceStore**
   - *Location*: `backend/app/shared/memory.py:176-204` & `backend/app/shared/evidence_store.py:51-140`
   - *Risk*: Every inspection permanently retains full stage histories and evidence records in memory, guaranteeing an eventual OOM crash on edge appliances.
8. **Unauthenticated Public Access to Inspection & Golden Images**
   - *Location*: `backend/app/main.py:90-98`
   - *Risk*: Static directories `/static/uploads` and `/static/golden` are mounted without authentication, exposing proprietary hardware designs and inspection photos.
9. **Path Traversal Vulnerability in Golden Reference Upload**
   - *Location*: `backend/app/routers/products.py:81-86`
   - *Risk*: Unsanitized `part_code` allowing `../` traversal enables arbitrary file creation outside the upload directory.
10. **Storage Leak from Orphaned Uploads & PDF Reports on Record Deletion**
    - *Location*: `backend/app/routers/reports.py:406-422` & `backend/app/routers/products.py:144-166`
    - *Risk*: Deleting inspection or product records removes DB rows but leaves image folders and PDF files on disk, leading to progressive disk exhaustion.

---

## Architectural Summary

### 1. What is genuinely broken
- **Real-Time Event Streaming**: The SSE endpoint `GET /api/v1/inspections/{id}/events` accesses a closed SQLAlchemy session whenever in-memory state is absent, throwing database errors during client polling.
- **Database Engine Fallback**: The automatic fallback in `database.py` to `sqlite+aiosqlite:///:memory:` with `NullPool` fails immediately because tables created in one connection do not exist in another connection.
- **Gemini-to-OpenCLIP Vector Dimension Failover**: A failure in the Gemini API returns a 512-dimension vector that causes an unhandled dimension mismatch crash in `FAISS` during Stage 3 search.
- **Privilege Escalation on User Registration**: `POST /api/v1/auth/register` blindly trusts the client-provided `role` field, permitting unauthenticated admin creation.

### 2. What is risky but functional
- **Asynchronous Execution of Synchronous CV**: OpenCV and NumPy forensic algorithms run inside `async def` functions on the main event loop. They work when processing a single inspection at low volume, but cause severe latency spikes and freeze concurrent connections.
- **In-Memory Registries**: `WorkingMemoryRegistry` and `EvidenceStore` function correctly for demo workflows and short test runs, but have no memory eviction or TTL policy, making them dangerous for long-running edge servers.
- **Static File Serving**: Serving images from `/static/uploads` functions well for the frontend UI, but provides zero access control or authorization.

### 3. What is missing for reliable company-edge deployment
- **Crash Recovery & Reconciliation**: A startup reconciliation process to detect inspections left in `pending` or `processing` states after a server reboot and mark them as failed or resume them.
- **Dedicated Offline Mode**: An operational setting to immediately bypass external cloud LLM/embedding APIs and operate purely with local OpenCLIP, YOLO, EasyOCR, and rule-based Judge logic.
- **Disk Storage Retention & Cleanup**: Automated pruning of old inspection images, deletion of files upon record removal, and upload file size caps.
- **Model Lifecycle Management**: Pre-warming and sharing singleton instances of PyTorch/YOLO/OCR models instead of reinstantiating them per execution.

### 4. What should be fixed before calling the backend production-ready
1. Restrict `/api/v1/auth/register` so only existing Admins can assign roles or create new accounts.
2. Fix the database session lifecycle in `/api/v1/inspections/{id}/events`.
3. Wrap all CPU-intensive image forensics and model predictions in `asyncio.to_thread`.
4. Ensure FAISS index queries are strictly guarded by `generate_embedding_for_index()`.
5. Add disk and file cleanup routines to report and product deletion endpoints.
6. Add an automatic startup recovery job in `lifespan` to clean up stuck inspections.
7. Enforce file upload size limits and magic-byte inspection.
