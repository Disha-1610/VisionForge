# The training dataset

> This describes the 4,448 images used to train the component detector, and what the data can and
> cannot tell you.
> All counts below were measured from the files themselves.

---

## Read this first

**The numbers that are easy to get wrong:**

- **The total is 76,672 boxes, not 59,773.** The 59,763 figure is the training split alone. The
  whole dataset has **76,672 boxes**.
- **Images do not range from 640x640 to 3840x2160.** They range from 153 pixels
  wide to 4,624, and 129 pixels tall to 5,632. Some of them are very small.

**No model accuracy can be quoted for this data either.** There is no training record anywhere in
this repository. No `results.csv`, no `best.pt`, no evaluation script, no training script at all.
The only file in the model folder is the weight file itself. Any mAP figure would be
unsupported, so this document does not repeat one. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

---

## Table of contents

1. [What is in the folder](#1-what-is-in-the-folder)
2. [The split](#2-the-split)
3. [The eight classes](#3-the-eight-classes)
4. [How many of each](#4-how-many-of-each)
5. [The images themselves](#5-the-images-themselves)
6. [How the labels are written](#6-how-the-labels-are-written)
7. [The images with no labels](#7-the-images-with-no-labels)
8. [Where the data came from](#8-where-the-data-came-from)
9. [What cannot be checked](#9-what-cannot-be-checked)
10. [How the dataset is used](#10-how-the-dataset-is-used)

---

## 1. What is in the folder

```
visionforge-dataset/
├── data.yaml                  # the class list and the folder layout
├── train/
│   ├── images/   3,393 files
│   └── labels/   3,393 files
├── valid/
│   ├── images/     715 files
│   └── labels/     715 files
└── test/
    ├── images/     340 files
    └── labels/     340 files
```

**Every image has a label file with the same name.** All 4,448 images are JPEG files, all 4,448
labels are text files. There are no stray files, no missing pairs, and no duplicates by name.

**Total size: 573 MB.**

**There is no other content.** No training script, no notes, no augmentation config, no licence
file, no dataset card, and no record of how the labels were checked.

## 2. The split

| Split | Images | Boxes | Share of images |
|---|---|---|---|
| Training | 3,393 | 59,763 | 76.3% |
| Validation | 715 | 11,236 | 16.1% |
| Test | 340 | 5,673 | 7.6% |
| **Total** | **4,448** | **76,672** | 100% |

**On the split names.** The folder is called `valid`, not `val`. `data.yaml` points at
`valid/images`, so it works, but it is worth knowing if you are following an example that assumes
`val`.

## 3. The eight classes

The classes are numbered, and the numbering matters because the labels are numbers.

| ID | Class name | What it is on a board |
|---|---|---|
| 0 | `capacitor` | The small blocks on a power rail |
| 1 | `resistor` | The other small blocks. Very similar to a capacitor |
| 2 | `ic_chip` | The black squares with pins |
| 3 | `connector` | Headers and sockets. By far the most common |
| 4 | `screw` | Board screws |
| 5 | `seal` | Tamper and warranty seals |
| 6 | `battery_cell` | Battery cells, of several shapes |
| 7 | `gold_pin_connector` | The gold contacts along the edge of a RAM module |

**The order is confirmed by three independent places:** `data.yaml`, the one test that loads the real
model file and checks its class count, and the constants in the structural agent's code. They all
agree.

**Note the class names are a bit misleading.** `gold_pin_connector` and `connector` are different
classes in the data, but they are related parts. `ic_chip` is one class covering several different
kinds of chip. A classifier trained on this will learn these 8 groups, not 8 tidy component types.

## 4. How many of each

**Measured by reading all 4,448 label files.**

| ID | Class | Train | Valid | Test | **Total** | Share |
|---|---|---|---|---|---|---|
| 0 | `capacitor` | 14,155 | 3,797 | 1,938 | **19,890** | 25.9% |
| 3 | `connector` | 27,014 | 3,630 | 1,920 | **32,564** | 42.5% |
| 2 | `ic_chip` | 5,998 | 1,032 | 574 | **7,604** | 9.9% |
| 6 | `battery_cell` | 4,065 | 1,158 | 631 | **5,854** | 7.6% |
| 1 | `resistor` | 3,591 | 597 | 439 | **4,627** | 6.0% |
| 4 | `screw` | 2,932 | 357 | 167 | **3,456** | 4.5% |
| 7 | `gold_pin_connector` | 1,528 | 659 | 0 | **2,187** | 2.9% |
| 5 | `seal` | 480 | 6 | 4 | **490** | 0.6% |
| | **Total** | **59,763** | **11,236** | **5,673** | **76,672** | |

Sorted from most common to least, which is more useful for reading the table.

**On average there are 17.2 boxes per image.** Divide by the whole dataset, not just the training
split, or the average comes out about 25% too high.

**Three things in this table are worth stopping on:**

1. **`connector` is 42.5% of everything.** More than the next three classes combined. **No loss
   weighting is configured anywhere.** There is no training code in the repository to configure it
   in, and no record that any balancing was applied.
2. **`seal` has 490 boxes in the entire dataset.** 480 of them are in the training split, 6 in
   validation, 4 in test. You cannot measure a model on 4 examples. **Any claim about seal
   detection accuracy is unsupported.**
3. **`gold_pin_connector` has no test examples at all.** Zero. So the test split cannot say anything
   about that class either.

## 5. The images themselves

**All 4,448 image dimensions were measured.**

| | |
|---|---|
| Width range | 153 to 4,624 pixels |
| Height range | 129 to 5,632 pixels |
| Distinct sizes in a 250-image sample | 25 |
| Every file is | `.jpg` |

**There is no consistent resolution.** Some images are 4,624x3,472, some are 640x640, some are
153 pixels wide. A sample of 250 images found 25 different sizes. The most common single size in
that sample was 640x640, which appeared 126 times out of 250, so the bulk are small, but there is a
long tail of large ones.

**This matters more than it looks.** The pipeline's stage 1 rejects any photo narrower than 640
pixels or shorter than 480. **724 of the 4,448 training images, or 16.3%, are smaller than that and
would be rejected by the project's own quality gate.** Roughly one image in six. More than a tenth
are so small that they could not pass.

**What this means:** the detector was trained on images a meaningful fraction of which the
application itself considers unusable. It is not a contradiction, since the detector is handed
crops rather than whole photos in the real pipeline, but it does mean the dataset is not a
representation of what the application receives.

**The subject matter is three kinds of hardware,** based on the folder names and the classes present:
motherboards, battery packs, and RAM modules.

## 6. How the labels are written

**Every label line has five numbers:**

```
<class_id> <x_center> <y_center> <width> <height>
```

A real line from the dataset:

```
6 0.41492708333333334 0.47916406250000004 0.42013541666666665 0.3072890625
```

That reads as: a battery cell, centred 41.5% across and 47.9% down the image, taking up 42.0% of
the width and 30.7% of the height.

**The first number is the class from the table in section 3. The other four are fractions of the
image size, not pixels.** This is the standard YOLO format, and it is why one label file works at any
image resolution.

**All 4,448 label files follow this format.** No file uses the polygon format, and none uses pixel
coordinates.

## 7. The images with no labels

**62 label files are completely empty:**

| Split | Empty label files |
|---|---|
| Training | 51 |
| Validation | 9 |
| Test | 2 |

**An empty label file means the image contains none of the 8 classes.** For a detector this is
valuable. It teaches the model that a picture of a blank board should produce no detections, rather
than hallucinating a capacitor somewhere.

**These empty files are not the result of a recorded experiment.** They are almost certainly just
images that had no annotations after cleaning, kept because the export included them. That is a
reasonable outcome. Nothing in the repository claims a measured effect on false positives.

**The empty files are only in the first line sense** — they are 0 bytes, so the parser reads no
boxes and the image is treated as a negative. Nothing in the project reads this dataset, so there is
no code to go wrong.

## 8. Where the data came from

**The filenames carry the fingerprint of Roboflow.** Every image is named something like:

```
-6001418491044938301_121_jpg.rf.793358d72f22822839878cff72890d02.jpg
```

The `.rf.` and the long hash are added by Roboflow when it exports a dataset. **So the data was
assembled in Roboflow, exported, and committed to this repository.**

**The project's own notes name five public sources:**

1. A printed circuit board dataset, with 34 original classes, filtered down to 4 of them
2. A battery types dataset
3. A motherboard screw dataset
4. A container seal dataset
5. A gold finger dataset

**The class-by-class training counts in the project notes match the real data exactly** for all 8
classes. That is a good sign. It means the notes describe the data that is actually here, not a
different version of it.

**Two specific cleaning steps in the notes are worth mentioning,** because they explain what is
missing rather than what is present:

- The screw dataset had both `screw_roi` and `no_screw` annotations. The negative ones were removed,
  so the model is not taught to detect empty screw holes as screws.
- The seal dataset had corrupt annotations that were dropped.

## 9. What cannot be checked

**Being clear about the limits of this dataset.**

| Question | Can it be answered? |
|---|---|
| How accurate is the model on this data? | **No.** No evaluation was run, and no result is stored |
| How accurate is the model on data it has not seen? | **No.** The test split exists but nothing has run against it |
| Which class does the model get wrong most? | **No.** There is no per-class result |
| Was the data cleaned by hand? | **No record.** The notes describe it, nothing is stored |
| Is the test split free of duplicate images from the training split? | **Not checked.** The notes mention deduplication was used, but no result is stored |
| Are the labels correct? | **Not verified.** There is no second annotator and no review record |
| What licence is this data under? | **Not recorded anywhere in the repository** |
| Can the model be retrained? | **No.** There is no training script |
| Is the split stratified? | **Not checked.** The `seal` and `gold_pin_connector` counts suggest it is not evenly stratified |

**The two empty-classes problem is the most important of these.** `seal` has 4 test boxes and
`gold_pin_connector` has 0. **Any overall accuracy figure is dominated by `connector` and
`capacitor`**, which are 68% of the data between them. A model that never detected a single seal
would still score well on a corpus-wide average.

**On licence:** the project notes name two of the sources as CC BY 4.0. **No licence text is in the
repository.** If this dataset is ever used for anything beyond a demo, the licence question needs
answering first.

**On retraining:** there is no script. To retrain, you would write one. The dataset and the weight
file are here; the process that produced the weight file is not.

## 10. How the dataset is used

**Short answer: it is not used at runtime at all.**

**The application never reads `visionforge-dataset/`.** Grep the backend for it and you get nothing.
The dataset was a training input, and the model file it produced is all the application uses.

**What the application actually loads at runtime:**

| What | Where |
|---|---|
| The trained detector | `backend/data/yolo_weights/component_detector.pt` |
| 3 reference photos | `backend/data/golden_images/` |
| 3 region files | `backend/data/roi_templates/` |
| The vector index | `backend/data/faiss_index/` |

**The 3 reference photos** are a battery, a motherboard, and a RAM module:

```
bat_std_v1_efdd0ef3.png
pcb_mcu_v2_a2ebf50f.png
ram_ddr4_v1_de3719e1.png
```

**The 3 region files** match them one to one, and each one lists the areas of that reference the
specialist agents should look at. See [PIPELINE.md](PIPELINE.md).

**The vector index** is 37 KB, holding one vector per reference image plus an ID list. It is not
built from the training dataset. It is built from the 3 reference photos, using Google's embedding
model. See [DATABASE.md](DATABASE.md).

**So the relationship is:**

```
visionforge-dataset/     4,448 images ──trained──▶ component_detector.pt ──used by──▶ stage 5
                                                                                    on crops
golden_images/           3 photos ──embedded──▶ faiss_index ──used by──▶ stage 3
roi_templates/           3 files ──────────────────────────────used by──▶ stage 4
```

**Two paths in the config file worth knowing about.** `data.yaml` sets `path: .`, which means it
only works when the training command is run from inside the dataset folder. And it points at
`valid/images` rather than `val/images`, which is correct for this layout.

---

*Next: [YOLO_MODEL.md](YOLO_MODEL.md) for the model trained on this data, or
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the problems.*
