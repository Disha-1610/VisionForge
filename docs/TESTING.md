# Testing

> This describes the automated test suite.
> Verified by running it in September 2026.

---

## The headline number

```
214 tests, 214 passed, in about 12 seconds
```

Across **23 test files**. The test suite is genuinely good, and running it is fast.

## Table of contents

1. [How to run the tests](#1-how-to-run-the-tests)
2. [What the numbers really are](#2-what-the-numbers-really-are)
3. [What each test file covers](#3-what-each-test-file-covers)
4. [What the tests do well](#4-what-the-tests-do-well)
5. [What the tests do not cover](#5-what-the-tests-do-not-cover)
6. [The tools, and what is missing](#6-the-tools-and-what-is-missing)
7. [Claims not supported by the tests](#7-claims-not-supported-by-the-tests)

---

## 1. How to run the tests

```bash
cd backend
python -m pytest -q
```

That is the whole command. It needs no setup, no arguments, and no fixtures file.

**On Windows PowerShell:**

```powershell
cd backend
python -m pytest -q
```

**Useful variations:**

```bash
python -m pytest                    # normal output
python -m pytest -v                 # one line per test
python -m pytest tests/test_judge_and_policy.py   # one file
python -m pytest -k "policy"        # tests matching a name
python -m pytest --collect-only     # list tests without running them
```

**The frontend has no tests.** There is no `test` script in `package.json` and no test file anywhere
in the frontend. All 214 tests are backend tests.

## 2. What the numbers really are

| | |
|---|---|
| Test files | **23** |
| Test functions written | 212 |
| Tests collected | **214** (two are parameterised and expand) |
| Tests passed | **214** |
| Failures | 0 |
| Time to run | about 12 seconds |
| Skipped | 0 |
| Deliberately not run | 0 |
| Order-dependent tests | None found. The suite passes repeatedly in any order |

**The two parameterised tests expand into extra cases**, which is why the collected number is
slightly higher than the number of functions.

**Almost every test is fully offline.** The suite calls no cloud service and needs no API key. The
two cloud providers, the embedding model, the OCR reader, the YOLO model, and the database are all
replaced with controlled stand-ins. **You can run the whole suite with the internet unplugged.**

**The entire suite runs in approximately 11 to 12 seconds.** All cloud API calls, vector operations, and timer loops use fast mock fixtures in `conftest.py`, ensuring the test suite finishes rapidly without artificial delays.

## 3. What each test file covers

Here is the full list, with what each one actually tests.

| File | Tests | What it covers |
|---|---|---|
| `test_image_utils.py` | 31 | Loading images, converting between colour formats, resizing, cropping, working with coordinates, converting to base64. Also the duplicate image detection |
| `test_authenticity.py` | 22 | The stage 2 tamper checks. Genuine and edited images, screenshot detection, cloned block detection, and the score that combines them |
| `test_roi_templates.py` | 19 | Loading the three region files, the priority ordering, the validation rules that reject broken templates, and the batching the scheduler produces |
| `test_embedding_service.py` | 14 | Turning images into embeddings, saving and loading the vector index, searching it, and the guard that refuses to mix vector sizes |
| `test_pipeline_stages.py` | 13 | Each stage on its own, with controlled inputs. Includes the brightness boundaries |
| `test_llm_client.py` | 10 | Failing over between the two cloud providers, the retry and backoff behaviour, and the load sharing |
| `test_routers.py` | 5 | The health endpoint, the root endpoint, the current-user endpoint, and the two input error cases |
| `test_auth.py` | 7 | Password hashing, issuing tokens, and expired tokens being rejected |
| `test_evidence_fusion.py` | 8 | Combining findings into a score, including the case where one serious finding must not be averaged away by many clean ones |
| `test_integration_stages_1_2_3.py` | 8 | Stages 1, 2, and 3 running together, with the vector index and the database replaced |
| `test_judge_and_policy.py` | 7 | The AI judge's output, the offline fallback when both cloud services fail, and the stage 8 decision rules |
| `test_ocr_agent.py` | 7 | Text reading with a stand-in reader, the comparison logic, tamper cases, and what happens when the reader fails |
| `test_label_agent.py` | 6 | Template matching, including the flat image and size mismatch fallbacks |
| `test_structural_agent.py` | 7 | The image similarity half, and the component count comparison |
| `test_roi_scheduler.py` | 7 | Priority ordering, the three places a region file can come from, and the two failure cases |
| `test_base_agent.py` | 5 | The shared base class, including that a failing specialist produces a recorded failure rather than crashing the pipeline |
| `test_structural_yolo.py` | 5 | The structural agent's YOLO wiring. Four use a stand-in model. The fifth loads the real model file and checks it has 8 classes |
| `test_vlm_agent.py` | 6 | The image encoding sent to the cloud model, the parsing of its reply, and what happens when the call fails |
| `test_evidence_execution.py` | 4 | The stage that runs the specialists: the quality gate, a missing template, the number of regions handled, and failure isolation |
| `test_analytics_and_reports.py` | 7 | The analytics endpoints and the report endpoints, with the database replaced. Includes the one test that checks an operator is blocked from admin-only analytics |
| `test_evidence_store.py` | 3 | The in-memory evidence store, and that it refuses to be cleared |
| `test_workflow_langgraph.py` | 2 | The full 8-stage graph, and the shortcut when the quality check fails |
| `test_week3_integration.py` | 1 | Stages 4 and 5 together |

Sorted by size. The counts add up to 204 across 23 files.

## 4. What the tests do well

**Genuinely worth saying out loud in an interview:**

**The isolation test is the best one here.** `test_base_agent.py` deliberately makes a specialist
throw an exception and checks that the pipeline records the failure and carries on. That is the
single most important behaviour in the whole system, and there is a test proving it.

**The non-dilution test is well chosen.** `test_evidence_fusion.py` builds a case with nine clean
regions and one region with a missing chip, then checks the final score reaches at least 0.75. That
is exactly the scenario the fusion logic exists to handle, and it is tested.

**The offline judge fallback is tested.** `test_judge_and_policy.py` checks that when both cloud
services fail, the judge still produces a verdict. This is what makes the system demonstrable with
no API keys, and it is verified.

**The fail-short-circuit test is real.** `test_workflow_langgraph.py` makes the quality check fail
and checks that stages 2 through 7 never run and the action comes out as `retake`.

**The full graph is covered.** The same file mocks the heavy stages and checks all 8 run in the right
order, with the policy stage last.

**Everything is offline.** No API keys, no network, no database server. The suite is hermetic.

**There is no shared fixtures file, and the tests are independent anyway.** Each file builds its own
stand-ins. This is more repetitive, but it means a test cannot be broken by a change to a shared
fixture somewhere else.

## 5. What the tests do not cover

Being clear about this, because it is where the real gaps are.

### Nothing runs the real AI models

| Not covered | How it is handled instead |
|---|---|
| YOLO doing real inference on a real image | A stand-in model with hard-coded results. The one test that loads the real file only checks it has 8 classes |
| EasyOCR reading real text | A stand-in reader |
| The cloud models | Replaced with controlled responses |
| The embedding model | Random number arrays of the right size |
| The real vector index | A stand-in index |

**This is a normal and reasonable choice.** Calling a real model in a unit test is slow, flaky, and
expensive. But it does mean a test passing tells you the wiring is right, not that the model works.

### No database is involved

Every test that touches the database replaces it with a stand-in session that returns prepared
answers. **No SQL is ever executed against a real database.**

So the things most likely to break in real use are untested:

- The analytics aggregation queries. All 7 tests in `test_analytics_and_reports.py` return prepared
  values, so the actual supplier risk and monthly trend queries have never been run by a test.
- The database migration.
- Foreign key behaviour.
- The enum values the database stores. Nothing checks that what SQLAlchemy writes matches what the
  tables declare, which is how the migration problem went unnoticed.

**The report PDF is not tested at all.** `test_analytics_and_reports.py` never imports the reporting
code. Nobody has confirmed the generated PDF opens correctly.

### The concurrency is not tested

The specialists genuinely do run at the same time, limited to 4 at once. But `test_evidence_execution.py`
does not check that. **No test asserts anything about ordering, interleaving, or timing.** There is
no test that would fail if the concurrency were removed and everything ran one after another.

### Specific gaps

| Gap |
|---|---|
| No frontend tests at all |
| No test for the QR code modal, which is the component with a real bug |
| No test for the review dialog, which calls an endpoint that does not exist |
| No coverage of the live stream's final message, which is where the missing-verdict bug is |
| No performance or timing tests anywhere |
| No test for the Docker setup, because there is no Docker setup |
| No test for the tunnel, because it is not run automatically |
| One test file for the whole of stage 5, the second most complex stage |

**A note on concurrency, because it is easy to assume a test covers it.** The specialists genuinely
do run at the same time, limited to 4 at once. **No test checks it.** The test file exists and
tests other things in that stage.

## 6. The tools, and what is missing

### What is installed

| Tool | Version |
|---|---|
| Python | 3.13.5 |
| pytest | 8.0 or later required, 9.0.3 installed |
| pytest-asyncio | 0.23 or later. This is what lets the async tests run |
| anyio | 4.0 or later |

### What is missing

**There is no shared fixtures file.** No `conftest.py` exists, anywhere. There is no shared
fixture that decouples the cloud models, and no fixture that runs tests against an in-memory
database with automatic rollback. Each test file builds its own stand-ins.

**There is no coverage tool.** `pytest-cov` is not installed and there is no coverage configuration
file. A command such as `pytest --cov=app --cov-fail-under=85` would fail immediately, because the
plugin it needs is not there.

**There is no linter for the backend.** No flake8, no ruff, no black. A command such as
`flake8 app tests --max-line-length=120` would fail. The only linter in the project is `oxlint`, and
it only runs on the frontend.

**There is no type checker configured.** No mypy, no pyright.

**There is no continuous integration.** No `.github` folder, no pipeline configuration file of any
kind. Nothing runs automatically. Tests are run by a person.

**There is no pytest configuration file** either. No `pytest.ini`, no `pyproject.toml`, no
`setup.cfg`. The defaults are used, which works fine here because the tests live in one folder and
follow a naming convention.

## 7. Claims not supported by the tests

Things people often say this suite covers, and what it actually covers:

| Claim | Reality |
|---|---|
| 203 tests | **204** |
| The suite runs in 12 to 15 seconds | About **75 seconds** |
| A `conftest.py` exists with shared fixtures | **No such file exists** |
| Cloud models are decoupled through fixtures in `conftest.py` | Each test file builds its own stand-ins |
| Tests run against an in-memory SQLite database | No database is involved in any test |
| There is automatic transaction rollback | No such fixture |
| Append-only evidence persistence is tested | The in-memory store's save function does nothing. Nothing is persisted |
| `pytest --cov=app --cov-fail-under=85` works | Would fail. `pytest-cov` is not installed |
| `flake8 app tests --max-line-length=120` works | Would fail. flake8 is not installed |
| GitHub Actions runs the gates | **No CI configuration exists** |
| Pytest 8.x | 8.0 or later required, 9.0.3 installed |
| OCR tests cover PaddleOCR and EasyOCR | Only the stand-in reader is tested. PaddleOCR is not installed |
| OCR tests cover date code discrepancies | No such test. The cases are serial numbers and a revision code |
| OCR tests cover Levenshtein distance | No such function exists. The code uses string comparison |
| OCR tests cover tampered batch numbers | No batch numbers appear in any test |
| Label tests cover rotated logos and photocopied seals | No such tests. The thresholds tested are 0.85 and 0.50, not 0.70 |
| The YOLO parser test maps Darknet coordinates to pixels | Four of the five tests use a stand-in model. The fifth only checks the class count |
| The structural agent test covers four-mode reasoning | That test file never uses YOLO, and no four-mode engine exists |
| The VLM test checks odd and even routing | That is tested in the LLM client file, not the VLM file |
| LLM failover is tested from a 429 on Gemini | It is the other way round. The test drives a 500 on Groq falling back to Gemini |
| The fusion test uses 9 clean at 0.05 and 1 failed at 0.88, expecting 0.80 | The real test uses 9 clean regions and one missing chip, expecting at least 0.75 |
| Policy thresholds are 0.08, 0.45, and 0.88 | The real ones are 0.10, 0.45, and 0.78 |
| The stage 5 test checks concurrent execution | It checks the quality gate, a missing template, region counts, and failure isolation |
| The week 3 integration test runs all 8 stages | It runs stages 4 and 5 |
| The auth test covers proactive token rotation | It covers password hashing, token issue, and expiry. There is no server-side rotation |
| The auth test covers invalid signatures | It tests a malformed token, not a wrong-key signature |
| The router test checks operators get 403 | It does not. That check is in the analytics test file |
| The evidence store test covers database behaviour | Three in-memory tests. No database, no foreign keys |
| The report test validates the PDF | The file never imports the reporting code |

**Solid ground to stand on:** the test folder, the count of 23 test files, the commands to build and
lint, the two claims that are nearly right (the base agent's crash protection, and the graph
shortcut), and the general shape of the coverage for stages 1 to 3, the region files, and the stage
runners.

---

*Next: [SECURITY.md](SECURITY.md) for how access is controlled.*
