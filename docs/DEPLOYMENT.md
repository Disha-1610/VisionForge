# Running VisionForge

> This covers getting the project running on a local machine, and being clear about what has not
> been built.
> Checked against the code in September 2026.

---

## Read this first

**There is no Docker setup in this repository.** The old version of this document showed a full
multi-container configuration and said the project "provides" it. There is no `Dockerfile` and no
`docker-compose.yml`. Every Docker and cloud section in the old document was written as a plan and
never turned into files.

If you want to run this, run it locally. That is the only method that is actually built.

---

## Table of contents

1. [What you need](#1-what-you-need)
2. [Setting it up](#2-setting-it-up)
3. [Running it](#3-running-it)
4. [On Windows](#4-on-windows)
5. [The optional phone tunnel](#5-the-optional-phone-tunnel)
6. [Every setting you can change](#6-every-setting-you-can-change)
7. [Where files are stored](#7-where-files-are-stored)
8. [Troubleshooting](#8-troubleshooting)
9. [If something goes wrong at startup](#9-if-something-goes-wrong-at-startup)
10. [What is not built yet](#10-what-is-not-built-yet)

---

## 1. What you need

| | Version | Check |
|---|---|---|
| Python | 3.11 or later. 3.13 is in use | `python --version` |
| Node.js | **20.19+ or 22.12+** | `node --version` |
| npm | Comes with Node | `npm --version` |

**Node 18 will not work.** The old document said Node 18 was the minimum. Vite 8 needs a newer
version, and it fails in a way that is not easy to read.

**A cloud API key is optional.** The system runs without one. Only two of the five AI components
need it, and the AI judge has a fallback that needs nothing. See
[AI_AGENTS.md](AI_AGENTS.md) section 8.

**Which database.** PostgreSQL is supported and SQLite is supported. For a first run, SQLite is
simpler, and the shipped `.env` is already set up for it.

## 2. Setting it up

### The backend

```bash
cd backend

python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS or Linux

pip install -r requirements.txt
```

**Then set up the environment file:**

```bash
copy .env.example .env       # Windows
cp .env.example .env         # macOS or Linux
```

Open `backend/.env` and set at least this:

```ini
JWT_SECRET_KEY=<a long random string, not the default>
```

A quick way to make one:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**If you want the cloud AI features**, also set:

```ini
GEMINI_API_KEY=<your key>
GROQ_API_KEY=<your key>
```

Without these, the structural, label, and OCR checks all still work, and the judge falls back to its
built-in rules.

### The frontend

```bash
cd frontend
npm install
```

`frontend/.env` already exists and is already correct. You do not need to change it.

## 3. Running it

**Two terminals.**

**Terminal one, the backend:**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Terminal two, the frontend:**

```bash
cd frontend
npm run dev
```

**Then open <http://localhost:5173>.**

**Sign in with:**

| Email | Password | Role |
|---|---|---|
| `admin@visionforge.ai` | `adminpassword123` | Admin |
| `operator@visionforge.ai` | `operatorpassword123` | Operator |

**Change these before putting this anywhere real.** They are in the source code and they are in the
readme.

**Useful URLs once it is running:**

| Address | What it is |
|---|---|
| <http://localhost:5173> | The web app |
| <http://localhost:8000/docs> | Interactive API documentation |
| <http://localhost:8000/health> | The health check |
| <http://localhost:8000> | Service name and version |

## 4. On Windows

There is a script that does the whole thing.

```bash
run_visionforge.bat
```

**What it actually does, in five steps:**

1. Checks that Python and npm are available.
2. Closes anything already using port 5173 or port 8000.
3. Asks whether to start the phone tunnel.
4. Starts the backend with Uvicorn.
5. Starts the frontend with Vite, and opens the browser.

**Two claims from the old document that are wrong:**

- It said the script creates a virtual environment and installs dependencies. **It does not.** If
  dependencies are missing, it will fail. Do the setup in section 2 first.
- It said the script seeds the database. **It does not.** Seeding happens inside the backend when it
  starts, and it is wrapped in a handler that only logs a warning if it fails.

There are also two smaller scripts:

```bash
start_backend.bat      # backend only
start_frontend.bat     # frontend only
```

## 5. The optional phone tunnel

This is for when the phone cannot reach your computer over the local network, which is common on a
factory floor with several locked-down wireless networks.

```bash
cd frontend
npm run tunnel
```

**What it does.** It downloads Cloudflare's `cloudflared` tool if it is not already there, about 55
MB, then starts a public HTTPS address pointing at the local frontend. It prints the address, for
example `https://something-random.trycloudflare.com`, and writes it to `frontend/.tunnel.url`.

**The address also has to be put in `frontend/.env`**, as `VITE_PUBLIC_URL`, for the QR code in the
app to show it. `run_visionforge.bat` does this for you.

**Then the operator scans the QR code** in the app with their phone, and the same page opens on the
phone. They photograph the part there, and it appears on the desktop.

**Two things to be clear about:**

- **This exposes the whole frontend development server**, not just the inspection page. Anyone with
  the address can reach every page.
- **The old document said the backend starts this automatically, and that the operator scans a QR
  code to reach a dedicated mobile intake page.** Neither is true. A person starts the tunnel, and
  the QR code opens the same page rather than a special mobile one.

**This is a demo tool.** It is the right answer for showing the project on a factory floor. It is not
a deployment.

## 6. Every setting you can change

All of them live in `backend/.env`. The old document listed 15. **There are around 48.** The ones
worth knowing about:

### The basics

| Setting | Default | What it does |
|---|---|---|
| `APP_NAME` | `VisionForge-AI` | The name shown by the health check |
| `APP_VERSION` | `0.1.0` | The version shown by the health check |
| `ENVIRONMENT` | `development` | `test` forces an in-memory database |
| `DEBUG` | `True` | **Set to `False` in production** |

### The database

| Setting | Default |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/visionforge` |
| `DATABASE_ECHO` | `False` |
| `DB_POOL_SIZE` | `10` |
| `DB_MAX_OVERFLOW` | `20` |
| `DB_POOL_TIMEOUT` | `30` |
| `DB_POOL_RECYCLE` | `1800` |

**The default in the code is PostgreSQL, but the shipped `.env` overrides it to SQLite.** So a fresh
clone runs on SQLite. To use PostgreSQL, set:

```ini
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/visionforge
```

**One warning about PostgreSQL.** The project builds its tables from the models rather than from the
migration script, which works. The migration script itself is out of date and will produce a broken
schema. Do not rely on it. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) issue 6.

### Login

| Setting | Default |
|---|---|
| `JWT_SECRET_KEY` | `change-me-in-production` |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` |
| `CORS_ORIGINS` | `http://localhost:5173`, `http://localhost:3000` |

### The AI providers

| Setting | Default | Notes |
|---|---|---|
| `GEMINI_API_KEY` | empty | |
| `GEMINI_BASE_URL` | Google's v1beta address | |
| `GEMINI_VLM_MODEL` | `gemini-2.5-flash` | Looks at images |
| `GEMINI_JUDGE_MODEL` | `gemini-2.5-flash` | The fallback judge |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-2` | Produces 3,072 numbers per image |
| `GROQ_API_KEY` | empty | |
| `GROQ_BASE_URL` | Groq's OpenAI-compatible address | |
| `GROQ_VLM_MODEL` | `qwen/qwen3.8-27b` | Also looks at images |
| `GROQ_JUDGE_MODEL` | `openai/gpt-oss-20b` | **The primary judge** |
| `LLM_TIMEOUT_SECONDS` | `10.0` | Per call |
| `LLM_MAX_RETRIES` | `3` | |
| `LLM_INITIAL_BACKOFF_SECONDS` | `1.0` | |
| `LLM_MAX_BACKOFF_SECONDS` | `8.0` | |
| `CLIP_MODEL` | `openai/clip-vit-base-patch32` | **Note: this setting is never actually read.** The code uses a hard-coded `ViT-B-32` |

**A note on model names.** The old document referred to "Gemini 3.5 Flash" in several places. **There
is no such model.** The setting is `gemini-2.5-flash`. The wrong name appears to have come from a
stale line in `.env.example`, which still says 3.5. Fix that file.

### The quality thresholds

These decide what stage 1 and stage 2 accept. They are all in `.env`, so they can be changed without
touching the code.

| Setting | Default | What it does |
|---|---|---|
| `MIN_BLUR_VARIANCE` | `100.0` | Below this, the photo is too blurry |
| `MIN_BRIGHTNESS` | `40.0` | Below this, too dark |
| `MAX_BRIGHTNESS` | `220.0` | Above this, overexposed |
| `MIN_IMAGE_WIDTH` | `640` | |
| `MIN_IMAGE_HEIGHT` | `480` | |
| `SIMILARITY_THRESHOLD` | `0.75` | Below this, no reference matches |
| `AUTHENTICITY_HARD_BLOCK_THRESHOLD` | `0.35` | Below this, the photo is untrustworthy |
| `AUTHENTICITY_FLAG_THRESHOLD` | `0.50` | Above this, the photo is flagged |
| `ELA_ANOMALY_STD_THRESHOLD` | `15.0` | Sensitivity of the tamper check |
| `ELA_RESAVE_QUALITY` | `95` | Quality used when re-saving |
| `NOISE_PATCH_GRID` | `4` | Grid size for the noise check |
| `NOISE_INCONSISTENCY_RATIO` | `2.5` | How much patches may differ |
| `COPY_MOVE_BLOCK_SIZE` | `16` | Window size for cloning detection |
| `COPY_MOVE_MATCH_THRESHOLD` | `200` | Similarity needed to count as a clone |
| `COPY_MOVE_MIN_DUPLICATE_RATIO` | `0.03` | Minimum duplicated area |
| `SCREENSHOT_UNIFORMITY_THRESHOLD` | `0.92` | Above this, treated as a screenshot |
| `DUPLICATE_HASH_MAX_DISTANCE` | `4` | Fingerprint distance treated as a repeat |

**The old documentation listed a "calibrate quality thresholds" feature for admins.** No such
feature exists. These are `.env` values only.

**The front end has one setting:**

| Setting | Default | Notes |
|---|---|---|
| `VITE_PUBLIC_URL` | the tunnel address | Shown in the QR code |
| `VITE_API_BASE_URL` | `/api/v1` | **Declared but never read.** The address is hard-coded in the code |

## 7. Where files are stored

Everything goes under `backend/data/`.

| Folder | What is in it |
|---|---|
| `inspection_uploads/` | Photos sent by operators |
| `golden_images/` | The known-good reference photos |
| `faiss_index/` | The vector index and its ID list |
| `roi_templates/` | The region files for each reference part |
| `yolo_weights/` | The component detection model |
| `reports/` | Generated PDFs |
| `visionforge.db` | The SQLite database, if you are using SQLite |

**The paths are configurable.** `UPLOAD_DIR`, `GOLDEN_IMAGE_DIR`, `FAISS_INDEX_PATH`,
`ROI_TEMPLATE_DIR`, `YOLO_WEIGHTS_DIR`, and `REPORTS_DIR` can each be changed.

**One gotcha.** The path resolution code does not build paths from the backend folder, as the old
document said. It tries the path as given, then a few known folders, then finally matches on the
file name alone. If none of those work, it raises an error rather than guessing. So a file in an
unusual place will not be found, even if it exists.

## 8. Troubleshooting

### Port 5173 or 8000 already in use

Something else is running. `run_visionforge.bat` closes both automatically. To do it by hand:

**Windows:**

```powershell
Get-NetTCPConnection -LocalPort 5173,8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force }
```

**macOS or Linux:**

```bash
lsof -ti:5173,8000 | xargs kill -9
```

### The frontend will not start on Node 18

Vite 8 needs Node 20.19 or 22.12 or later. Check with `node --version` and upgrade if needed.

### The frontend starts but every request fails

The backend is probably not running, or it is on a different port. The proxy forwards port 5173 to
port 8000. Check <http://localhost:8000/health>.

### The backend starts but there are no tables or no sample data

The setup is wrapped in a handler that logs a warning instead of failing. Look for a warning about
creating the database in the backend output.

If you are using PostgreSQL, check that the server is running and the credentials are right. If you
are using SQLite, check that `backend/data/` exists and is writable.

### An inspection stops with a vector size mismatch

The vector index was built with one embedding model and something is trying to add vectors from
another. The current index is 3,072 numbers, from Google's model. The local fallback makes 512.

This usually means the Google embedding service is unreachable, so the fallback is being used
against an index built by Google. The code raises a clear error rather than corrupting the index,
which is the right behaviour, but the inspection will not complete.

### The AI judge always says the same thing

That is the built-in fallback running, which means both cloud providers are failing. Check the keys
and the network.

### The phone tunnel does not come up

Check that `frontend/.env` has `VITE_PUBLIC_URL` set to the address the tunnel printed. Without
that, the QR code shows the wrong address.

## 9. If something goes wrong at startup

The backend is deliberately forgiving. Two things will not stop it:

**If the database cannot be reached,** it logs a warning and falls back to an in-memory SQLite
database. The server starts and appears to work, **but nothing is saved.** This is the most confusing
failure mode, because everything looks fine until you restart and find the data gone.

**If table creation fails,** it logs a warning and carries on.

Both choices are reasonable for a demo. Both are worth knowing about before you rely on the data.

**The health check will not tell you either.** It only returns the service name and version. It does
not check the database, the vector index, or the model.

**The old document described a health endpoint reporting the database, vector index, and model
status, and a `tunnel-url` endpoint.** Neither exists. The only system endpoint is one that returns
the machine's network address.

## 10. What is not built yet

Stated plainly, so nothing is a surprise:

| Missing | Notes |
|---|---|
| **Docker packaging** | No `Dockerfile`, no `docker-compose.yml`, no `.dockerignore`. The old document's compose file was a plan |
| **Continuous integration** | No `.github` folder, no pipeline configuration. Tests are run by a person |
| **A production frontend build served by the backend** | The backend serves the API and some static files. The frontend is built and served separately |
| **A real health check** | Only the name and version. It does not verify anything is working |
| **A database migration that works** | The initial migration is out of date. The app builds its own tables, so it works, but the migration is not usable |
| **A tunnel managed by the backend** | The tunnel is a frontend script a person starts |
| **Secrets management** | Keys are plain text in `.env`, and `.env.example` contains real-looking keys |
| **HTTPS** | Nothing terminates TLS. Use the tunnel, or put a reverse proxy in front |
| **Automatic backups** | Nothing |
| **A frontend test suite** | No tests for the web app at all |
| **Measured performance** | No timing has ever been recorded |

**On the old cloud deployment sections.** The old document described deploying to ECS with SQS and
S3, and a comparison table of cloud providers with prices. None of that is implemented and none of
the prices can be checked. The project runs locally, or behind the demo tunnel. Anything else would
be starting from scratch.

**The one part of that section that is right:** the ports. The backend is on 8000 and the frontend
on 5173, and the tunnel points at the frontend.

---

*Next: [ROADMAP.md](ROADMAP.md) for what is planned, or
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) for what is broken.*
