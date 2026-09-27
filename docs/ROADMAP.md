# Roadmap

> What is built, what is planned, and what is only an idea.
> Checked against the code in September 2026.

---

## Read this first

**The old roadmap had a different problem from the other documents.** It did not describe this
project. It described a different, larger one.

It claimed a "production complete" phase one, a judge running in about 420 milliseconds, a
TensorRT export that would cut inference from 15 ms to 3.8 ms, a federated vector mesh
synchronising worldwide in under 5 minutes, and robotic arms ejecting boards from a conveyor. **None
of that is in this repository, and none of it can be measured.**

It also called the current version `v0.1.0-production`. **The version in the code is `0.1.0`, and the
environment defaults to `development`.**

So this document does three things: says plainly what exists, lists what the project itself has
written down as deferred, and puts the Phase 2 and Phase 3 hardware ideas in a clearly marked
section at the end, with no numbers attached.

---

## Table of contents

1. [Where the project actually is](#1-where-the-project-actually-is)
2. [What is built](#2-what-is-built)
3. [What is built but not finished](#3-what-is-built-but-not-finished)
4. [What to fix first](#4-what-to-fix-first)
5. [What the project has deferred](#5-what-the-project-has-deferred)
6. [What is not built and would be new work](#6-what-is-not-built-and-would-be-new-work)
7. [The hardware ideas](#7-the-hardware-ideas)
8. [How to report a problem](#8-how-to-report-a-problem)

---

## 1. Where the project actually is

| | |
|---|---|
| Version in the code | `0.1.0` |
| Environment default | `development` |
| Tests | 204, all passing |
| Test coverage tool | None |
| Continuous integration | None |
| Docker packaging | None |
| Frontend tests | None |
| Training or evaluation script | None |
| Recorded accuracy figure | **None** |

**The honest one-line version:** a working 8-stage pipeline with a real detector, a real web app, and
a real test suite, running entirely on a laptop, with three known security holes and a set of
documented bugs that have not been fixed yet.

**The project's own notes** describe the goal as proving the pipeline works, and say explicitly that
the pipeline is validated when there is a measured precision and recall figure plus at least one
documented failure case. **Neither exists yet.** That is the single most important thing on this
roadmap.

## 2. What is built

Everything in this table is in the code and runs.

| Area | What exists |
|---|---|
| **Pipeline** | 8-stage LangGraph workflow, with a quality-failure shortcut that skips stages 2 to 7 |
| **Stage 1** | Blur, brightness, and size checks with configurable thresholds |
| **Stage 2** | Four tamper checks: error-level analysis, noise inconsistency, copy-move detection, screenshot detection |
| **Stage 3** | Vector search over 3 reference photos, using Google's embedding model with a local fallback |
| **Stage 4** | Region scheduler that reads the 3 region files and builds the work list |
| **Stage 5** | Four specialist agents run concurrently, at most 4 at a time, with per-agent failure isolation |
| **Structural agent** | Image similarity, plus real YOLO inference counting components |
| **Label agent** | Template matching against reference crops, with flat and size-mismatch fallbacks |
| **OCR agent** | EasyOCR text reading and comparison |
| **VLM agent** | Sends the image to a cloud model and parses the reply |
| **Stage 6** | Weighted fusion that will not let many clean regions average away one serious problem |
| **Stage 7** | Cloud AI judge, with a built-in rule-based fallback that needs no API key |
| **Stage 8** | Threshold rules mapping the score to an action, and PDF report generation |
| **API** | 43 routes across auth, inspections, vendors, golden images, analytics, reports, and system |
| **Live updates** | Server-Sent Events, with a 2.5 second polling fallback in the browser |
| **Database** | 5 tables, built from the models at startup. Works on SQLite and PostgreSQL |
| **Auth** | bcrypt passwords, 30-minute access tokens, 7-day refresh tokens, two roles |
| **Frontend** | 7 pages, 2 context hooks, 19 components, live progress, dual synchronised canvases |
| **Mobile access** | Cloudflare quick tunnel, started by a script, surfaced as a QR code |
| **Tests** | 204 tests across 23 files, all offline, all passing |

## 3. What is built but not finished

**These exist in some form but are not finished. This is the most useful list on the page, because
it is the shortest distance between what is there and what works.**

| Item | What is there | What is missing |
|---|---|---|
| **The review dialog** | The UI is built | It calls an endpoint that does not exist. Every submission is a 404 |
| **The final live update** | The stream sends a `verdict` event | On the main code path it carries no verdict, so the screen stays blank |
| **The phone QR fallback** | The modal is built | It makes an unauthenticated request, gets a 401, and silently falls back to a useless address |
| **The database migration** | The file exists | It is missing two columns and gets the enum values wrong. It would fail on PostgreSQL |
| **Vendor `is_active`** | The API accepts it | The column does not exist, so the change is silently dropped |
| **`vendor_id` on golden images** | The API returns it | The column does not exist |
| **PaddleOCR** | The code tries to import it | It is not in the requirements file, so it is never used |
| **Report signing** | Claimed in the old docs | No hashing exists anywhere in the backend |
| **Evidence permanence** | Claimed in the old docs | Nothing enforces it. Deleting an inspection deletes its evidence |
| **The health check** | Returns the name and version | It does not check the database, the index, or the model |
| **The judge** | Cloud model with a rule-based fallback | The fallback produces fixed reasoning. It is not a measurement of anything |

## 4. What to fix first

**This is the near-term work, and none of it is new features.**

### Before it goes anywhere public

1. **Stop registration accepting a role.** [KNOWN_ISSUES.md](KNOWN_ISSUES.md) issue 1. A few lines.
2. **Add a login check to the live stream.** Issue 2. One line.
3. **Require admin to delete a report.** Issue 11. One line.
4. **Remove the API keys from the repository and rotate them.** Issue 8.
5. **Change the signing key and the seed passwords.** Both are in the source and the readme.

### Then the broken features

6. **Fix the review dialog.** Issue 3. Point it at `/approve` or `/override` and use real verdicts.
7. **Build the final live event in one place.** Issue 4. Always include the verdict and the action.
8. **Fix the QR fallback request.** Issue 5. Use the authenticated client.
9. **Regenerate the database migration.** Issue 6.
10. **Remove or add the two dead API fields.** Issue 7.
11. **Decide what evidence permanence means, and enforce it.** Issue 9.
12. **Turn on SQLite foreign keys.** Issue 10.
13. **Add a file size limit on uploads.** Not currently in the issue list, but worth adding.
14. **Unify the two error response shapes.** Issue 14.

### Then the things that make it measurable

15. **Measure the detector.** Run it against the test split, store the results, put them in
    [YOLO_MODEL.md](YOLO_MODEL.md). Until this exists, no accuracy claim can be made.
16. **Measure the pipeline end to end.** Precision and recall on a set of known-genuine and
    known-fraud pairs, as the project's own notes ask for.
17. **Document one failure case** in detail: what the judge got wrong, and whether the component
    evidence helped or was overridden.
18. **Add a coverage tool.** Currently there is no way to know what fraction of the code is tested.
19. **Add continuous integration** so the 204 tests run on every change.
20. **Add frontend tests**, starting with the review dialog and the QR modal, since both are broken.

## 5. What the project has deferred

**These are not my suggestions. They are written down in the project's own planning notes** as
deliberate scope cuts. The reasoning is recorded too: they were cut to prove the pipeline works, not
because they are hard.

| Deferred item | Why it was cut, per the project notes |
|---|---|
| **Multi-agent debate** | A full debate loop is expensive to tune and hard to demo. One reasoning call that shows its work gives most of the value |
| **Fraud knowledge graph** | Useful at scale, not needed to prove the pipeline |
| **Fraud memory and continuous learning** | Needs history across many runs to mean anything |
| **Tool registry** | Dynamic capability routing is not needed yet |
| **Richer analytics** | Detector accuracy over time, human-override rate, and the tampering-versus-physical-fraud split all need history first |
| **5 more evidence agents** | Component, material, connector, manufacturing, and usage. The YOLO detector already covers much of what the component agent would have done |
| **Full human review workflow** | A queue, escalation rules, and a multi-reviewer audit trail. The MVP has a single approve-or-override action |
| **YOLO on the label agent** | Extending object detection to seals and logos, once the component detector is proven out |
| **A vendor management page** | A dedicated page, replacing the inline add-vendor shortcut on the new inspection form |
| **A review queue page** | A dedicated multi-reviewer queue, replacing the single action |
| **Moving to paid tiers** | Paid model tiers, proper rate limiting, and monitoring |

**One of these is worth taking first: the review queue.** It is the most requested thing in a real
quality process, and the single approve-or-override button is the thin version of it.

## 6. What is not built and would be new work

**Things a reader might expect, that simply do not exist in any form.**

| Not built | What it would take |
|---|---|
| **Docker packaging** | A `Dockerfile` for the backend and one for the frontend, plus a compose file. Starting from nothing |
| **Continuous integration** | A workflow file. One file, and it would be immediately useful |
| **Multi-tenancy** | There is no organisation concept anywhere. Every record belongs to one company implicitly |
| **Evidence search** | Evidence can be listed by inspection. There is no search across historical fraud cases |
| **A fraud pattern store** | Nothing remembers past fraud |
| **Model versioning** | One weight file, no history, no way to compare two models |
| **A second supplier's worth of reference images** | There are 3 reference photos total, one battery, one motherboard, one RAM module |
| **Automatic reference image registration** | An admin uploads an image, but there is no step that builds its region file or indexes it. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) and [PIPELINE.md](PIPELINE.md) |
| **Report templates** | One hard-coded layout |
| **Email or notification on a verdict** | Nothing is sent |
| **Scheduled or batch inspections** | One inspection at a time, started by a person |
| **A public API key scheme** | Auth is for the web app only. There is no API token for an external system |
| **An audit log of who did what** | Approvals and overrides are recorded on the inspection. There is no general log |
| **Local language models** | Everything except the two cloud calls needs no network. There is no local VLM option |
| **A real offline mode** | The two cloud agents fail to their fallbacks. The system runs, but the reasoning is much weaker |

**The second row of that list is the important one.** Three reference photos is enough to demonstrate
the pipeline. It is not enough to inspect real incoming stock, because every new part number would
need a reference photo and a hand-written region file before it could be checked.

## 7. The hardware ideas

**The old roadmap had a detailed Phase 2 and Phase 3. It is reproduced here in outline, with no
numbers, because none of it can be checked.**

**Phase 2, described as edge and hardware integration:**

- Exporting the detector to a TensorRT engine for a Jetson-class edge device
- Direct bindings for industrial GigE cameras, Basler and FLIR
- A local quantised vision model so the system works with no internet at all
- An automatic alignment step that corrects a tilted board before stage 4
- Thermal and X-ray intake for inspecting things that cannot be seen, such as solder voids under a
  chip

**Phase 3, described as enterprise and robotics:**

- Sending a hold to an ERP such as SAP or Siemens when an inspection is quarantined
- Sharing fraud signatures between sites
- Driving a pneumatic reject arm through a PLC relay

**What to be clear about:** every number attached to these in the old document was invented.
"Sub-5ms inference", "15 ms down to 3.8 ms", "under 5 minutes worldwide" — there is no measurement
behind any of it, and the project has not done any of the work.

**The first two items on Phase 2 are the only ones with a natural next step**, and only because the
detector already exists as a standard PyTorch file that any export tool can read.

**The alignment idea is the most interesting of the lot, and it is not speculative.** The pipeline
compares an incoming photo to a reference photo using a vector search, and then crops matching
regions. If the board is photographed at an angle, the crops are wrong. A homography step between
stages 3 and 4 would address a real limitation. It is a genuinely good idea and it is not built.

**The ERP and PLC items are the furthest away.** They assume the verdicts are trustworthy, which
depends on the measurement work in section 4 not being done yet. Automating a decision you have not
measured is how you get a system that confidently rejects good parts.

## 8. How to report a problem

**The old document said to open a GitHub issue with the input image, the PDF, and the raw evidence
JSON attached. Attaching the raw evidence payload is a good instinct and worth keeping.**

For a bug in this project, the most useful things to include are:

| Include | Why |
|---|---|
| The inspection ID | Everything about it can be looked up |
| What you expected | The verdict, the action, or the screen |
| What happened instead | Including the exact error text |
| Whether the cloud keys were set | If not, the rule-based judge ran, which changes the result |
| The browser console output | Several bugs, including the review dialog, only show up there |

**If you are reporting a hardware detection problem,** the image matters, but so does the reference
photo it was compared against, because most failures turn out to be a wrong region file or a photo
taken at a different angle. Only 3 reference photos exist, so this is worth checking first.

---

*Next: [INTERVIEW_100_QA.md](INTERVIEW_100_QA.md), or back to
[README.md](README.md) for the full index.*
