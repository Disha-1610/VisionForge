# System Architecture

> This document explains how VisionForge is put together.
> Every statement here was checked against the code in September 2026.
> Anything that is planned but not built is labelled as such.

---

## Table of contents

1. [The problem](#1-the-problem)
2. [What the system does](#2-what-the-system-does)
3. [The main parts](#3-the-main-parts)
4. [How the 8 pipeline stages fit together](#4-how-the-8-pipeline-stages-fit-together)
5. [How one inspection flows through the system](#5-how-one-inspection-flows-through-the-system)
6. [Live progress updates](#6-live-progress-updates)
7. [Handling failure and slow AI services](#7-handling-failure-and-slow-ai-services)
8. [Design decisions and why they were made](#8-design-decisions-and-why-they-were-made)
9. [What is not built yet](#9-what-is-not-built-yet)

---

## 1. The problem

Electronics factories receive shipments of parts every day. Some of those parts are counterfeit or
have been tampered with. The ways this happens include:

- Taking working chips off old boards, sanding the top flat, and printing a fake serial number on it.
- Leaving out expensive parts, such as the small capacitors that smooth out power, to save money.
- Selling a battery pack that claims four cells but contains two, with the safety seal copied.
- Sending back burnt or corroded memory modules through the warranty process.

A human inspector on a receiving dock checks hundreds of boards an hour. They cannot reliably
spot:

- A serial number that was edited in image editing software.
- One missing 0402-size capacitor among three hundred identical parts. That part is smaller than a
  grain of rice.
- A small difference in the font used by the real factory laser engraver compared to a counterfeit
  printed label.
- A solder bridge or a scorch mark on a board with many layers.

Sending the whole photo to a general-purpose cloud AI model does not work well either. A high
resolution photo gets shrunk to fit, so tiny parts turn into blurry blobs. The call takes several
seconds, it uses up the API quota quickly, and the model often guesses wrong when asked how many
of something it can see.

## 2. What the system does

VisionForge handles this by combining fast, predictable computer vision with slow, careful AI
reasoning, and by only sending the AI models small cropped regions instead of the whole image.

The flow in plain words:

1. **Check the photo.** If it is blurry, too dark, or too bright, ask for a new one immediately.
2. **Check for editing.** Look for signs that the image was tampered with in software.
3. **Find the matching reference.** Compare the photo against known-good reference images to work
   out what part this is.
4. **Plan the work.** The reference says which areas of the board matter. Crop those areas.
5. **Run four specialists.** Text reading, label checking, component counting, and surface damage
   checking, each looking at its own crops.
6. **Combine the findings.** Turn many small results into one score, without letting a serious
   problem get averaged away by lots of clean results.
7. **Ask an AI judge.** Give an AI model the findings and ask for a written explanation.
8. **Apply the rules.** Turn the score into a decision, save everything, and build a PDF report.

## 3. The main parts

### 3.1 The web app (frontend)

- **Built with:** React 19.2 and Vite 8.3, styled with Tailwind CSS 3.4.
- **Look:** A dark industrial dashboard. Near-black background (`#070b12`) with bright cyan
  highlights (`#00f0ff`). Colours are chosen to stay readable under bright factory lighting.
- **How the operator works:** They drag a photo onto the page, or use their computer's camera, or
  scan a QR code with a phone to open the same page on the phone.
- **Live updates:** A custom hook called `usePipelineSSE` opens a live connection to the server and
  shows progress as the inspection runs. If that connection is blocked, it falls back to asking the
  server for the status every 2.5 seconds.
- **Comparing images:** A component called `DualImageCanvas` shows the submitted photo and the
  reference photo side by side, with a shared zoom control and coloured boxes over detected parts.

### 3.2 The web server (backend)

- **Built with:** FastAPI, running asynchronously.
- **Login:** Two tokens are issued. An **access token** lasts 30 minutes and is used on every
  request. A **refresh token** lasts 7 days and is used to get a new access token without asking the
  user to log in again. Both are signed with HS256. Passwords are hashed with bcrypt.
- **Two roles:**
  - `operator` — can run inspections, view results, approve or override verdicts, and download
    reports.
  - `admin` — can do everything an operator can, plus create and delete vendors, upload new
    reference images, and see analytics across all operators.

**A note on the admin role:** the registration endpoint currently lets a new user choose their own
role, which means anyone can register as an admin. This is a real bug. See
[problems.md](../problems.md) issue 1.

### 3.3 The pipeline

The inspection is modelled as a graph of 8 stages, using LangGraph. LangGraph is a library for
running steps in a defined order, with the ability to skip ahead when something goes wrong.

The state passed between stages is a `WorkingMemory` object. It holds the image paths, what has
been found so far, and the score being built up. LangGraph's own state type, `PipelineGraphState`,
is a small dictionary with three fields: the inspection ID, the working memory, and an error message
if anything failed.

Why use a graph rather than a simple function? Because the stages need to be:

- **Ordered**, so that cheap checks run before expensive AI calls.
- **Interruptible**, so a blurry photo stops at stage 1 and never spends any AI quota.
- **Visible**, so the operator can see which stage is running.

**Only one stage can be skipped.** If the photo fails the quality check at stage 1, the graph jumps
straight to stage 8 and records a `retake` action. Every other stage always runs. The old
documentation claimed there were several such shortcuts, including one for edited photos and one
for unknown hardware. Those do not exist.

### 3.4 The four AI specialists

Rather than sending the whole board to one model, four specialists each look at their own cropped
regions. Details are in [AI_AGENTS.md](AI_AGENTS.md).

| Specialist | What it looks at | Method |
|---|---|---|
| OCR | Text and serial numbers | EasyOCR, compared using string similarity |
| Label | Safety logos and seals | OpenCV template matching |
| Structural | Counting components | YOLO11n detection plus image similarity |
| VLM | Burn marks, solder damage | Google Gemini 2.5 Flash and Groq Qwen 3.8 27B |

Plus a fifth, the **AI judge**, which reads the findings from all four and writes the final
explanation. It runs on Groq's `gpt-oss-20b` model, with Gemini as a backup.

### 3.5 Storage

- **Database:** SQLAlchemy 2.0, running asynchronously. There are two supported databases:
  - **SQLite** — no setup needed. This is what the shipped `.env` file uses for local development.
  - **PostgreSQL** — for production. The default value in the code settings points here.
- **Vector search:** FAISS stores a numeric fingerprint for each reference image. When an
  inspection starts, the incoming photo is turned into a fingerprint too, and FAISS finds the
  closest match. The current index uses Google's `gemini-embedding-2`, which produces 3,072
  numbers per image.
- **Fallback embeddings:** If the Google embedding service is unavailable, the system uses OpenCLIP
  `ViT-B-32` instead, which produces 512 numbers. The code checks the sizes match and refuses to mix
  them up.
- **Files:** Uploaded photos, reference photos, and generated PDFs are stored on disk in folders
  under `backend/data/`.

**One thing to be clear about:** the evidence table is **not** permanently
append-only, and it does not protect against anyone editing past results. That rule is not actually
enforced anywhere. It is a comment in the code and nothing more, and deleting an inspection also
deletes its evidence. See [problems.md](../problems.md) issue 9.

## 4. How the 8 pipeline stages fit together

The stages run in this fixed order:

| # | Stage name | What it does |
|---|---|---|
| 1 | `quality_check` | Is the photo sharp, correctly exposed, and big enough? |
| 2 | `authenticity` | Does the photo look edited in software? |
| 3 | `reference_match` | Which known-good part does this look like? |
| 4 | `roi_scheduler` | Which areas of the board matter, and who should look at them? |
| 5 | `evidence_execution` | Run the four specialists on their crops |
| 6 | `evidence_fusion` | Turn the findings into one score |
| 7 | `judge` | Ask an AI model to explain what went wrong |
| 8 | `policy_engine` | Turn the score into a decision, save, and build the PDF |

```
                       [image uploaded]
                              |
                     1. quality_check ---- failed ----> 8. policy_engine
                              |                          (action: retake)
                     2. authenticity
                              |
                    3. reference_match
                              |
                    4. roi_scheduler
                              |
              5. evidence_execution   (two passes, see below)
                              |
                   6. evidence_fusion
                              |
                         7. judge
                              |
                    8. policy_engine  -> save to database, build PDF, tell the frontend
```

**Stage 5 runs twice.** This is worth knowing about:

- **Pass one** sends each cropped region to whichever specialist the reference file assigns to it.
- **Pass two** sends every region the structural specialist looked at to the VLM specialist, so the
  AI can double-check the automated component counts.

So it is not one flat four-way split. It is a specialist pass followed by a verification pass.

**Stage 4 groups the work.** The scheduler does not just list regions. It groups them by priority
and by which specialist will handle them, then runs the groups in order: most serious first, then
important, then routine.

## 5. How one inspection flows through the system

Here is what actually happens, in order, when an operator uploads a photo.

1. The operator submits the photo, the supplier it came from, and the location.
2. The server saves the photo, creates a database row with status `pending`, and gives the case a
   number like `CASE-20260917120754-38350E`.
3. The server replies straight away with that case number. It does not wait.
4. The inspection runs in the background.
5. Meanwhile the frontend opens a live connection to watch progress.
6. Stage 1 checks sharpness, brightness, and image size. A blurry photo stops here.
7. Stage 2 re-saves the image at a known compression level and looks at how the error pattern
   differs across the image. Edited regions often compress differently from untouched ones. It also
   checks for signs of a screenshot and for cloned blocks.
8. Stage 3 turns the image into a numeric fingerprint and searches the FAISS index for the closest
   reference. The match must score at least 0.75 to be accepted.
9. Stage 4 reads the matched reference's region file and builds the work plan.
10. Stage 5 runs the specialists. Up to four run at the same time, limited by a counter so the
    server is not overwhelmed.
11. Stage 6 combines the findings into one score between 0 and 1.
12. Stage 7 sends the findings to the AI judge, which returns a verdict, a confidence, a category
    such as "missing components", a written explanation, and recommendations.
13. Stage 8 turns that into a decision, saves the inspection and the evidence records, and builds a
    PDF report.

## 6. Live progress updates

The operator watches progress through a live connection, which the project calls Server-Sent
Events. The browser holds the connection open and the server pushes small messages down it.

**The endpoint:** `GET /api/v1/inspections/{id}/events`

**How it works:**

- The server checks its in-memory record of the inspection every half second.
- Most messages have no name. They contain the current stage number, the stage name, the status,
  how many stages are done, and a detail field.
- Two messages have names: `verdict` when the inspection reaches a final state, and `error` if
  nothing finalises within about 60 seconds.
- The connection closes after 120 checks, which is about 60 seconds.

**Two things people get wrong about this:**

- The only named events are `verdict` and `error`. Names like `stage_progress`, `evidence_card`, and
  `pipeline_complete` are not used anywhere in the backend.
- The 2.5 second fallback polling interval is in the frontend, not the server. The server's own
  internal check is every 0.5 seconds.

**Two more things to know:** there is no keepalive signal on the connection, so an aggressive proxy
can close it during a quiet period. And the connection currently requires no login, which is a
security problem. See [problems.md](../problems.md) issue 2.

## 7. Handling failure and slow AI services

The project uses two cloud AI providers so that a problem with one does not stop inspections.

**Which is used for what:**

| Job | Primary | Backup |
|---|---|---|
| Looking at images (VLM) | Google Gemini 2.5 Flash and Groq Qwen 3.8 27B, shared out evenly | The other one |
| Final judgement | Groq `gpt-oss-20b` | Google Gemini 2.5 Flash, then a rule-based fallback |
| Image fingerprints | Google `gemini-embedding-2` | OpenCLIP ViT-B-32 |

Note that Groq is the **primary** for the judge, and Gemini is the backup. Gemini is not the primary.

**How failures are handled:**

- If one provider returns a server error, a rate-limit code, or takes longer than 10 seconds, the
  request is sent to the other one.
- The client retries with a growing wait between attempts, up to 8 seconds, up to 3 attempts.
- If both providers fail, the judge falls back to a fixed set of rules in the code. This always
  produces a verdict, even with no internet connection. It is tested, and it is the reason the
  system can be demonstrated without any API keys.
- If a specialist agent fails, the pipeline does not stop. A failed result is recorded with its
  error message, and the fusion stage treats it as a mild anomaly.

**About speed:** no timing has ever been measured. There is no benchmark script in the project, and
the two stages that call cloud models each allow 10 seconds before giving up. Do not quote a
per-stage or whole-inspection figure. See
[problems.md](../problems.md) and [PIPELINE.md](PIPELINE.md).

## 8. Design decisions and why they were made

**Why not send the whole board to one AI model?**
Small parts disappear when a large image is shrunk to fit a model's input size. Counting forty
identical capacitors is something these models do unreliably. And full-image calls use up the API
quota fast. So the project uses fast local tools for the counting and positioning work, and only
calls the cloud models for surface damage and the final judgement.

**Why not just average all the anomaly scores?**
Imagine a board with ten perfect connectors and one missing critical power capacitor. A plain
average gives a low score, and the board looks fine. That is the wrong answer. So the fusion stage
works differently:

- It computes a weighted average, where a structural finding counts more than a label finding.
- It also takes the single worst score.
- It blends the two, 65% average and 35% worst.
- And if the worst score reaches 0.75, that score wins outright. A serious problem cannot be
  averaged away.

**Why store the evidence separately?**
So a decision can be explained later. Each specialist's raw output, its confidence, how long it
took, and its explanation are all saved, so a human can see why a verdict was reached. The current
version does this in memory and then writes the records to the database, but the separate in-memory
store is not yet written back to the database on its own.

## 9. What is not built yet

Being clear about the gaps:

- **No measured accuracy or speed figures.** The YOLO model runs for real, but no evaluation has
  been recorded. Any accuracy or timing number in a demo would be a guess.
- **No Docker packaging.** There is no `Dockerfile` and no `docker-compose.yml`.
- **No continuous integration.** Tests are run manually.
- **No signed reports.** PDFs are generated with text and tables only. No hashing, no signature, and
  no images embedded in the report.
- **No rate limiting** on any endpoint.
- **No image alignment step.** There is no rotation or alignment handling anywhere, and none is in
  the roadmap. Tilted photos are not corrected before analysis.
- **Fallback threshold alignment.** The judge's offline fallback rule marks `reject` at 0.65 fraud probability, while the policy stage's independent numeric threshold is 0.70. However, the policy engine explicitly inspects `judge_verdict == "reject"`, so a judge rejection always triggers `QUARANTINE` regardless of whether the score reached 0.70.

---

*Next: [PIPELINE.md](PIPELINE.md) for the stage-by-stage detail, or
[AI_AGENTS.md](AI_AGENTS.md) for the specialist agents.*
