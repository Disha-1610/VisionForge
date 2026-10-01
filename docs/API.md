# REST API Reference

> This lists every HTTP endpoint the backend actually exposes.
> Checked against the code in September 2026.
> The fastest way to see the live list is <http://localhost:8000/docs> while the server is running.

**Base address:** `http://localhost:8000/api/v1`
**Interactive documentation:** `/docs` and `/redoc` (these are at the server root, not under `/api/v1`)

---

## Table of contents

1. [How the API is designed](#1-how-the-api-is-designed)
2. [Sending a login token](#2-sending-a-login-token)
3. [Error responses](#3-error-responses)
4. [Login and users - `/auth`](#4-login-and-users-auth)
5. [Inspections - `/inspections`](#5-inspections-inspections)
6. [Live progress stream](#6-live-progress-stream)
7. [Reference images - `/products`](#7-reference-images-products)
8. [Suppliers - `/vendors`](#8-suppliers-vendors)
9. [Reports - `/reports`](#9-reports-reports)
10. [Analytics - `/analytics`](#10-analytics-analytics)
11. [System - `/system` and root](#11-system-system-and-root)
12. [Routes people assume exist](#12-routes-people-assume-exist)

---

## 1. How the API is designed

An inspection takes a few seconds because it runs several AI models. If the browser had to wait
for one long request, the page would appear frozen, and if the connection dropped the whole
inspection would be lost.

So VisionForge splits intake from execution:

1. The operator uploads the photo. The server saves it, creates a database record, and replies
   immediately with a case number. This happens in well under a second.
2. The inspection runs in the background.
3. The frontend opens a separate live connection to watch progress.

This means a lost connection does not lose the inspection.

## 2. Sending a login token

All endpoints except registration, login, token refresh, the live stream, and the root health check
need a login token in the `Authorization` header:

```
Authorization: Bearer <your_access_token>
```

**Token lifetimes:**

- Access token: 30 minutes.
- Refresh token: 7 days. Send it to the refresh endpoint to get a new pair.

**Signing and hashing:**

- Tokens are signed with HS256.
- Passwords are hashed with bcrypt.

**The two roles, and what each can do:**

| Role | Can do |
|---|---|
| `operator` | Run inspections, view evidence, approve or override verdicts, download reports, see analytics for their own inspections |
| `admin` | Everything above, plus: create/edit/delete suppliers, upload and delete reference images, and see analytics for all operators |

Role values are lowercase in requests and responses: `"operator"` and `"admin"`.

**Two permissions worth flagging:**

- The registration endpoint accepts a `role` field, so anyone can register as an admin. This is a
  real bug. See [problems.md](../problems.md) issue 1.
- The live progress stream takes no token at all. Also a real bug. See issue 2.

## 3. Error responses

**The simple case.** The project's own error handler returns a body with one field:

```json
{
  "detail": "Inspection not found"
}
```

That is the whole body. There is no error code and no timestamp.

**The validation case.** When the request body itself does not match what is expected, the
framework's own handler runs instead and returns a list of problems:

```json
{
  "detail": [
    {
      "loc": ["body", "vendor_id"],
      "msg": "value is not a valid uuid",
      "type": "type_error.uuid"
    }
  ]
}
```

So `detail` is a string in one case and a list in the other. Clients need to handle both. There is
no `error_code` field and no `timestamp` field in either shape.

**Status codes used:**

| Code | Meaning |
|---|---|
| `200` | Success |
| `201` | Something was created |
| `204` | Deleted, nothing returned |
| `400` | Bad input, such as an unsupported file type or too many images |
| `401` | Missing, expired, or invalid token |
| `403` | Logged in, but this role is not allowed to do this |
| `404` | Not found |
| `409` | The inspection is not in a state where this action makes sense |
| `422` | The request body failed validation |
| `500` | Server error. The body is always `{"detail": "Internal server error"}` |

**One more note:** the framework's "Authorize" button on the `/docs` page does not work. It is
configured to send a username and password as a form, but the login endpoint expects a JSON body
with an email and password. Use the login endpoint directly.

## 4. Login and users - `/auth`

### 4.1 Register

`POST /api/v1/auth/register` — no login needed

```json
{
  "email": "operator@visionforge.ai",
  "password": "SecurePassword123!",
  "full_name": "John Doe",
  "role": "operator"
}
```

`role` is optional and defaults to `operator`. Setting it to `admin` currently works, which is the
privilege escalation bug noted above.

**Response, `201`:**

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "email": "operator@visionforge.ai",
  "full_name": "John Doe",
  "role": "operator",
  "is_active": true,
  "created_at": "2026-09-18T10:15:00Z"
}
```

### 4.2 Log in

`POST /api/v1/auth/login` — no login needed

Send JSON. Do not use form data.

```json
{
  "email": "operator@visionforge.ai",
  "password": "operatorpassword123"
}
```

**Response, `200`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "user": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "operator@visionforge.ai",
    "full_name": "John Doe",
    "role": "operator"
  }
}
```

### 4.3 Refresh the tokens

`POST /api/v1/auth/refresh` — no login needed

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsIn..."
}
```

**Response, `200`:** a new `access_token` and a new `refresh_token`. Both are replaced, not just the
access token.

Note that the server does not keep a list of issued refresh tokens, so an old refresh token stays
valid until it expires. There is no way to revoke one.

### 4.4 Current user

`GET /api/v1/auth/me` — login needed

**Response, `200`:** the user profile and role.

## 5. Inspections - `/inspections`

### 5.1 Create an inspection

`POST /api/v1/inspections` — login needed

Send `multipart/form-data`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `vendor_id` | UUID | Yes | The supplier |
| `location` | string | Yes | Where the part was received |
| `images` | files | Yes | At least one. Up to 6. Only `.jpg`, `.jpeg`, `.png` |
| `product_type` | string | No | Defaults to `"motherboard"` |
| `part_code` | string | No | |

**Response, `201`:**

```json
{
  "id": "7b12c8a4-e912-4c22-9214-419b489a2345",
  "case_number": "CASE-20260917120754-38350E",
  "status": "pending",
  "message": "Inspection created. Results will be available shortly."
}
```

Four fields only: `id`, `case_number`, `status`, `message`. There is no `image_count` and no
`created_at` in this response.

**Case number format:** `CASE-<YYYYMMDDHHMMSS>-<6 hex characters>`, for example
`CASE-20260917120754-38350E`.

**There is no way to choose the reference image through this endpoint, and no `golden_reference_id`
form field.** Stage 3 always finds the match itself.
The database column exists but is never filled from user input.

### 5.2 List inspections

`GET /api/v1/inspections` — login needed

Query parameters: `vendor_id`, `status_filter`, `page`, `page_size`.

Returns a list, newest first.

### 5.3 Get one inspection

`GET /api/v1/inspections/{id}` — login needed

**Response, `200`:** the full inspection record, including the case number, supplier, status,
verdict, fraud probability, root cause, policy action, and the list of evidence records.

### 5.4 Check the status

`GET /api/v1/inspections/{id}/status` — login needed

This is the fallback the frontend uses when the live stream is blocked.

**Response, `200`**, depending on whether the inspection is still in memory:

```json
{
  "stage": 5,
  "stage_name": "evidence_execution",
  "status": "in_progress",
  "progress": 4,
  "detail": null
}
```

**Fields:**

- `stage` — a number from 1 to 8.
- `stage_name` — one of `quality_check`, `authenticity`, `reference_match`, `roi_scheduler`,
  `evidence_execution`, `evidence_fusion`, `judge`, `policy_engine`.
- `status` — `pending`, `processing`, `completed`, or `failed`.
- `progress` — how many stages are finished, a number from 0 to 8. It is **not** a percentage.
- `detail` — an error message if it failed, or extra information about the current stage.
- `verdict` and `policy_action` — only present once the inspection has finished.

The status response has no `id`, no `fraud_probability`, and no `report_path`.

### 5.5 Approve an inspection

`POST /api/v1/inspections/{id}/approve` — login needed, `operator` or `admin`

```json
{
  "review_decision": "approved",
  "reviewer_comment": "Confirmed missing capacitor C12 under a stereo microscope."
}
```

`review_decision` is required. `reviewer_comment` is optional.

**Response, `200`:** the full inspection record with the review applied.

This only works if the inspection status is `completed`. Otherwise the response is `409`.

Note that the `review_decision` you send is ignored by this endpoint. It always records `approved`.
The override endpoint always records `overridden`. The field is validated as a string but not
checked against any list of allowed values.

### 5.6 Override an inspection

`POST /api/v1/inspections/{id}/override` — login needed, `operator` or `admin`

Same body as approve.

**Response, `200`:** the full inspection record with the override applied.

Unlike approve, this one **requires** a comment. An empty comment returns `400` with the message
"Override requires a reviewer comment".

### 5.7 There is no `/review` endpoint

`POST /api/v1/inspections/{id}/review` does not exist, and the body fields are `review_decision` and
`reviewer_comment`, not `decision` and `comment`.

The frontend still calls it, so the review dialog in the web app returns 404. See
[problems.md](../problems.md) issue 3.

## 6. Live progress stream

`GET /api/v1/inspections/{id}/events`

**Response headers:**

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

**No login token is required.** This is a bug. See [problems.md](../problems.md) issue 2.

**How the stream behaves:**

- The server checks its in-memory record every 0.5 seconds.
- It closes after 120 checks, which is about 60 seconds.
- There is no keepalive comment frame, so a proxy may cut an idle connection.

**Unnamed messages.** Most messages have no name. The browser delivers them as ordinary messages.
They look like this:

```
data: {"stage": 5, "stage_name": "evidence_execution", "status": "in_progress", "progress": 4, "detail": null}
```

**The `verdict` event.** Sent once when the inspection reaches a final state:

```
event: verdict
data: {"event": "verdict", "status": "completed", "inspection_id": "7b12c8a4-...", "detail": null}
```

Read this carefully. On the most common path, **this message does not include the verdict or the
policy action**, even though the event is called `verdict`. The frontend reads those two fields,
gets nothing back, and shows a blank result. This is a real bug. See
[problems.md](../problems.md) issue 4.

Two other exit paths build the same event differently, and those two do include the verdict. The
inconsistency is the bug.

**The `error` event.** Sent if nothing finalises within the timeout:

```
event: error
data: {"error": "stream_timeout"}
```

**Events that do not exist.** `stage_progress`, `evidence_card`, and `pipeline_complete` are not
event names in this system. Searching the whole backend for those strings returns nothing outside
the Markdown files.

**The frontend fallback.** If the live connection errors, `usePipelineSSE.js` starts asking the
status endpoint every 2500 milliseconds. That interval is in the frontend code. The server's own
internal check is every 500 milliseconds.

## 7. Reference images - `/products`

These are the known-good reference images the system compares incoming photos against.

| Method | Path | Access | What it does |
|---|---|---|---|
| `GET` | `/api/v1/products` | any user | List all reference images |
| `GET` | `/api/v1/products/{reference_id}` | any user | One reference image, with its region coordinates |
| `POST` | `/api/v1/products/upload` | `admin` | Upload a new reference image |
| `POST` | `/api/v1/products` | `admin` | Register a reference image by file path, as JSON |
| `DELETE` | `/api/v1/products/{reference_id}` | `admin` | Delete a reference image and remove it from the FAISS index |

**The upload endpoint** takes `multipart/form-data`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `image` | file | Yes | One file only. `.jpg`, `.jpeg`, `.png`, `.webp` |
| `product_type` | string | Yes | |
| `part_name` | string | Yes | |
| `part_code` | string | Yes | |
| `view_angle` | string | No | Defaults to `"front"` |
| `description` | string | No | |

Note the field is called `image`, singular, unlike the inspection endpoint which takes `images`.
This endpoint also accepts `.webp`, which the inspection endpoint does not.

Uploading computes the image fingerprint, adds it to the FAISS index, and looks for a matching
region template file in `backend/data/roi_templates/`.

There are two ways to add a reference image: the multipart `POST /api/v1/products/upload` form, and
the `POST /api/v1/products` JSON endpoint that registers an image by file path.

## 8. Suppliers - `/vendors`

| Method | Path | Access | What it does |
|---|---|---|---|
| `GET` | `/api/v1/vendors` | any user | List suppliers |
| `GET` | `/api/v1/vendors/dropdown` | any user | Short list for selection menus |
| `GET` | `/api/v1/vendors/{vendor_id}` | any user | One supplier |
| `POST` | `/api/v1/vendors` | `admin` | Create a supplier |
| `PATCH` | `/api/v1/vendors/{vendor_id}` | `admin` | Update a supplier |
| `DELETE` | `/api/v1/vendors/{vendor_id}` | `admin` | Delete a supplier |

**Create body:**

```json
{
  "name": "Apex Semiconductor Corp",
  "site_name": "Shenzhen Fab 4",
  "code": "VND-APEX-04"
}
```

**One bug here:** the update schema accepts an `is_active` field, but the `vendors` table has no such
column. Sending it returns success and does nothing. See
[problems.md](../problems.md) issue 7.

## 9. Reports - `/reports`

| Method | Path | Access | What it does |
|---|---|---|---|
| `GET` | `/api/v1/reports` | any user | List reports |
| `GET` | `/api/v1/reports/{id}` | any user | Report details and summary findings |
| `GET` | `/api/v1/reports/{id}/pdf` | any user | Download the PDF |
| `DELETE` | `/api/v1/reports/{id}` | **any user** | Delete a report |

**List query parameters:** `vendor_id`, `verdict`, `policy_action`, `page`, `page_size`, `limit`.

There is no `date_range` parameter.

**Two things to know:**

- The response is `{"total": n, "items": [...]}`. There are no `page` or `page_size` fields in the
  response, even though you can send them as query parameters.
- Pagination is done in memory. The whole result set is loaded, then sliced. Fine at small scale,
  but it will not stay fast with a lot of data.
- The delete endpoint has no role check, so any logged-in user can delete any report. Every other
  delete in the project is admin-only. See [problems.md](../problems.md) issue 11.

**About the PDFs themselves.** They are real, generated with ReportLab, and contain text and tables.
They are **not** signed, not hashed, and contain no images. There is no SHA-256 hash stamp and no
embedded comparison images with bounding boxes. The signature table is drawn as text, but no hashing
happens anywhere in the backend, and no images are embedded.

**Download filenames** come from the case number, and the frontend saves the file as
`inspection-report-<first 8 characters of the id>.pdf`.

## 10. Analytics - `/analytics`

Every response except `summary` is wrapped in an object with an `items` list, not a bare array.

| Path | What it returns |
|---|---|
| `GET /api/v1/analytics/summary` | Overall counts |
| `GET /api/v1/analytics/vendors` | Fraud rate grouped by supplier |
| `GET /api/v1/analytics/locations` | Fraud rate grouped by receiving location |
| `GET /api/v1/analytics/trend` | Counts over time |
| `GET /api/v1/analytics/by-operator` | **Admin only.** Counts per operator |

Older names still work as hidden aliases: `/analytics/vendor-risk` and `/analytics/by-vendor` both
reach the suppliers endpoint. `/analytics/by-location` and `/analytics/monthly-trend` do the same for
locations and trend. These are hidden from the API documentation page.

**`summary` fields:** `total_inspections`, `fraud_detected_count`, `fraud_rate_pct`,
`pending_reviews_count`, `accepted_count`, `quarantined_count`, `avg_confidence_pct`.

There is no `active_vendors` field.

**Supplier risk item fields:** `vendor_id`, `vendor_name`, `total_inspections`, `fraud_count`,
`fraud_rate_pct`, `risk_level`. The risk level is `LOW`, `MEDIUM`, or `HIGH`. An item is `HIGH` if
the fraud rate is 20% or more, or there are 3 or more fraud cases. It is `MEDIUM` if the rate is 5%
or more, or there is at least one.

**Location item fields:** `location`, `total_inspections`, `fraud_count`, `fraud_rate_pct`. No risk
level.

**Trend item fields:** `period`, `total_inspections`, `fraud_count`, `fraud_rate_pct`. Despite the
name, `period` is day-level, formatted like `"Sep 24"`, not `"2026-09"`.

**Operator item fields:** `operator_id`, `operator_name`, `operator_email`, `total_inspections`,
`approved_count`, `overridden_count`.

**Who sees what:** an `admin` sees everything. An `operator` is quietly limited to inspections they
created themselves. This filtering is not obvious from the route definition and is easy to miss.

## 11. System - `/system` and root

There are only three system-level routes:

| Method | Path | Access | Response |
|---|---|---|---|
| `GET` | `/` | public | Basic service info |
| `GET` | `/health` | public | `{"status": "healthy", "app": "VisionForge-AI", "version": "0.1.0"}` |
| `GET` | `/api/v1/system/network` | login needed | `{"ip": "192.168.1.42", "hostname": "factory-pc-04"}` |

**Endpoints and fields that are not real:**

- `GET /api/v1/system/health` — does not exist. The real one is `GET /health`, at the server root,
  not under `/api/v1`.
- A field called `database` reporting the database status — does not exist.
- A field called `faiss_index` reporting the vector index — does not exist. The index is loaded at
  startup, but its state is never reported over HTTP.
- A field called `yolo_model` — does not exist.
- `GET /api/v1/system/tunnel-url` — does not exist. The public tunnel address is a frontend build
  setting, not a backend endpoint.
- The field is called `app`, not `app_name`.

`/system/network` is the only route in that file.

**Also on the server root:** `/docs`, `/redoc`, and `/openapi.json`, all public. Plus two static file
serves at `/static/uploads` and `/static/golden`.

## 12. Routes people assume exist

A quick list, so nothing is a surprise:

| Assumed | Reality |
|---|---|
| Errors include `error_code` and `timestamp` | Only `detail` |
| Create inspection returns `image_count` and `created_at` | Returns `id`, `case_number`, `status`, `message` |
| Create inspection accepts `golden_reference_id` | No such field |
| Status returns `id`, `fraud_probability`, `report_path` | Returns `stage`, `stage_name`, `status`, `progress`, `detail`, and later `verdict` and `policy_action` |
| `POST /inspections/{id}/review` | Does not exist. Use `/approve` and `/override` |
| Review body is `{decision, comment}` | It is `{review_decision, reviewer_comment}` |
| Live events: `stage_progress`, `evidence_card`, `pipeline_complete` | Only `verdict` and `error` |
| `/api/v1/system/health` | `GET /health` at the root, with different fields |
| `/api/v1/system/tunnel-url` | Does not exist |
| Reports filter by `date_range` | No such parameter |
| Summary includes `active_vendors` | No such field |
| Case numbers look like `VF-20260918-7B12` | They look like `CASE-20260917120754-38350E` |
| Override is admin-only | Operators can override too |
| Reports cannot be deleted by operators | They can |

---

*Next: [DATABASE.md](DATABASE.md) for what gets stored, or
[FRONTEND.md](FRONTEND.md) for how the web app uses these endpoints.*
