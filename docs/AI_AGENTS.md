# The AI Specialists

> This describes the four specialists that examine the board, and the AI judge that reads their
> findings.
> Checked against the code in September 2026.

---

## Table of contents

1. [Why four specialists instead of one model](#1-why-four-specialists-instead-of-one-model)
2. [The shared base class](#2-the-shared-base-class)
3. [The standard result](#3-the-standard-result)
4. [The OCR specialist](#4-the-ocr-specialist)
5. [The label specialist](#5-the-label-specialist)
6. [The structural specialist](#6-the-structural-specialist)
7. [The VLM specialist](#7-the-vlm-specialist)
8. [The AI judge](#8-the-ai-judge)
9. [Spreading the load between cloud providers](#9-spreading-the-load-between-cloud-providers)
10. [When things go wrong](#10-when-things-go-wrong)
11. [What the old documentation got wrong](#11-what-the-old-documentation-got-wrong)

---

## 1. Why four specialists instead of one model

Sending a whole circuit board to one large AI model does not work well. The image gets shrunk to
fit, so a capacitor smaller than a grain of rice becomes an unrecognisable smudge. Asking a model to
count forty identical components gives unreliable answers. And every full-image call uses up API
quota.

So VisionForge splits the work. Each specialist uses the cheapest reliable method for the job it
does, and only the two hardest jobs involve a cloud AI model.

| Specialist | Job | Method | Cloud AI? |
|---|---|---|---|
| OCR | Read text and serial numbers | EasyOCR | No |
| Label | Match logos and seals | OpenCV template matching | No |
| Structural | Count components | YOLO11n plus image similarity | No |
| VLM | Judge surface damage | Gemini and Groq | **Yes** |
| Judge | Write the final explanation | Groq and Gemini | **Yes** |

Two of the five use a cloud model. Three run entirely on the local machine.

## 2. The shared base class

All four specialists inherit from one base class, which gives them the same shape and the same
safety net.

**What the base class provides:**

- **Crash isolation.** If a specialist throws an exception, the base class catches it and returns a
  normal result with `failed` set to true and the error message stored. The inspection carries on.
  This is tested.
- **Timing.** Every result records how long the specialist took, in milliseconds.
- **A consistent interface.** Every specialist is called the same way, so the pipeline does not need
  to know what each one does internally.

**The subclasses have to implement two things:** the actual detection work, and how to turn their
raw output into the standard result shape.

## 3. The standard result

Every specialist returns the same structure, so the pipeline can treat them identically.

| Field | What it holds |
|---|---|
| `evidence_id` | A unique ID for this finding |
| `roi_id` | Which cropped region this came from |
| `roi_type` | `text`, `label`, `structural`, or `visual` |
| `detector_name` | Which specific detector, e.g. `ocr_agent` |
| `confidence` | How sure it is, from 0 to 1 |
| `evidence` | The measured value, such as a similarity number |
| `explanation` | A written explanation in plain English |
| `bounding_box` | Where in the image |
| `processing_time_ms` | How long it took |
| `failed` | Whether it worked |
| `failure_reason` | If not, what went wrong |

**This structure is frozen**, meaning it cannot be changed after it is created. That is a deliberate
choice: once a finding is recorded, nothing can quietly alter it later.

**Two corrections to the old documentation.** It listed the fields as `agent_id`,
`component_class`, `anomaly_score`, and `finding_summary`. None of those exist. And it showed
`detector_name` as `"paddle_ocr"` — the real values are `ocr_agent`, `opencv_match_template`, and
`structural_ssim`.

## 4. The OCR specialist

Reads text and compares it against what the reference says it should say.

### What it does

1. The cropped region is prepared. Low-contrast images get contrast enhancement first, using a
   technique called CLAHE, which improves faint stamped text without blowing out bright areas.
2. Text is read out of the region.
3. The text is read out of the matching region of the reference image.
4. The two are compared, and a similarity number between 0 and 1 is produced.
5. If the similarity drops below **0.85**, it is reported as a discrepancy.

### Which text reader is used

**EasyOCR.**

**The old documentation said PaddleOCR was the primary reader, with EasyOCR as the fallback. That is
backwards in practice.** PaddleOCR is not in the requirements file, so in any clean install the
import fails and EasyOCR always runs. The import is wrapped in a try and except, so this happens
silently.

If PaddleOCR is added later, the code calls it using an older version of its API, so that call would
need updating too. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) issue 13.

### How the comparison actually works

This is where the old documentation was most wrong.

**It described a Levenshtein distance formula:**

```
similarity = 1 - (edit_distance / longest_length)
```

**There is no edit distance function in this project.** The code uses Python's built-in
`difflib.SequenceMatcher`, which compares how the two strings line up in blocks. It is a different
algorithm with different behaviour.

**The worked example in the old documentation does not work either.** It showed a comparison scoring
about 0.76 and being flagged as a defect. Under the algorithm actually used, that same pair scores
around 0.94, which is above the 0.85 threshold, so **it would not be flagged.** The old example
described a result the code cannot produce.

**Character-level differences** are also reported. When two strings differ, the code lists which
positions changed and what the expected and actual characters were. This is a straightforward
position-by-position comparison, not an edit distance.

**The old documentation claimed the reader normalises common confusions**, such as treating the
letter O and the digit zero as the same. It does not. The only normalisation applied is collapsing
repeated whitespace and converting to upper case.

### The "not sure" case, which the old documentation left out

**This is the most important behaviour in this specialist, and it was not documented.**

If neither the uploaded region nor the reference region yields any readable text, the specialist
returns:

- similarity 0.5
- no defect
- confidence 0.2

**It reports no defect.** This is deliberate. A blank or unreadable region is not evidence of
tampering. Treating unreadable as fake would generate false alarms on every badly lit photo. The low
confidence of 0.2 records how unsure it is, so a later stage can weigh it down.

## 5. The label specialist

Checks that safety logos, seals, and stamps match the reference.

### What it does

1. The uploaded region's label area is located.
2. The reference image's same area is located.
3. The two are compared using normalised cross-correlation, which is a way of asking "how similar do
   these two patches of pixels look, regardless of brightness".
4. If the score is below **0.80**, it is reported as a discrepancy.

### The old description of this was wrong in two ways

**It said the matching is "multi-scale", testing the template at several sizes to handle rotation and
scaling.** There is no multi-scale loop. **A single `cv2.matchTemplate` call is made.** If the
template is not the same size as the region, the code resizes it and tries once more, but there is no
scale sweep.

**It described a two-tier calibration, saying a score of 0.88 or above is perfect and below 0.70 is
a defect.** There is one threshold and it is 0.80. Neither 0.88 nor 0.70 is a setting in this
specialist. The 0.70 figure appears in the judge, not here, which is likely where the old
documentation picked it up.

### Two fallbacks worth knowing about

**Flat images.** If a region is a single flat colour, cross-correlation cannot work, because there is
no pattern to match. The code notices this and falls back to comparing the average brightness
instead.

**Size mismatch.** If the reference region is a different size from the uploaded region, the code
resizes it before trying again, rather than failing.

## 6. The structural specialist

Counts components and checks whether any are missing.

### What it does, in two halves

**Half one: image similarity.** The region is compared against the same region of the reference
using SSIM, a measure of structural similarity. If that drops below **0.80**, the region is
reported as different and the detection half is skipped.

**Half two: component counting.** A YOLO model finds every component in the region, and the count is
compared against the count in the reference.

**Which SSIM is used.** The code prefers the `scikit-image` implementation, and falls back to a
hand-written OpenCV version if that library is missing. The old documentation described this as
"OpenCV SSIM" throughout, which is the less accurate of the two.

### The YOLO model

| Setting | Value |
|---|---|
| Weights file | `component_detector.pt` |
| Size | 5,468,826 bytes, about 5.2 MB |
| Classes | 8 (listed below) |
| Detection confidence | 0.20 |
| Count tolerance | 25 |
| Library | Ultralytics, version 8.3 or later |

**The 8 classes:** `capacitor`, `resistor`, `ic_chip`, `connector`, `screw`, `seal`, `battery_cell`,
`gold_pin_connector`.

**The model is real and actually runs.** It is not a mock or a placeholder. The file is in the
repository and the code loads it with the real Ultralytics library.

**The detection confidence of 0.20 is deliberately low.** In safety inspection, missing something
is much worse than flagging something that is not there. A low bar means the model finds more
candidates, and the count comparison decides whether that matters.

### The three outcomes

The comparison produces one of three statuses:

| Status | Meaning |
|---|---|
| `missing` | Fewer components found than expected |
| `extra` | More components found than expected |
| `match` | The counts agree within tolerance |

**The old documentation described "four-mode reasoning", including a fourth mode called position
drift that compared the distance between where a component was found and where it should be.** There
is no position comparison anywhere in the code. The agent has three statuses, and the third is
"match", not "count divergence".

Interestingly, the file's own comment at the top makes the same claim as the old documentation, which
is probably where it came from. The judge also has a branch for a status the agent never produces,
which is dead code.

## 7. The VLM specialist

Looks at surface damage that counting and matching cannot detect: scorch marks, solder problems,
cracks, discoloration.

### Which models

| Role | Model |
|---|---|
| Providers | Google Gemini 2.5 Flash, and Groq Qwen 3.8 27B |
| How they are shared | Alternating, by region number |

**The old documentation said "Gemini 3.5 Flash".** There is no such model. The configured value is
`gemini-2.5-flash`. This wrong name appears in several documents and even in a code comment, and
almost certainly came from a stale line in the example environment file.

### What it sends

1. The region is resized so its longest side is at most 512 pixels, using a high-quality resampling
   method. Larger images cost more and are not more useful.
2. It is converted to base64 and sent with a prompt asking for a specific JSON structure.
3. The reply is parsed into a structured report.

**The reply must match this structure:**

```json
{
  "anomaly_detected": true,
  "anomaly_severity": "high",
  "anomaly_type": "solder_bridge",
  "confidence": 0.85,
  "description": "Visible solder bridging across two adjacent pads",
  "location_hint": "lower-left quadrant"
}
```

The code enforces this structure strictly. A reply that does not fit is treated as a failure.

### Two details the old documentation missed

- Replies are capped at 1,024 tokens.
- If the first attempt fails, the code retries once with different image contrast settings before
  giving up.

## 8. The AI judge

Reads the specialists' findings and writes the explanation a human reads.

### It never looks at an image

**The judge is text-only.** It reads a written summary of what the specialists found, nothing else.

This is worth understanding, because it is deliberate. It means the judge's answer is grounded in
measured values rather than its own impression. It also means the judge cannot contradict a
specialist about what it saw, because it never saw anything.

### Three tiers, not two

| Order | What it is | When |
|---|---|---|
| 1 | Groq `gpt-oss-20b` | Normal operation |
| 2 | Google Gemini 2.5 Flash | If Groq fails |
| 3 | A fixed set of rules in the code | If both cloud services fail |

**The third tier is the important one, and the old documentation did not mention it exists.** It is
a small block of ordinary code that looks at the fraud score and the fraud category and produces a
verdict without calling anything. It is tested.

**That means the system never returns an inspection with no verdict.** It works with no API keys and
no internet connection. For a demo, or for a factory that needs the system to keep working during an
internet outage, this matters a lot.

**Its thresholds are its own, and they do not match the policy stage.** The fallback rejects at 0.65.
The policy stage quarantines at 0.70. A score in between gets different answers from the two. This
is a real inconsistency, listed in [PIPELINE.md](PIPELINE.md).

### What the judge returns

```json
{
  "verdict": "reject",
  "confidence": 0.9,
  "fraud_category": "missing_components",
  "root_cause_reasoning": "Capacitor C12 is absent from the power rail...",
  "recommendations": "Quarantine the lot and notify the supplier."
}
```

Five fields. **The old documentation showed `root_cause` and `risk_assessment`.** The real field is
`root_cause_reasoning`, and there is no `risk_assessment` field anywhere in the project. It also
showed a `risk_level` field with values like `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. That does not
exist either.

Verdicts are lowercase: `accept`, `reject`, `review`, `pending`.

### What the judge is given

A summary, not the raw records: the part code, the declared product type, whether there was a
category mismatch, the location, the authenticity score and flag, the reference similarity, the
fraud score, the primary fraud category, a list of detected issues, a bulleted summary from each
specialist, and a per-region summary.

**The old documentation said it receives "the complete list of structured evidence cards" along with
the supplier's identity and historical risk rating.** It receives neither. The supplier is not named
in the judge's context, and there is no historical risk information in the model at all.

### The system prompt

The real prompt is short. It instructs the model to return the five fields, to be specific and
factual, to cite the specialist findings that support the verdict, and not to invent measurements.

**The old documentation included a quoted prompt with different fields and a `risk_level` output.**
That quoted prompt was not the prompt in the code.

## 9. Spreading the load between cloud providers

Two cloud providers are used so a problem with one does not stop inspections.

### How the sharing works

**For image analysis**, regions are dealt out alternately between the two providers. Even-numbered
regions go to one, odd-numbered to the other, so roughly half go to each.

There is a second, independent alternating counter inside the shared client, so the choice is a
blend of the region number and a global counter. The old documentation described only the first.

**For the judge**, Groq is always tried first and Gemini second. The old documentation claimed the
opposite in three separate places.

### Timeouts and retries

| Setting | Value |
|---|---|
| Timeout per call | 10.0 seconds |
| Maximum attempts | 3 |
| First wait between attempts | 1.0 second |
| Longest wait between attempts | 8.0 seconds |

**The old documentation said the timeout was 8 seconds in one place and 10 seconds in another.** Both
were in the same file. The 10 second figure is the real timeout. The 8 second figure is the longest
wait between retries, which is a different thing.

**What triggers a switch to the other provider:**

- A server error, including 429 (rate limited) and any 5xx.
- A network failure.
- Taking longer than 10 seconds.

**The old documentation described a "fast-fail" that switches providers in under 180 milliseconds.**
There is no such timed fast path. Failover happens when a call actually fails, not on a timer.

**Two other claims from the old documentation that are not real:**

- That artificial waiting calls were removed to cut latency from 125 seconds. **No such code ever
  existed.** There is no 1.2 second wait anywhere in the project.
- That the client guarantees a specific token count per crop to stay inside a rate limit. There is no
  token counting in the code.

## 10. When things go wrong

**If a specialist fails,** the base class catches it. The result is recorded with `failed` set and
the reason stored. The pipeline continues. The fusion stage counts a failure as a mild anomaly of
0.20, so a broken specialist makes the result slightly suspicious rather than falsely clean.

This is one of the better design decisions in the project and it is tested: there is a test that
makes an agent throw and checks the pipeline survives.

**If a cloud provider is down,** calls fail over to the other. If both are down, the judge falls back
to its rule-based tier. Inspections still complete.

**If the image embeddings cannot be produced,** the local CLIP model is used instead. If the
dimension does not match the index, the code raises a clear error rather than corrupting the index.

**If no API keys are set,** the system still runs. Only the VLM and the judge are affected, and the
judge has its offline tier. Structural, label, and OCR analysis are all local and unaffected. This
means a demo works out of the box.

## 11. What the old documentation got wrong

Collected here so nothing is a surprise.

| Old claim | Reality |
|---|---|
| Levenshtein distance for text comparison | Uses `difflib.SequenceMatcher`, a different algorithm |
| The worked OCR example scores 0.76 and is flagged | It scores about 0.94 and is **not** flagged |
| Normalises O/0 and I/1 confusions | Only collapses whitespace and upper-cases |
| PaddleOCR is the primary reader | Not installed. EasyOCR always runs |
| Multi-scale template matching at 0.90 to 1.10 | One single matching call |
| Label thresholds of 0.88 perfect and 0.70 defect | One threshold: 0.80 |
| OpenCV SSIM as the engine | Uses `scikit-image` first, OpenCV as fallback |
| Four-mode reasoning including position drift | Three statuses. No position comparison |
| "Gemini 3.5 Flash" | `gemini-2.5-flash`. No such 3.5 model |
| Judge returns `root_cause` and `risk_assessment` | Returns `root_cause_reasoning`. No `risk_assessment` |
| Judge has a `risk_level` field | Does not exist |
| A quoted judge system prompt | Not the prompt in the code |
| Judge gets full evidence records and supplier risk | Gets a text summary, with no supplier information |
| Gemini is primary, Groq is backup for the judge | Groq is primary, Gemini is backup |
| An 8-second timeout | 10 seconds. The 8 seconds is the retry backoff cap |
| Fast-fail in under 180 milliseconds | No timed fast path exists |
| A 1.2 second wait was removed | Never existed |
| A 1,000 token per-crop cap | No token counting exists |
| A table of per-specialist latency and memory | Never measured |
| A deterministic conflict-resolution table between specialists | Does not exist. The judge just reads all findings |
| Evidence card fields `agent_id`, `component_class`, `anomaly_score`, `finding_summary` | Real fields are listed in section 3 |
| Intake accepts multi-angle photo arrays | A flat list of strings. No multi-angle handling |
| Four specialists all run at once, once | Two passes. See [PIPELINE.md](PIPELINE.md) |
| The offline judge fallback | Never mentioned. This is the most useful part of the design |

**Not mentioned anywhere in the old documentation, but real and important:**

- The OCR specialist's "not sure, report no defect" behaviour.
- The judge's rule-based offline tier.
- The duplicate image detection in stage 1.
- The screenshot and cloned-block checks in stage 2.
- The hardware category mismatch check in stage 3.
- The batching that stage 4 does before stage 5 runs.

---

*Next: [YOLO_MODEL.md](YOLO_MODEL.md) for the component detection model in detail.*
