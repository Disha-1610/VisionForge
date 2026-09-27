# The Inspection Pipeline

> This walks through all 8 stages, in order, explaining what each one checks and why.
> Checked against the code in September 2026.

---

## Table of contents

1. [The big picture](#1-the-big-picture)
2. [What gets passed between stages](#2-what-gets-passed-between-stages)
3. [Stage 1: Is the photo usable?](#3-stage-1-is-the-photo-usable)
4. [Stage 2: Was the photo edited?](#4-stage-2-was-the-photo-edited)
5. [Stage 3: What part is this?](#5-stage-3-what-part-is-this)
6. [Stage 4: What should we look at?](#6-stage-4-what-should-we-look-at)
7. [Stage 5: Running the four specialists](#7-stage-5-running-the-four-specialists)
8. [Stage 6: Turning findings into one score](#8-stage-6-turning-findings-into-one-score)
9. [Stage 7: Asking the AI judge](#9-stage-7-asking-the-ai-judge)
10. [Stage 8: Applying the rules](#10-stage-8-applying-the-rules)
11. [The decision table](#11-the-decision-table)
12. [Known problems](#12-known-problems)

---

## 1. The big picture

An inspection has 8 stages. They run in a fixed order, because each one narrows down what the next
needs to do.

```
   photo uploaded
        |
   1. quality_check ------ failed ---------------------------+
        |                                                    |
   2. authenticity                                          |
        |                                                    |
   3. reference_match                                       |
        |                                                    |
   4. roi_scheduler                                         |
        |                                                    |
   5. evidence_execution  (two passes)                      |
        |                                                    |
   6. evidence_fusion                                       |
        |                                                    |
   7. judge                                                 |
        |                                                    |
   8. policy_engine <----------------------------------------+
        |
   save to database + build PDF + tell the frontend
```

**There is exactly one shortcut in the whole graph.** If the photo fails the quality check at stage
1, it jumps straight to stage 8 and records a "retake" action. Stages 2 to 7 never run, so no AI
quota is spent on a bad photo.

Every other stage always runs, whatever happened before.

**The old documentation claimed three shortcuts:** one for a failed tamper check going to
quarantine, and one for unrecognised hardware skipping the specialists. **Neither exists.** A photo
that fails the tamper check still goes through all the remaining stages, and ends up with a
`vendor_verification` action rather than a quarantine. And hardware that does not match a reference
still goes to stage 4.

## 2. What gets passed between stages

Stages do not return raw dictionaries. Each one returns a small result object with four parts:

| Part | What it holds |
|---|---|
| `stage` | Which stage this was |
| `status` | `passed`, `flagged`, or `failed` |
| `data` | Anything the next stage needs |
| `error` | The reason, if it failed |
| `processing_time_ms` | How long it took |

The things that carry forward are held in a `WorkingMemory` object.

**A naming caution, because the old documentation got this wrong.** The LangGraph state type is
`PipelineGraphState`, and it only has three fields: `inspection_id`, `state`, and `error`. The
detailed state is `WorkingMemory`.

**The real field names, so you can read the code:**

| Field | What it holds |
|---|---|
| `image_paths` | The uploaded files. A flat list of strings |
| `part_code` | The part number of the matched reference |
| `declared_product_type` | What the operator said it was |
| `hardware_category_mismatch` | Whether the photo does not match the declared type |
| `similarity_score` | How well it matched. **Not** called `reference_similarity` |
| `roi_execution_plan` | The work plan. **Not** called `scheduled_rois` |
| `evidence_refs` | IDs pointing at stored evidence. **Not** a list of evidence cards |
| `fused_evidence` | The combined findings |
| `fraud_probability` | The score being built up. **Not** called `composite_fraud_score` |
| `stage_history` | What each stage did |

**Four field names the old documentation invented do not exist anywhere in the code:** `blur_score`,
`brightness_score`, `anomaly_map`, and `quality_failure_reason`. Blur and brightness live in the
stage result's `data`, not in the carried state. There is no anomaly map.

## 3. Stage 1: Is the photo usable?

A bad photo produces a meaningless result, so this stage rejects bad photos early.

### What it checks

| Check | Rule | Setting |
|---|---|---|
| Sharpness | Reject if the Laplacian variance is under 100.0 | `MIN_BLUR_VARIANCE` |
| Too dark | Reject if average brightness is under 40.0 | `MIN_BRIGHTNESS` |
| Too bright | Reject if average brightness is over 220.0 | `MAX_BRIGHTNESS` |
| Too small | Reject if under 640 wide or under 480 tall | `MIN_IMAGE_WIDTH`, `MIN_IMAGE_HEIGHT` |
| Duplicate | Reject if it looks the same as one seen recently | `DUPLICATE_HASH_MAX_DISTANCE` |

### How sharpness is actually measured

The photo is converted to greyscale, then a Laplacian filter is applied and the variance of the
result is calculated.

**Two corrections to the old documentation:**

- It said a 3x3 kernel is used. The code uses the default kernel size, which is 1x1.
- It said brightness is measured "across all channels". The photo is converted to **greyscale**
  first, and the brightness is a plain average of that greyscale. **There is no histogram.** The
  word "histogram" in the old documentation was wrong.

### The duplicate check, which the old documentation left out

The stage also computes a perceptual hash, sometimes called an average hash. This reduces the image
to a short fingerprint of its overall brightness pattern. Two images of the same board will have
very similar fingerprints, even if one is slightly brighter.

Fingerprints are compared by counting how many bits differ. If two are within 4 bits of each other,
the image is treated as a repeat and rejected.

This is genuinely useful: it catches an operator submitting the same photo twice, and it catches a
fake reference image copied from an existing one.

### What happens on failure

The graph jumps straight to stage 8. The action is set to `retake`, and the operator is told to
photograph the part again. **The verdict field is left alone.** The old documentation said a quality
failure produces a `reject`. It does not. Only stage 7 sets a verdict, and it is skipped here.

## 4. Stage 2: Was the photo edited?

If someone edited a serial number in image editing software, the edit usually leaves traces. This
stage looks for them. Four separate checks run.

### 4.1 Error Level Analysis

This is the best-known technique. The photo is re-saved as a JPEG at a known quality level, here 95.
The difference between the original and the re-saved version is an "error map".

Why this works: in an untouched photo, the error is spread evenly. In an edited region, the pixels
were changed and they compress differently, so the error jumps.

The code does not simply scale the error map to its maximum, as the old documentation described. It
compares the standard deviation of the error against a threshold, then scores the result as:

```
score = min(1.0, error_standard_deviation / (threshold * 3.0))
```

### 4.2 Noise consistency

The photo is divided into a 4x4 grid of patches. Each patch's noise level is measured and compared.
In a genuine photo the patches should be similar. Patches that are much noisier than the others
suggest a local edit.

**The old documentation left this out entirely.**

### 4.3 Screenshot detection

A photo of a screen has a very even look. The code measures how uniform the image is, and if it is
more uniform than 0.92 it is flagged as a screenshot. The old documentation did not mention this.

### 4.4 Cloned block detection

This is the most forensically useful check, and the old documentation did not mention it either.

Someone who clones a serial number from one part of the photo to another has copied a block of
pixels. The code slides a 16x16 window across the image looking for near-identical blocks in
different places. A block counts as suspicious if:

- It is in a different location, and
- Its similarity score is over 200, and
- The duplicated area is more than 3% of the image.

### The thresholds

| Setting | Value | What it does |
|---|---|---|
| `AUTHENTICITY_HARD_BLOCK_THRESHOLD` | 0.35 | Below this, the photo is not trustworthy |
| `AUTHENTICITY_FLAG_THRESHOLD` | 0.50 | Above this, the photo is flagged |
| `ELA_RESAVE_QUALITY` | 95 | Quality used when re-saving |
| `NOISE_PATCH_GRID` | 4 | Grid size for the noise check |
| `SCREENSHOT_UNIFORMITY_THRESHOLD` | 0.92 | Above this, treated as a screenshot |
| `COPY_MOVE_BLOCK_SIZE` | 16 | Window size for cloning |
| `COPY_MOVE_MATCH_THRESHOLD` | 200 | Similarity needed to count as a clone |
| `COPY_MOVE_MIN_DUPLICATE_RATIO` | 0.03 | Minimum duplicated area |

**The old documentation said a failed tamper check sends the case straight to quarantine.** It does
not. The pipeline carries on through all remaining stages. The flagged photo ends up with a
`vendor_verification` action at stage 8.

## 5. Stage 3: What part is this?

The incoming photo is turned into a list of numbers and compared against the reference images using
a FAISS vector index.

### How the matching works

1. The photo is resized and turned into an embedding, 3,072 numbers using Google's
   `gemini-embedding-2` model.
2. FAISS searches the index for the closest match.
3. The result must score at least 0.75 to be accepted. This is `SIMILARITY_THRESHOLD`.
4. The best match's ID is looked up to get the reference record, which points at the region
   template file.

If Google is unavailable, the code falls back to OpenCLIP `ViT-B-32`, which produces 512 numbers.
The code checks the sizes match and refuses to mix them.

### What happens when nothing matches

**The old documentation said unmatched hardware is classified `UNKNOWN_HARDWARE` and skips straight
to stage 8.** There is no such status anywhere in the code.

What actually happens is much quieter. If the best match scores below 0.75:

- The match status becomes `flagged`.
- The reason is set to `below_similarity_threshold`.
- **The pipeline carries on to stage 4 like normal.**

So an unrecognised board still gets its regions examined. That may or may not be what you want, but
it is what the code does.

### A second check the old documentation left out

There is also a hardware category check. If the operator said this is a motherboard but the matched
reference is a battery pack, that is recorded as a `hardware_category_mismatch`. **This has a real
effect at stage 8** — it pushes the result to `vendor_verification` even if the fraud score is low.
Someone swapping a battery into a laptop and labelling it a motherboard would be caught here.

## 6. Stage 4: What should we look at?

This stage reads the reference's region template file and builds a work plan.

### Region types

Every region is one of four types:

| Type | What it is |
|---|---|
| `text` | Serial numbers, part codes. Goes to the OCR specialist |
| `label` | Logos, seals, safety stamps. Goes to the label specialist |
| `structural` | Component areas. Goes to the structural specialist |
| `visual` | General surface. Goes to the VLM specialist |

**The old documentation called the fourth type `SURFACE`.** The actual name is `visual`.

### How regions are prioritised

The template lists regions in order of importance. The code sorts them using a fixed priority
order defined in one place, then groups them.

**The old documentation said this used a Python priority queue.** There is no priority queue. The
ordering comes from a fixed sort.

### How the work is grouped, which the old documentation missed

This is the part worth knowing. The scheduler does not produce a flat list. It produces a **batched
plan**:

- Regions are grouped by their priority level **and** by which specialist will handle them.
- Batches run in order: most serious first, then important, then routine.

This means the most important regions are analysed first, and results come back sooner, even though
the full set still runs.

### The three shipped templates

| Part | Regions |
|---|---|
| Motherboard | **8** |
| Battery pack | **7** |
| RAM module | **5** |

**The old documentation said the motherboard has 6 regions. It has 8.**

### Validation

The scheduler also checks the template file before trusting it. It rejects templates with duplicate
region IDs, regions with coordinates outside the image, and regions marked as text or label that
have no criticality rating. A broken template stops the inspection with a clear error rather than
producing nonsense.

## 7. Stage 5: Running the four specialists

### This stage runs twice, not once

**The old documentation showed a single flat four-way split, running in parallel once.** That is
not what happens. There are two passes:

- **Pass one** sends each region to whichever specialist the template assigns.
- **Pass two** sends every region the structural specialist handled to the VLM specialist, so the AI
  can double-check the automated component counts.

This is a genuine design choice: YOLO counts components, but it cannot tell you whether a component
that is present is actually damaged. Pass two gives the AI a chance to look at the same regions with
a different tool.

### How work is limited

- Regions are processed with `asyncio.gather`, so several run at the same time.
- A counter limits how many run at once, to **4** at a time. Without this, a template with 20
  regions would try to start 20 AI calls simultaneously and hit rate limits.
- Each specialist's VLM calls are shared out evenly between the two cloud providers, alternating by
  region number.

### When an agent fails

**This is well designed and worth highlighting.** If a specialist throws an exception, the pipeline
does not stop. A result is recorded with `failed` set to true and the error message stored. The
fusion stage then treats that failure as a mild anomaly of 0.20.

So one agent crashing produces a slightly suspicious result rather than a dead inspection.

### What each specialist does

| Specialist | Method | Threshold |
|---|---|---|
| OCR | EasyOCR, compared with string similarity | 0.85 |
| Label | OpenCV template matching | 0.80 |
| Structural | YOLO11n detection plus image similarity | 0.80 for similarity, 0.20 for detection confidence |
| VLM | Google Gemini 2.5 Flash and Groq Qwen 3.8 27B | Based on the AI's own answer |

Full detail is in [AI_AGENTS.md](AI_AGENTS.md).

**One correction:** the old documentation listed PaddleOCR as the primary text reader. PaddleOCR is
not in the requirements file, so in a clean install the import always fails and **EasyOCR always
runs**. The fallback is silent.

## 8. Stage 6: Turning findings into one score

This is the most important stage to get right, and the old documentation described it incorrectly.

### The problem it solves

Imagine a board with 10 perfect connectors and one missing critical power capacitor. A plain average
would give a low score and the board would look fine. That is the wrong answer.

### What the code actually does

**Step 1: Weight each finding by which specialist produced it.**

| Specialist | Weight |
|---|---|
| Structural | 0.45 |
| OCR | 0.40 |
| VLM | 0.35 |
| Label | 0.30 |

A structural finding counts for more than a label finding, because counting components is more
reliable than matching a logo.

**Step 2: Apply a severity multiplier for VLM findings only.**

| Severity | Multiplier |
|---|---|
| Critical | 1.0 |
| High | 0.85 |
| Medium | 0.55 |
| Low | 0.25 |

**Step 3: Blend the average with the worst single finding.**

```
weighted_average = sum(anomaly × weight) / sum(weight)
blended          = 0.65 × weighted_average + 0.35 × worst_single_finding
```

**Step 4: Protect a serious finding.**

```
if worst_critical_finding >= 0.75:
    final = min(1.0, max(worst_critical_finding, blended))
else:
    final = min(1.0, blended)
```

That `0.75` check is the real protection. Once a single critical finding reaches 0.75, it wins
outright and no amount of clean results can average it away.

**The old documentation got this wrong in three ways:**

- It said the blend was 70% average and 30% worst. **It is 65% and 35%.**
- It described a "criticality weight" ranging from 1.0 to 1.5. **No such weight exists.** The real
  weights are the fixed per-specialist numbers above.
- It did not mention the 0.75 override, which is the mechanism that actually does what the
  description was reaching for.

### Two extra findings get folded in

| Finding | What it contributes |
|---|---|
| The photo was flagged as edited | 0.85 × 0.40 |
| The reference match was weak | 0.70 × 0.30 |

So a photo that looks tampered with cannot score low just because the components all look fine.

### Failed agents

A failed agent contributes a fixed anomaly of 0.20. Not alarming on its own, but it stops a broken
agent from silently looking clean.

## 9. Stage 7: Asking the AI judge

The judge reads everything the specialists found and writes a human-readable explanation.

### It does not look at images

**The judge is text-only.** It never sees the photo. It reads the findings as text. This is
deliberate: it keeps the call fast, cheap, and repeatable, and it means the judge's answer is
grounded in the specialists' actual measurements rather than its own impression of a blurry crop.

### Which model

| Order | Model |
|---|---|
| 1st | Groq `gpt-oss-20b` |
| 2nd | Google Gemini 2.5 Flash |
| 3rd | A set of fixed rules in the code |

**Groq is the primary, not the backup.** The old documentation had this backwards in several
places.

**The third option matters more than it sounds.** If both cloud services fail, the code falls back to
a simple set of rules that always produces a verdict. This is tested. It means the system can be
demonstrated with no internet connection and no API keys, and it will never leave an inspection with
no verdict at all.

### What it returns

```json
{
  "verdict": "reject",
  "confidence": 0.9,
  "fraud_category": "missing_components",
  "root_cause_reasoning": "Capacitor C12 is absent from the power rail...",
  "recommendations": "Quarantine the lot and notify the supplier."
}
```

**Five fields. The old documentation described `root_cause` and `risk_assessment`, neither of which
exists.** The real field is `root_cause_reasoning`. There is no `risk_assessment` and no
`risk_level` field anywhere.

Valid verdicts are lowercase: `accept`, `reject`, `review`, `pending`. The old documentation showed
them in capitals.

### What the judge is given

Not the raw evidence records. It is given a summary built from them: the part code, the declared
product type, whether there was a category mismatch, the location, the authenticity score and
whether it was flagged, the reference similarity, the fraud score, the primary fraud category, a
list of detected issues, a bulleted summary of each specialist's findings, and a per-region summary.

**The old documentation said the judge receives "the complete list of structured evidence cards"
plus the supplier's identity and historical risk rating.** It receives neither the full raw records
nor any supplier risk information.

## 10. Stage 8: Applying the rules

This stage turns the score into a decision, saves everything, and builds the PDF.

### The rules, in the order they are checked

1. **The photo failed the quality check** → action `retake`.
2. **Fraud score is 0.70 or higher** → action `quarantine`.
3. **The judge said `reject`** → action `quarantine`.
4. **The fraud category is a serious one** → action `quarantine`.

   The serious categories are: `missing_components`, `counterfeit_rework`, `tampered_serial`.
5. **The fraud score is 0.30 or higher** → verdict `review`, action `vendor_verification`.
6. **The photo was flagged as edited** → action `vendor_verification`.
7. **There was a hardware category mismatch** → action `vendor_verification`.
8. **Otherwise** → verdict `accept`, action `accept`.

### What gets saved

- The inspection record, with the status, verdict, policy action, fraud score, category, root cause,
  and reference similarity all filled in.
- One evidence row per specialist finding.
- A PDF report written to `backend/data/reports/`.

### About the PDF

**What it really is:** a ReportLab document with text and tables. It includes the case number, the
supplier name, the verdict, the policy action, the fraud score, the written explanation, and a
table of the evidence findings.

**What the old documentation claimed, and the truth:**

| Claimed | Reality |
|---|---|
| A SHA-256 hash stamp proving it was not altered | No hashing anywhere. `hashlib` is not even imported |
| Cryptographically signed | Unsigned |
| Side-by-side comparison images with boxes drawn on them | No images in the report at all |
| The operator's ID | Only the case number and supplier name are included |

There is a "chain of custody sign-off" section, but it is a printed table of empty fields for
someone to write on. Nothing is filled in and nothing is verified.

## 11. The decision table

This is the whole thing in one table. The fraud score runs from 0 to 1.

| Fraud score | Other conditions | Verdict | Action |
|---|---|---|---|
| Any | Quality check failed | not set | `retake` |
| 0.70+ | Any | `reject` | `quarantine` |
| Below 0.70 | Judge said `reject` | `reject` | `quarantine` |
| Below 0.70 | Category is serious | `reject` | `quarantine` |
| 0.30 to 0.69 | None of the above | `review` | `vendor_verification` |
| Below 0.30 | Photo flagged as edited | `accept` | `vendor_verification` |
| Below 0.30 | Category mismatch | `accept` | `vendor_verification` |
| Below 0.30 | Clean | `accept` | `accept` |

**Two things the old documentation got wrong here:**

- **It said the review band starts at 0.20. It starts at 0.30.** A score of 0.25 results in an
  accept, not a review.
- **It said a flagged photo goes to quarantine. It goes to `vendor_verification`.**

**The valid values are:**

- Verdicts: `accept`, `reject`, `review`, `pending`
- Actions: `accept`, `retake`, `quarantine`, `vendor_verification`

The old documentation used a different set of names in different places, including `VERIFIED`,
`TAMPERED`, and `VERIFY`. None of those exist.

## 12. Known problems

**1. The judge's fallback and the policy stage use different thresholds.**
When the judge falls back to its own rules, it rejects at 0.65. The policy stage quarantines at
0.70. A score between those two values gets a `reject` verdict from one and a `review` from the
other. This is not reconciled anywhere.

**2. Unmatched hardware is not handled clearly.**
Below the similarity threshold, the pipeline sets a flag and carries on to stage 4. An unrecognised
board is analysed as though it matched something. Whether that is intended or not, it is not what
the documentation claimed.

**3. A failed tamper check does not stop the pipeline.**
An edited photo still goes through all the specialists, which wastes quota on an image already known
to be unreliable. It is caught at stage 8, but late.

**4. There is no measured timing.**
**The old documentation gave precise timings for every stage and for the whole inspection** — 0.2
seconds for the gates, 3.2 seconds overall, and so on. **No benchmark has ever been run.** There is
no timing script in the project and no recorded results. The two pipeline stages that call cloud
models each allow 10 seconds before giving up, so the theoretical worst case is well over 20
seconds, not under 4.

**Do not quote any timing figure for this system.**

**5. Stage 5 runs the specialists on a plan built from a template that may not match the photo.**
If a reference image and its region template are out of step, the regions will not line up. Nothing
checks that the template matches the image it belongs to.

---

*Next: [AI_AGENTS.md](AI_AGENTS.md) for the four specialists in detail.*
