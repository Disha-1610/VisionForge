# The Component Detection Model

> This describes the YOLO model that finds components on a board.
> Checked against the model file, the code, and the dataset in September 2026.

---

## Read this first

**This project has never measured how accurate this model is.**

There is no evaluation file, no results spreadsheet, no confusion matrix, no training log, and no
training script in this repository. **No accuracy figure can be supported.** There is nothing in the
repository that would let anyone reproduce or check one.

**Do not quote an accuracy figure for this model.** If you need one, run an evaluation and record
it. The command is in [How to evaluate it](#6-how-to-evaluate-it).

What this document does give you is everything that *is* verifiable: the model file, its size, its
classes, how it is called, and the dataset it came from.

---

## Table of contents

1. [What the model does](#1-what-the-model-does)
2. [The model file](#2-the-model-file)
3. [The 8 classes](#3-the-8-classes)
4. [How the model is called](#4-how-the-model-is-called)
5. [How the counts are compared](#5-how-the-counts-are-compared)
6. [How to evaluate it](#6-how-to-evaluate-it)
7. [Unsupported performance claims](#7-unsupported-performance-claims)
8. [What is not known about this model](#8-what-is-not-known-about-this-model)

---

## 1. What the model does

The model looks at one cropped region of a board and lists every electronic component it can see.

This is what makes the whole counting check possible. Without it, there is no reliable way to answer
"is one capacitor missing from this row of ten?" — the parts are tiny and identical.

**It only runs when the image comparison says the region is different from the reference.** There is
a cheaper check first: if the region matches the reference closely, there is nothing to count. The
model is only asked when the region already looks wrong. That saves a lot of work.

## 2. The model file

| | |
|---|---|
| **File** | `component_detector.pt` |
| **Location** | `backend/data/yolo_weights/` |
| **Size** | 5,468,826 bytes, which is about 5.2 MB |
| **Type** | Ultralytics YOLO detection model |
| **Architecture** | YOLO11n, the smallest of the YOLO11 family |
| **Class count** | 8 |
| **Size in pixels** | Not set in the code, so the library default is used |

**The model is real and genuinely runs.** The code loads it with the real Ultralytics library and
runs real inference on it. It is not a mock, a stub, or a placeholder.

**The only test that touches it** loads the file, reads the class names out of it, and checks there
are 8 of them. **No test runs actual inference on a real image.** Every other detection test in the
project substitutes a fake model that returns hard-coded results.

**The library requirement** is Ultralytics 8.3 or later, declared in `backend/requirements.txt`.

## 3. The 8 classes

| # | Class name | What it is |
|---|---|---|
| 0 | `capacitor` | Small ceramic or electrolytic capacitors |
| 1 | `resistor` | Resistors and other small surface-mount parts |
| 2 | `ic_chip` | Integrated circuits, the black chips with pins |
| 3 | `connector` | Connectors, sockets, headers |
| 4 | `screw` | Mounting screws |
| 5 | `seal` | Tamper seals, warranty seals |
| 6 | `battery_cell` | Individual cells inside a battery pack |
| 7 | `gold_pin_connector` | The gold contact edge on a RAM module |

These 8 names match the dataset configuration file exactly. There is no mismatch between the model
and the data it came from. Names like "solder joints", "barcodes", or "missing-component slots" are
not classes in this model.

**Two notes on the class list:**

**Screws and seals are in there on purpose.** They are small and easy to remove, and a missing
mounting screw or a broken warranty seal is a real tampering signal. The dataset has relatively few
of each compared to the other classes.

**Gold pin connectors have no test examples.** Looking at the test split, there are 117 images
containing gold pin connectors in total, and **all of them are in the training and validation splits.
The test split contains zero.** So the model has never been checked on a held-out example of that
class. Any claim about how well it detects gold pin connectors is unsupported.

## 4. How the model is called

### The settings

| Setting | Value | What it does |
|---|---|---|
| Detection confidence | **0.20** | The minimum score for a detection to be counted |
| Count tolerance | **25** | How much two counts may differ before it is called a mismatch |
| Image similarity threshold | **0.80** | Below this, the model is not even run |

### The confidence threshold of 0.20 is deliberate and worth understanding

A general object detector is usually run at 0.25 or 0.5, throwing away anything less certain. **This
one runs at 0.20, which is low.**

The reasoning: in safety inspection, missing something is much worse than looking at something that
is not there. A false alarm costs an operator thirty seconds. A missed missing capacitor costs a
recalled batch.

So the model is deliberately over-eager. It finds more candidates than a normal detector would. The
count comparison, not the detection, is what decides whether a region is a problem.

**0.20 is a chosen value, not a calibrated one.** There is no record of any calibration
process behind it. It is a value in the code with a comment. That is a reasonable choice, but
calling it calibrated would imply a process that has not happened.

### The image size is not set

The code does not pass a size argument, so the library uses its own default. 640x640 with letterbox
resizing may match that library default, but this project does not specify it, and it has not been
verified here.

## 5. How the counts are compared

### The three outcomes

| Status | What it means |
|---|---|
| `missing` | Fewer components found than the reference has |
| `extra` | More components found than the reference has |
| `match` | The two counts are within the tolerance of 25 |

**The tolerance of 25 is a pixel-area threshold, not a count.** It is compared against the total
detected area, so a region with more parts has more room before a difference counts.

### The two halves of the check, in order

1. **Image similarity first.** Compare the region against the reference. If the similarity is at or
   above 0.80, stop — the region matches and there is nothing to count.
2. **Count only if different.** If the similarity dropped below 0.80, run the model and compare
   counts.

**This ordering matters: the real logic is a cheap check gating an expensive one.** There is no
"four-mode reasoning" engine, and no position-comparison mode.

### The AI double-check

After the specialists run, a second pass sends every region the structural specialist handled to the
VLM specialist. So the AI looks at the same regions with a different tool and can disagree. This
second pass is easy to overlook when reading the stage as a single parallel split.

## 6. How to evaluate it

If you need a real accuracy number, this is how to get one. Note that this has not been run, which is
why no number appears in this document.

The dataset is configured in `visionforge-dataset/data.yaml`, with the training, validation, and test
splits laid out as directories. Ultralytics can evaluate directly from that:

```bash
# from the repository root, with the backend environment active
yolo val model=backend/data/yolo_weights/component_detector.pt \
       data=visionforge-dataset/data.yaml \
       split=test \
       imgsz=640
```

**What to record if you run this.** The mean average precision at 50% overlap, the mean average
precision at 50 to 95% overlap, the precision, the recall, and the per-class results. Write them
down with the date and the command, so the next person can reproduce them.

**Two things to be careful about when you do:**

- **The test split is small.** 340 images. A result from 340 images has real uncertainty in it.
  Report the interval, not just the number.
- **Gold pin connectors have no test examples.** The per-class average will silently skip that class.
  Say so, rather than letting it look like the model handles all 8.

## 7. Unsupported performance claims

If you are asked about this model's accuracy, these are the figures that sometimes get quoted, and
what the repository actually supports:

| Claimed figure or claim | What the repository supports |
|---|---|
| Accuracy improved from 74.2% to 88.4% | No metrics file exists to support either number |
| Accuracy of 98.4% | Also unsupported, and contradicts the 88.4% quoted elsewhere |
| Precision dropped to 64% during consolidation | Unsupported |
| Class oscillation fell from 18.4% to 1.2% | Unsupported |
| False positives fell from 14.8 to 1.6 per 100 boards | Unsupported |
| Box loss fell from 1.84 to 0.62 | No loss curves exist |
| Class loss fell from 2.14 to 0.28 | No loss curves exist |
| DFL loss fell to 0.84 | No loss curves exist |
| A per-class test accuracy table | No evaluation script, no confusion matrix, no per-class results file |
| Training used 100 epochs, batch 32, AdamW, specific learning rates | No training script and no training log in the repository |
| The dataset went from 10 classes to 8 | The data file only ever declared 8. No 10-class version exists |
| A pre-merge model of 5.9 MB | No such file exists |
| Benchmarks on an RTX 4060, Jetson Orin, i7, and Raspberry Pi 5 | No benchmark script, and TensorRT, OpenVINO, and ONNX Runtime are not even in the requirements file |
| Benchmarks were based on 500 inference runs | No such run was recorded |
| Features expand 8x to 12x under magnification | The region files have no magnification or scale settings at all |

**On the 74.2% to 88.4% figure specifically:** even taken at face value, going from 0.742 to 0.884 is
a 19.1% relative increase, not a 14.2% one. Claims of that kind mix up percentage points with
percent.

**Two things about this model that are checkable and true:**

- The model file is about 5.2 MB.
- The detection confidence really is 0.20.

## 8. What is not known about this model

Being clear about the gaps, because they matter if you are asked about this model:

**Never measured.** No accuracy, no precision, no recall, no speed. Nothing.

**Never retrained in this repository.** There is no training script. The model file is committed as
a finished artefact, with no record of how it was produced.

**Dataset provenance is undocumented.** The data file does not say where the images came from, and
there are no licence files, download scripts, or source records in the repository. No cleaning or
merging process is recorded. For a project that would
ever be used commercially, the licence position on the training images needs to be established.

**Some training images are of poor quality.** The dataset contains images as small as 153x287 pixels.
The product rejects anything under 640x480 at stage 1. So the model is partly trained on images the
system itself would reject. The distribution of image sizes in the dataset is 140 different
resolutions, from 153x287 up to 4624x3472.

**No per-class balance.** One class has 32,564 labelled instances and another has 490. A model
trained on that will be much better at the common classes. The dataset details are in
[DATASET.md](DATASET.md).

**No augmentation record.** No training configuration exists, so the augmentation settings used are
unknown. Any specific augmentation values, or any claimed reduction in false alarms, cannot be
checked against the repository.

**Gold pin connectors are untested.** No held-out examples exist.

---

*Next: [DATASET.md](DATASET.md) for the training data in detail, or
[AI_AGENTS.md](AI_AGENTS.md) for how this model fits into the wider inspection.*
