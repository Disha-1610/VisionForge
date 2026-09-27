# Known Issues

This file lists real problems found in the code during a documentation review in September 2026.
Nothing here is theoretical — each one was confirmed by reading the code or running the tests.

These are listed rather than fixed on purpose, so the documentation can be honest about the state
of the project. Some of them matter for security and should be fixed before any real deployment.

---

## 1. Anyone can sign themselves up as an admin

**Severity: High. This is a security hole.**

`POST /api/v1/auth/register` is a public endpoint. It accepts a `role` field in the request body and
uses whatever the caller sends.

```json
{ "email": "me@example.com", "password": "whatever", "full_name": "Me", "role": "admin" }
```

The route handler writes the requested role straight onto the new user record
(`backend/app/routers/auth.py:43`). No check is made that the caller is allowed to pick that role.

**What this means:** anyone who can reach the registration endpoint can create an admin account.
An admin can upload golden reference images, create and delete vendors, and see operator analytics
across the whole organisation.

**Where it is:** `backend/app/schemas/auth.py:18` and `backend/app/routers/auth.py:43`.

**Suggested fix:** ignore any `role` in the request body and always create new accounts as
`operator`. If admin accounts are needed, create them through a separate admin-only route, or seed
the first admin from the environment.

---

## 2. The live progress stream has no login check

**Severity: High. This is a security hole.**

`GET /api/v1/inspections/{id}/events` streams the progress of an inspection over a live
connection. It is the only data endpoint in the project with no authentication — it depends on a
database session, but not on a user token.

Anyone who knows or guesses an inspection ID can watch that inspection run and read its final
verdict, without logging in.

**Where it is:** `backend/app/routers/inspections.py:219-223`.

**Suggested fix:** add the same `Depends(get_current_user)` used by the other inspection routes.

---

## 3. The review dialog calls an endpoint that does not exist

**Severity: Medium. A visible feature is broken.**

When an operator opens the manual review dialog and submits it, the frontend sends a request to:

```
POST /api/v1/inspections/{id}/review
```

That route does not exist. Every submission returns **404 Not Found**.

The real endpoints are two separate ones:

- `POST /api/v1/inspections/{id}/approve`
- `POST /api/v1/inspections/{id}/override`

Both take a body with `review_decision` and `reviewer_comment`.

There is a second problem: the dialog sends `GENUINE` and `FRAUD` as verdicts. Neither is a valid
verdict in this project. The valid values are `accept`, `reject`, `review`, and `pending`.

**Where it is:** `frontend/src/services/api.js:247` and
`frontend/src/components/inspection/ReviewModal.jsx`.

---

## 4. The final live update is missing the verdict

**Severity: Medium. Causes a blank result in the UI.**

When an inspection finishes, the live stream sends a final event called `verdict`. On the most
common code path, that message does not actually contain the verdict or the policy action. It only
carries the status and the inspection ID.

The frontend reads `data.verdict` and `data.policyAction`, gets `undefined`, and shows nothing.

The same event is built three different ways depending on how the code exits, and only two of the
three include a verdict.

**Where it is:** `backend/app/routers/inspections.py:241-246`, compared with `:255-262` and
`:268-274`.

**Suggested fix:** build the final message in one place with a fixed set of fields, and always
include `verdict` and `policy_action`.

---

## 5. The phone QR code fallback is broken

**Severity: Medium. Silent failure.**

The modal that warns desktop users to use a phone instead tries to show the local network address
of the machine. It fetches it like this:

```javascript
await fetch('/api/v1/system/network')
```

That request sends no login token. The endpoint requires one, so it returns **401**. The modal then
falls back to using the current page address, which on a phone is `localhost:5173` — a useless
address on any other device.

This is currently masked because `frontend/.env` has a public tunnel address that takes priority.
Remove the tunnel and the fallback quietly stops working.

**Where it is:** `frontend/src/components/inspection/DesktopGuardModal.jsx:38` and
`backend/app/routers/system.py:36`.

**Suggested fix:** use the existing authenticated API client instead of a bare `fetch`.

---

## 6. The database migration script is broken for PostgreSQL

**Severity: Medium. Only affects the migration path.**

The project has two ways to build the database schema. They disagree.

- `init_db()` builds tables directly from the SQLAlchemy models. This is what actually runs.
- `migrations/versions/001_initial_tables.py` is the Alembic migration.

Two problems with the migration:

**a. Two columns are missing.** `inspections.status` and `inspections.error_message` exist in the
model and in the live database, but the migration never creates them.

**b. The enum labels do not match.** The migration creates the database enum types with lowercase
values (`'admin'`, `'operator'`, `'accept'`). SQLAlchemy, with no extra configuration, writes the
uppercase member names (`'ADMIN'`, `'OPERATOR'`, `'ACCEPT'`). On PostgreSQL the insert would be
rejected as an invalid enum value.

The migration also never creates the `inspection_status` type, even though its `downgrade` tries to
drop it — a sign the migration predates the column.

**Where it is:** `backend/migrations/versions/001_initial_tables.py`.

**Suggested fix:** regenerate the initial migration from the current models and set
`values_callable` on the enum types so the stored values match.

---

## 7. Two API fields are accepted but silently discarded

**Severity: Low. Confusing but not harmful.**

Two request fields are defined in the API schemas but have no matching database column:

- `PATCH /api/v1/vendors/{id}` accepts `is_active`. The `vendors` table has no such column. The
  handler sets it as a plain Python attribute that is never saved, so the change disappears.
- `GoldenReference` responses include `vendor_id`. The `golden_references` table has no such column.

Both return a successful response, so a caller believes the change was applied when it was not.

**Where it is:** `backend/app/schemas/vendor.py:39,46`, `backend/app/routers/vendors.py:88-90`,
`backend/app/schemas/product.py:13`.

**Suggested fix:** add the columns, or remove the fields from the schemas.

---

## 8. API keys are committed in plain text

**Severity: High if the repository is public.**

`backend/.env` and `backend/.env.example` both contain real-looking `GEMINI_API_KEY` and
`GROQ_API_KEY` values. `.env` is normally ignored by Git, but `.env.example` is meant to be
committed and should only ever contain placeholders.

Also, `backend/.env.example` is out of date in one place: it says `gemini-3.5-flash` where the
code uses `gemini-2.5-flash`. This stale value is easy to pick up by mistake when writing
documentation or answering questions.

**Where it is:** `backend/.env`, `backend/.env.example`, `frontend/.env`.

**Suggested fix:** replace the keys in `.env.example` with empty placeholders, confirm the committed
keys are not live, and rotate them if they were ever pushed.

---

## 9. Evidence records are deleted when an inspection is deleted

**Severity: Low for a demo, High for a compliance story.**

**Evidence records are not permanent.** They can be changed or deleted, and the model file's comment
about append-only storage is not backed by a rule.

- No database trigger, rule, or constraint stops an `UPDATE` or `DELETE` on the `evidence` table.
  The "append-only" rule is a comment in the model file, not a rule.
- The `evidence` table has `ON DELETE CASCADE` on its link to inspections. Deleting an inspection
  deletes its evidence rows. There is also a matching delete rule in the model layer.

The separate in-memory evidence store does enforce immutability in its own Python interface, but it
is a process-local dictionary, it disappears when the server restarts, and its save function does
nothing at all.

**Where it is:** `backend/app/models/evidence.py:27,35`,
`backend/app/models/inspection.py:146-148`, `backend/app/shared/evidence_store.py:141-143`.

**Suggested fix:** decide what the real requirement is. If evidence must be permanent, delete the
cascade and add a database trigger that rejects updates and deletes.

---

## 10. Foreign key rules are not enforced on SQLite

**Severity: Low on SQLite, none on PostgreSQL.**

The models declare sensible rules, such as "do not allow deleting a vendor that has inspections".
These are only enforced if the database enforces them. PostgreSQL does. SQLite does not, because
foreign key checking is off by default and this project never turns it on.

So on the default development database, deleting a vendor leaves its inspections pointing at
nothing.

**Where it is:** `backend/app/core/database.py` — no `PRAGMA foreign_keys=ON` anywhere.

**Suggested fix:** add a connect handler that runs `PRAGMA foreign_keys=ON` for SQLite.

---

## 11. Any logged-in user can delete any report

**Severity: Medium.**

Every other delete operation in the project requires the `admin` role. `DELETE
/api/v1/reports/{id}` does not. Any authenticated user, including an `operator`, can delete any
report in the system.

**Where it is:** `backend/app/routers/reports.py:406`.

**Suggested fix:** add the same admin role check the other delete routes use.

---

## 12. There is no data separation between organisations

**Severity: Medium.**

Analytics endpoints filter results by vendor and location, and the summary endpoint does limit an
`operator` to inspections they created themselves. But the individual inspection, report, and
evidence endpoints check only that a user is logged in. There is no check that a user is allowed to
see a particular record.

In a single-company setup this does not matter. In a multi-tenant setup it is a data leak.

---

## 13. PaddleOCR is referenced but not installed

**Severity: Low. Documentation and naming only.**

The OCR agent tries to import PaddleOCR first and falls back to EasyOCR if the import fails. The
import is wrapped in a try/except, so the fallback is silent.

PaddleOCR is not in `backend/requirements.txt`, so in a clean install it is always missing and
EasyOCR always runs. The code that would call PaddleOCR also uses an older version of its API.

Either add PaddleOCR to the requirements and update the call, or remove the code and describe
EasyOCR as the only engine.

---

## 14. Two error response shapes

**Severity: Low. Minor inconsistency.**

The project installs its own error handler, which returns a body with a single `detail` field.
But validation errors are not caught by that handler, so the framework's default body is returned
instead, where `detail` is a list of objects rather than a string.

Clients have to handle both shapes. There is also a set of custom exception classes that are
registered but never raised anywhere.

**Where it is:** `backend/app/core/exceptions.py`.

**Suggested fix:** add a handler for validation errors so all errors use one shape.

---

## 15. The Swagger "Authorize" button does not work

**Severity: Low. Only affects the built-in API docs.**

The project tells the API documentation tool that login uses an OAuth2 form with a username and
password. The actual login endpoint expects JSON with an email and password. The documentation page
therefore offers a login form that will never work.

**Where it is:** `backend/app/core/security.py:22` compared with `backend/app/schemas/auth.py`.
