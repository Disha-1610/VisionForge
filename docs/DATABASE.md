# Database Structure

> This describes what VisionForge stores and why.
> Checked against the SQLAlchemy models, the migration script, and the live database in
> September 2026.

---

## Table of contents

1. [Overview](#1-overview)
2. [Which database is used](#2-which-database-is-used)
3. [The five tables](#3-the-five-tables)
4. [How the tables connect](#4-how-the-tables-connect)
5. [Types used in columns](#5-types-used-in-columns)
6. [Indexes](#6-indexes)
7. [The vector index](#7-the-vector-index)
8. [Reference region templates](#8-reference-region-templates)
9. [Default data created at startup](#9-default-data-created-at-startup)
10. [Problems to be aware of](#10-problems-to-be-aware-of)

---

## 1. Overview

VisionForge stores everything in **5 tables**. That is all.

| Table | Holds | Roughly how many rows |
|---|---|---|
| `users` | People who can log in | A handful |
| `vendors` | The suppliers whose parts are being checked | A handful |
| `golden_references` | Known-good reference images | A few to hundreds |
| `inspections` | One row per inspection | Grows with use |
| `evidence` | One row per finding per inspection | Grows fast, many rows per inspection |

A simple picture of the relationships:

```
  users ──────────┬──────────────┐
                  │              │
        created the          reviewed
                  │              │
                  ▼              │
            ┌──────────┐        │
            │vendors   │        │
            └────┬─────┘        │
                 │              │
         supplied the           │
                 │              │
                 ▼              ▼
           ┌────────────────────────┐        ┌───────────────┐
           │      inspections       │──1:N──▶│   evidence    │
           └───────────┬────────────┘        └───────────────┘
                       │                              ▲
                       │  compared against             │ written by
                       ▼                              │ the 4 agents
              ┌──────────────────┐                    │
              │ golden_references│                    │
              └──────────────────┘                    │
                                                      │
                                          ┌───────────┴──────────┐
                                          │  ocr · label ·       │
                                          │  structural · vlm    │
                                          └──────────────────────┘
```

**Important:** there is no audit trail table in this project. Five tables is the complete list, and
nothing logs who changed what.

## 2. Which database is used

The code talks to the database **asynchronously**, through SQLAlchemy 2.0. Two drivers are
supported:

| Database | Driver | Used for |
|---|---|---|
| PostgreSQL | `asyncpg` | Production |
| SQLite | `aiosqlite` | Local development, and what the shipped `.env` uses |

**Which one runs by default is a bit confusing, and worth understanding:**

- The default written in `backend/app/core/config.py` is
  `postgresql+asyncpg://postgres:postgres@localhost:5432/visionforge`
- But `backend/.env` overrides it with `sqlite+aiosqlite:///data/visionforge.db`
- `.env` wins, so **a fresh clone runs on SQLite**

This means someone reading only the code would think PostgreSQL is the default, and someone running
the project gets SQLite. Both work. The tables are written so the same model definitions work on
both.

**If the configured database cannot be reached,** the code does not crash. It logs a warning and
falls back to an in-memory SQLite database. Handy for a demo, worth knowing about before you rely
on your data being saved.

**Alembic** is set up for schema migrations, and also runs asynchronously. However, see
[problems](#10-problems-to-be-aware-of) — the initial migration script is out of date.

## 3. The five tables

### 3.1 `users`

People who can log in.

| Column | Type | Rules | Notes |
|---|---|---|---|
| `id` | UUID | Primary key | Generated in Python |
| `email` | VARCHAR(255) | Not null, **unique**, indexed | The login name |
| `hashed_password` | VARCHAR(255) | Not null | bcrypt hash, never the real password |
| `full_name` | VARCHAR(255) | Not null | |
| `role` | Enum | Not null | `ADMIN` or `OPERATOR`. Defaults to `OPERATOR` |
| `is_active` | Boolean | Not null | Defaults to `true`. Not currently enforced at login |
| `created_at` | Timestamp | Not null | Set by the database |
| `updated_at` | Timestamp | Not null | Set by the database, refreshed on change |

No index on `is_active`.

### 3.2 `vendors`

The suppliers whose parts are being inspected.

| Column | Type | Rules | Notes |
|---|---|---|---|
| `id` | UUID | Primary key | |
| `name` | VARCHAR(255) | Not null, indexed | **Not unique.** Two suppliers can share a name |
| `site_name` | VARCHAR(255) | Not null | Which factory or site |
| `code` | VARCHAR(50) | Not null, **unique**, indexed | Short code, for example `SMT-01` |
| `created_at` | Timestamp | Not null | |
| `updated_at` | Timestamp | Not null | |

**There is no `is_active` column on this table.** The API accepts an `is_active` field when updating
a vendor and reports one back, but neither is real — see
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) issue 7.

### 3.3 `golden_references`

The known-good images that incoming photos are compared against.

| Column | Type | Rules | Notes |
|---|---|---|---|
| `id` | UUID | Primary key | |
| `part_id` | VARCHAR(100) | Not null, indexed | Manufacturer part number. **Not unique** |
| `part_name` | VARCHAR(255) | Not null | |
| `image_path` | VARCHAR(512) | Not null | Where the image is stored on disk |
| `thumbnail_path` | VARCHAR(512) | **Nullable** | |
| `embedding_id` | VARCHAR(100) | **Nullable**, indexed | See note below |
| `roi_template_path` | VARCHAR(512) | **Nullable** | Points at the region template file |
| `view_angle` | VARCHAR(50) | Not null | Defaults to `"front"`. Free text, no allowed-value list |
| `description` | Text | **Nullable** | |
| `meta` | JSON / JSONB | **Nullable** | Anything extra |
| `created_at` | Timestamp | Not null | |
| `updated_at` | Timestamp | Not null | |

Three details that are easy to get wrong:

- `image_path`, `thumbnail_path`, and `roi_template_path` are `VARCHAR(512)`.
- `embedding_id` and `roi_template_path` are both **nullable**. They are not required.
- The default `view_angle` is `"front"`.

**`view_angle` has no allowed-value list.** It is free text. It is not limited to `"top"`, `"iso"`,
or `"pins"`, and the only value actually used anywhere in the project is `"front"`.

**A note on `embedding_id`:** this column is written on upload but is never read back. The FAISS
index stores its own ID list, keyed on the record's `id`, not on `embedding_id`. So this column is
currently unused weight, and because it is nullable and not unique it is not a reliable key.

**There is no `vendor_id` column on this table,** even though the API schema has such a field.

### 3.4 `inspections`

One row per inspection. This is the biggest table, with **30 columns**.

#### Identity and ownership

| Column | Type | Rules | Notes |
|---|---|---|---|
| `id` | UUID | Primary key | |
| `case_number` | VARCHAR(50) | Not null, **unique**, indexed | Format `CASE-YYYYMMDDHHMMSS-XXXXXX` |
| `vendor_id` | UUID | Not null, indexed | Links to `vendors` |
| `location` | VARCHAR(255) | Not null, indexed | Where it was received |
| `created_by` | UUID | Not null | Links to `users`. **Not indexed** |

#### Images

| Column | Type | Rules | Notes |
|---|---|---|---|
| `image_paths` | Array of strings / JSON | Not null | Paths to the uploaded files |
| `image_count` | Integer | Not null | Defaults to `1` |
| `golden_reference_id` | UUID | **Nullable** | Set by stage 3, not by the user |

#### Results

| Column | Type | Rules | Notes |
|---|---|---|---|
| `status` | Enum | Not null, indexed | `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`. Defaults to `PENDING` |
| `verdict` | Enum | Not null, indexed | `ACCEPT`, `REJECT`, `REVIEW`, `PENDING`. Defaults to `PENDING` |
| `policy_action` | Enum | **Nullable**, indexed | `ACCEPT`, `RETAKE`, `QUARANTINE`, `VENDOR_VERIFICATION` |
| `fraud_probability` | Float | Nullable | 0 to 1 |
| `fraud_category` | VARCHAR(100) | Nullable, indexed | For example `missing_components` |
| `root_cause` | VARCHAR(4000) | Nullable | The written explanation |
| `reference_similarity` | Float | Nullable | How well it matched a reference |
| `report_path` | VARCHAR(500) | Nullable | Where the PDF was written |
| `working_memory` | JSON / JSONB | Nullable | The full in-flight state of the pipeline |

#### Quality and authenticity

| Column | Type | Rules | Notes |
|---|---|---|---|
| `quality_passed` | Boolean | Not null | Defaults to `false` |
| `quality_failure_reason` | VARCHAR(500) | Nullable | Why the photo was rejected |
| `authenticity_score` | Float | Nullable | 0 to 1, higher means more trustworthy |
| `authenticity_flagged` | Boolean | Not null | Defaults to `false` |
| `judge_confidence` | Float | Nullable | How sure the AI judge was |

#### Human review

| Column | Type | Rules | Notes |
|---|---|---|---|
| `review_decision` | Enum | Not null | `APPROVED`, `OVERRIDDEN`, `PENDING`. Defaults to `PENDING` |
| `reviewed_by` | UUID | **Nullable** | Links to `users`. **Not indexed** |
| `reviewer_comment` | VARCHAR(2000) | Nullable | |
| `reviewed_at` | Timestamp | **Nullable** | |

#### Errors and timing

| Column | Type | Rules | Notes |
|---|---|---|---|
| `error_message` | VARCHAR(2000) | Nullable | If the pipeline crashed |
| `created_at` | Timestamp | Not null, indexed | |
| `updated_at` | Timestamp | Not null | |

All 30 columns are listed above. The two timestamp columns, `created_at` and `updated_at`, plus
`created_by`, `image_count`, `error_message`, `quality_failure_reason`, `authenticity_flagged`,
`judge_confidence`, `fraud_category`, `root_cause`, `review_decision`, `reviewed_by`,
`reviewer_comment`, and `reviewed_at` are the ones most often missed.

**One field is not a column.** `vendor_name` looks like a field on this table but is a calculated
value that looks up the supplier. Same for `product_type`, which is derived from the working memory.

### 3.5 `evidence`

One row per finding per inspection. This table grows quickly, because each cropped region produces
one row.

| Column | Type | Rules | Notes |
|---|---|---|---|
| `id` | UUID | Primary key | |
| `inspection_id` | UUID | Not null, indexed | Links to `inspections`, with delete-cascade |
| `agent_type` | Enum | Not null, indexed | `OCR`, `LABEL`, `STRUCTURAL`, `VLM` |
| `detector_name` | String(100) | Not null | Which specific detector, e.g. `structural_ssim` |
| `roi_id` | String(100) | Not null | Which cropped region |
| `roi_type` | String(50) | Not null | `text`, `label`, `structural`, or `visual` |
| `bounding_box` | JSON / JSONB | Not null | Where in the image |
| `confidence` | Float | Not null | 0 to 1 |
| `evidence_summary` | String(2000) | Not null | One-line summary |
| `explanation` | String(2000) | Not null | Full explanation |
| `processing_time_ms` | Integer | Not null | How long the agent took |
| `failed` | Boolean | Not null | Defaults to `false` |
| `failure_reason` | String(500) | Nullable | Set if it failed |
| `detected_count` | Integer | Nullable | How many were found |
| `expected_count` | Integer | Nullable | How many should be there |
| `component_findings` | JSON / JSONB | Nullable | Per-component detail |
| `raw_output` | JSON / JSONB | Nullable | The agent's untouched output |
| `created_at` | Timestamp | Not null | |

**There is no `updated_at` column,** which fits the idea that evidence should not change. There is
also no `sequence` column — the in-memory records are numbered, but that number is never saved.

Five columns on this table are easy to overlook: `roi_type`, `raw_output`, `failed`, `failure_reason`,
and `created_at`.

**There is no range check on `confidence` at the database level.** The in-memory records check that
it is between 0 and 1, but the column itself accepts anything.

#### About "append-only"

"Evidence is append-only" sounds like a strong security property, but the database does not
enforce it. Here is what actually exists:

- The model file has a comment saying never to update, only insert. That is a comment.
- **There is no database trigger, rule, or constraint** that would reject an update or a delete.
- Nothing in the application code updates evidence, so no accidental updates happen today.
- **But deletes do happen.** The `evidence` table has `ON DELETE CASCADE` to `inspections`, and the
  model also has a delete rule. Deleting an inspection deletes its evidence.

The separate in-memory evidence store does enforce immutability at its own Python level, and raises
an error if you try to clear a record. But it is a plain dictionary in memory, it is gone when the
server restarts, and its save function does nothing at all — it is an empty function with a note
saying it is a hook for future database writes.

See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) issue 9.

## 4. How the tables connect

| From | To | Relationship | If the parent is deleted |
|---|---|---|---|
| `inspections.vendor_id` | `vendors.id` | Many inspections per supplier | **Blocked** by the model, but see below |
| `inspections.golden_reference_id` | `golden_references.id` | Many inspections per reference | Set to null |
| `inspections.created_by` | `users.id` | Many inspections per user | **Blocked** |
| `inspections.reviewed_by` | `users.id` | Many inspections per reviewer | Set to null |
| `evidence.inspection_id` | `inspections.id` | Many evidence rows per inspection | **Deleted** |

**`inspections.reviewed_by` is easy to miss.** It is the second link to `users`, and it is the one
that nulls out rather than blocking a delete.

**A real caveat about the "blocked" rules.** They are declared correctly in the models, and
PostgreSQL enforces them. But SQLite does not enforce foreign keys unless it is switched on, and
this project never switches it on. So on the default development database, deleting a supplier
leaves its inspections pointing at a supplier that no longer exists. See
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) issue 10.

## 5. Types used in columns

**The same model definitions work on both databases**, which is why a single set of model files
covers SQLite and PostgreSQL.

Most columns are plain types that work everywhere. Three need help, using SQLAlchemy's variant
mechanism to say "use this on PostgreSQL, that one on SQLite":

| Column | On PostgreSQL | On SQLite |
|---|---|---|
| `golden_references.meta` | `JSONB` | `JSON` |
| `inspections.working_memory` | `JSONB` | `JSON` |
| `evidence.bounding_box` | `JSONB` | `JSON` |
| `evidence.component_findings` | `JSONB` | `JSON` |
| `evidence.raw_output` | `JSONB` | `JSON` |
| `inspections.image_paths` | Array of strings | `JSON` |

`JSONB` on PostgreSQL is better because it compresses and can be queried inside. On SQLite
everything is stored as text, which is fine for this use.

**A custom JSON serialiser is installed** on the database engine. It handles UUIDs, dates, and
dataclasses, which Python's default JSON encoder cannot do. Without it, saving an inspection with a
UUID in it would fail.

### The six enumerations

| Enumeration | Values |
|---|---|
| `UserRole` | `admin`, `operator` |
| `InspectionStatus` | `pending`, `processing`, `completed`, `failed` |
| `InspectionVerdict` | `accept`, `reject`, `review`, `pending` |
| `PolicyAction` | `accept`, `retake`, `quarantine`, `vendor_verification` |
| `ReviewDecision` | `approved`, `overridden`, `pending` |
| `AgentType` | `ocr`, `label`, `structural`, `vlm` |

**These are the values you see over the API, in lowercase.** But the database stores the
**uppercase name**, because SQLAlchemy saves the enumeration member name by default when no
converting function is given. So the database contains `ADMIN` while the API sends `admin`.

This is invisible on SQLite. It is not invisible on PostgreSQL, and it is part of why the migration
script is broken. See [problems](#10-problems-to-be-aware-of).

These six lists are the only valid values. Names like `VERIFIED`, `TAMPERED`, and `VERIFY` are not
used anywhere in this codebase.

## 6. Indexes

There are **15 indexes**. Three of them enforce uniqueness.

| Table | Columns | Unique? |
|---|---|---|
| `users` | `email` | **Yes** |
| `vendors` | `name` | No |
| `vendors` | `code` | **Yes** |
| `golden_references` | `part_id` | No |
| `golden_references` | `embedding_id` | No |
| `inspections` | `case_number` | **Yes** |
| `inspections` | `vendor_id` | No |
| `inspections` | `location` | No |
| `inspections` | `status` | No |
| `inspections` | `fraud_category` | No |
| `inspections` | `verdict` | No |
| `inspections` | `policy_action` | No |
| `inspections` | `created_at` | No |
| `evidence` | `inspection_id` | No |
| `evidence` | `agent_type` | No |

**There are no indexes that span more than one column.** Every index covers a single column.

**There is no combined index on `(vendor_id, created_at)`.** It appears nowhere in the models, the
migration, or the live database.

**On the `evidence` table, only `agent_type` is indexed.** `confidence` is not, and there are no
partial indexes anywhere in this database.

**Columns with no index that you might expect one on:**

- `inspections.created_by` and `inspections.reviewed_by` — both are foreign keys with no index.
- `inspections.golden_reference_id` — a foreign key with no index.
- `inspections.review_decision`
- `golden_references.part_id` is indexed but not unique, so the same part number can be inserted
  more than once.

On PostgreSQL, an unindexed foreign key means every insert and delete has to scan the table. With
the current data size this does not matter. With a lot of data it will.

## 7. The vector index

Reference images are matched by turning images into lists of numbers, called embeddings, and
finding the closest list.

**This is separate from the database.** There is no vector column in any table. Instead:

| File | What it is |
|---|---|
| `backend/data/faiss_index/golden.index` | The FAISS search index itself. Currently 3 vectors |
| `backend/data/faiss_index/golden.ids.npy` | Maps each vector back to a `golden_references.id` |
| `backend/data/faiss_index/golden.meta.json` | Records which embedding model made the index |

**The meta file contains exactly two fields:**

```json
{"provider": "gemini", "dimension": 3072}
```

**Which embedding model is used:**

| Model | Size | When |
|---|---|---|
| `gemini-embedding-2` (Google) | 3,072 numbers | Primary |
| OpenCLIP `ViT-B-32` | 512 numbers | Fallback when the Google service is unavailable |

The current index was built with the Google model at 3,072 numbers, which matches the file on disk.

**Dimension mismatches are properly guarded.** If the fallback tries to add a 512-number vector to
a 3,072-number index, the code raises a clear error instead of silently corrupting the index. This
is a real safeguard and is tested.

**OpenCLIP is the fallback embedder, not the primary one.** The 3,072 number Google model is
primary.

## 8. Reference region templates

Alongside each reference image there can be a JSON file listing the areas of the board that matter
and which specialist should look at each one. There are three such files, shipped in
`backend/data/roi_templates/`:

| File | Part | Number of regions |
|---|---|---|
| `motherboard_pcb_mcu_v2.json` | Motherboard | **8** |
| `battery_bat_std_v1.json` | Battery pack | **7** |
| `ram_ddr4_v1.json` | RAM module | **5** |

For the motherboard, the 8 regions are: serial label, QC seal, capacitor bank 1, resistor array,
main IC chip, I/O connector bank, mounting screws, and a general surface check.

**Path resolution is worth understanding.** The template loading code does not rebuild paths relative
to the backend folder. It tries the path as given, then a few known folders, and finally matches on
the file name alone. If none of those work, it raises an error rather than guessing.

## 9. Default data created at startup

When the server starts for the first time, it creates the tables if they are missing and adds some
sample data.

**Two users:**

| Email | Password | Role |
|---|---|---|
| `admin@visionforge.ai` | `adminpassword123` | Admin |
| `operator@visionforge.ai` | `operatorpassword123` | Operator |

**These are development passwords committed to the repository.** Change them before putting this
anywhere real.

**Three suppliers:** `SMT-01`, `FII-04`, `DLT-09`.

**Three reference images:**

| Part name | Part ID | Region file |
|---|---|---|
| Industrial ATX Motherboard V1 | `PCB-MCU-V2` | `motherboard_pcb_mcu_v2.json` (8 regions) |
| Smart Lithium Battery Pack 48V | `BAT-STD-V1` | `battery_bat_std_v1.json` (7 regions) |
| ECC DDR4 Server Module 16GB | `RAM-DDR4-V1` | `ram_ddr4_v1.json` (5 regions) |

**If table creation fails, the server logs a warning and carries on.** It does not stop. This
matters for the request that triggered a table creation to succeed, but the process stays up.

## 10. Problems to be aware of

Four real problems, all covered in [KNOWN_ISSUES.md](KNOWN_ISSUES.md):

**1. The migration script does not match the models.**
`migrations/versions/001_initial_tables.py` never creates `inspections.status` or
`inspections.error_message`, even though both exist in the models and the live database. If you
build a fresh database with the migration instead of letting the app create the tables, those two
columns will be missing and the app will crash on the first inspection.

**2. Enumeration values do not match between the migration and the models.**
The migration creates the PostgreSQL enumeration types with lowercase labels. SQLAlchemy writes
uppercase names. On PostgreSQL the first insert would be rejected as an invalid value. The
migration also never creates the `inspection_status` type, though its undo step tries to drop it.

**In practice this is hidden,** because the app builds its tables directly from the models and does
not use the migration. But it means the migration path is broken for PostgreSQL.

**3. Foreign key rules are not enforced on SQLite.**
The models declare sensible rules. SQLite ignores them because foreign key checking is off and
nothing turns it on. The "blocked" and "cascade" rules in the table above only really apply on
PostgreSQL.

**4. Evidence is not fully append-only.**
No trigger or constraint prevents updates or deletes, and deletes do happen through the cascade
from inspections.

**One more, smaller thing:** the report list endpoint loads every matching row into memory and then
slices it to the requested page. Fine now, will not stay fine.

---

*Next: [PIPELINE.md](PIPELINE.md) for how an inspection actually runs.*
