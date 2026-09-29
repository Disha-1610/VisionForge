# VisionForge AI — ML Training Documentation

> **Purpose:** Complete ML workflow for the VisionForge component detector, from dataset collection and class mapping to YOLO11n training, evaluation, and annotation cleanup.

---

## 1. ML Pipeline

```text
Public / Custom Datasets
        │
        ▼
Dataset Extraction
        │
        ▼
Class Mapping
        │
        ▼
Annotation Validation / Cleanup
        │
        ▼
Unified 8-Class Dataset
        │
        ▼
YOLO11n Training
        │
        ▼
Best Model (best.pt)
        │
        ▼
Test / Evaluation
        │
        ▼
Component Detection
        │
        ▼
VisionForge Inspection Logic
```

VisionForge uses YOLO11n to detect hardware components. These detections are later used with structural image evidence such as OpenCV/SSIM to identify possible missing, extra, misplaced, or visually different components.

## 2. Original and Final Classes

The original system specification contained 10 classes:

| ID | Original Class | Hardware |
|---:|---|---|
| 0 | capacitor | Motherboard |
| 1 | resistor | Motherboard |
| 2 | ic_chip | Motherboard |
| 3 | connector | Motherboard |
| 4 | screw | Motherboard |
| 5 | terminal | Battery |
| 6 | seal | Battery |
| 7 | battery_cell | Battery |
| 8 | ram_ic_chip | RAM |
| 9 | gold_pin_connector | RAM |

For the working MVP, the model uses 8 classes. `terminal` and `ram_ic_chip` were deferred because suitable datasets with enough confidence and usable annotations were not available.

### Final 8-Class Label Space

```text
0  capacitor
1  resistor
2  ic_chip
3  connector
4  screw
5  seal
6  battery_cell
7  gold_pin_connector
```

## 3. Dataset Sources

| Dataset | Main purpose | Final class(es) |
|---|---|---|
| LibreYOLO PCB | PCB / motherboard components | capacitor, resistor, ic_chip, connector |
| Battery Types | Battery objects | battery_cell |
| Motherboard Screw Localization | Screw detection | screw |
| Container Seal Detection | Seal detection | seal |
| GoldFinger | RAM gold connector | gold_pin_connector |

The source datasets used different class IDs, so their labels were remapped before merging.

## 4. Class Mapping

### PCB

```text
source 4 + 11  → capacitor (0)
source 25      → resistor  (1)
source 15 + 33 → ic_chip   (2)
source 5       → connector (3)
```

### Battery

```text
selected battery object classes → battery_cell (6)
```

### Screw

```text
screw source class → screw (4)
no_screw           → removed
```

### Seal

```text
seal source class → seal (5)
no_seal           → removed
```

### Gold Finger

```text
GoldFinger → gold_pin_connector (7)
```

## 5. Final Dataset Structure

```text
visionforge-dataset/
├── data.yaml
├── train/
│   ├── images/
│   └── labels/
├── valid/
│   ├── images/
│   └── labels/
└── test/
    ├── images/
    └── labels/
```

| Split | Images | Labels |
|---|---:|---:|
| Train | 3,393 | 3,393 |
| Validation | 715 | 715 |
| Test | 340 | 340 |
| **Total** | **4,448** | **4,448** |

## 6. YOLO Detection Label Format

Every detection row follows:

```text
class_id x_center y_center width height
```

Coordinates are normalized to `0–1`.

Example:

```text
2 0.521000 0.433000 0.120000 0.180000
```

This means class `2` (`ic_chip`) with a normalized bounding box.

## 7. Annotation Problem Found After the First Run

During post-training evaluation, some labels were discovered to be segmentation polygons instead of normal detection boxes.

A detection row has 5 values:

```text
class x_center y_center width height
```

A polygon row contains a class followed by multiple `x,y` points:

```text
class x1 y1 x2 y2 x3 y3 ...
```

The first training run therefore contained a mixture of detection and segmentation-style annotations. Ultralytics warned about mixed segments and boxes during validation, so the first metrics should be treated as baseline results rather than the final clean-dataset benchmark.

## 8. Polygon-to-Bounding-Box Cleanup

For a polygon, the cleanup process used the minimum and maximum coordinates:

```text
xmin = min(x values)
xmax = max(x values)
ymin = min(y values)
ymax = max(y values)

x_center = (xmin + xmax) / 2
y_center = (ymin + ymax) / 2
width     = xmax - xmin
height    = ymax - ymin
```

The polygon was then rewritten as a normal YOLO detection box.

### Cleanup Result

| Split | Non-detection rows before cleanup | After cleanup |
|---|---:|---:|
| Train | 1,966 | 0 |
| Validation | 754 | 0 |
| Test | 63 | 0 |

Image/label counts stayed unchanged.

> **Important:** The cleanup was completed after the first training run. A second training run was **not completed**. Therefore, all reported model metrics in this document are from the original run.

## 9. Final `data.yaml`

```yaml
path: /content/visionforge-dataset

train: train/images
val: valid/images
test: test/images

nc: 8

names:
  - capacitor
  - resistor
  - ic_chip
  - connector
  - screw
  - seal
  - battery_cell
  - gold_pin_connector
```

## 10. Dataset Distribution

Approximate training-instance counts:

| Class | Instances |
|---|---:|
| capacitor | 14,155 |
| resistor | 3,591 |
| ic_chip | 5,998 |
| connector | 27,014 |
| screw | 2,932 |
| seal | 480 |
| battery_cell | 4,065 |
| gold_pin_connector | 1,528 |

The dataset is not perfectly balanced. `connector` and `capacitor` have many more instances than smaller classes such as `seal` and `gold_pin_connector`. This matters when interpreting per-class metrics.

## 11. Why YOLO11n?

YOLO11n was selected because VisionForge needs a lightweight object detector that is practical for an inspection pipeline. The `n` model is the small YOLO11 variant, making it suitable for an MVP and easier to deploy than heavier detector variants.

## 12. Transfer Learning

The model started from pretrained YOLO11n weights:

```text
yolo11n.pt
```

Instead of learning all visual features from random initialization, the pretrained model was adapted to the VisionForge hardware-component task.

```text
Pretrained YOLO11n
        ↓
General visual features
        ↓
VisionForge custom dataset
        ↓
Fine-tuning
        ↓
Hardware component detector
```

## 13. Training Environment

Training was performed in Google Colab on a Tesla T4 GPU.

```text
GPU        → Tesla T4 (~16 GB VRAM)
Python     → 3.13.x
PyTorch    → 2.11.0+cu128
Ultralytics → 8.4.147
```

The dataset was stored in Google Drive and copied into the Colab runtime before training.

## 14. Training Configuration

| Parameter | Value |
|---|---|
| Model | YOLO11n |
| Initial weights | `yolo11n.pt` |
| Epochs | 100 |
| Image size | 640 × 640 |
| Batch size | 16 |
| Device | Tesla T4 |

### Training Code

```python
from ultralytics import YOLO

model = YOLO("yolo11n.pt")

results = model.train(
    data="/content/visionforge-dataset/data.yaml",
    epochs=100,
    imgsz=640,
    batch=16,
    device=0,
    project="/content/visionforge-runs",
    name="component_detector",
    exist_ok=True
)
```

## 15. Why 100 Epochs?

100 epochs was used as an initial training budget, not as a magic optimal value.

One epoch means that the training process has gone through the training dataset once. The model therefore had up to 100 passes through the training data.

A final epoch count should be decided by observing validation behavior:

```text
Validation improves → continue
Validation converges → stopping may be reasonable
Training improves but validation gets worse → possible overfitting
```

## 16. Training Time and Model Files

The completed training run took approximately **2.4 hours** on the Tesla T4.

Ultralytics generated:

```text
best.pt
last.pt
```

The best checkpoint was saved to Google Drive as:

```text
visionforge-component-detector-best.pt
```

## 17. Test Prediction

All 340 test images were passed through the trained model.

```python
model.predict(
    source="/content/visionforge-dataset/test/images",
    conf=0.25,
    save=True,
    project="/content/visionforge-predictions",
    name="test",
    exist_ok=True
)
```

This produced saved prediction images for the test split.

## 18. Evaluation

Evaluation was performed with:

```python
test_results = model.val(
    data="/content/visionforge-dataset/data.yaml",
    split="test",
    imgsz=640,
    batch=16,
    device=0,
    plots=True
)
```

### First and Only Completed Training Run

```text
mAP50     ≈ 0.502
mAP50-95  ≈ 0.331
```

These are **baseline results from the original run**. They are not results from the cleaned-and-retrained dataset because that retraining was not completed.

## 19. Per-Class Observation from the First Evaluation

The first evaluation showed stronger results for classes such as:

```text
battery_cell
screw
seal
```

and much weaker results for:

```text
capacitor
resistor
connector
```

Possible contributing factors include class imbalance, differences between source datasets, small/dense PCB objects, domain differences, and the annotation issue discovered during evaluation.

## 20. Important Metrics

### Precision

```text
Precision = TP / (TP + FP)
```

It answers:

> When the model predicts an object, how often is that prediction correct?

### Recall

```text
Recall = TP / (TP + FN)
```

It answers:

> Of all real objects, how many did the model find?

### IoU

Intersection over Union measures overlap between a predicted bounding box and the ground-truth box.

### mAP50

Average precision across classes at an IoU threshold of `0.50`.

### mAP50-95

Average precision across IoU thresholds from `0.50` to `0.95` in steps of `0.05`, making it a stricter localization metric.

## 21. YOLO Inside the VisionForge System

```text
                 Inspection Image
                        │
                        ▼
                Image Preprocessing
                        │
                        ▼
                     YOLO11n
                        │
                        ▼
              Component Detections
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
         Classes     Positions     Counts
            │           │           │
            └───────────┼───────────┘
                        ▼
             Compare with Golden ROI
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
         Missing       Extra      Misplaced
                        │
                        ▼
                 OpenCV / SSIM
                        │
                        ▼
                  Fusion / Judge
                        │
                        ▼
                 Final Inspection
```

## 22. Why YOLO + SSIM?

YOLO gives component-level evidence:

```text
What is present?
Where is it?
How many are present?
```

SSIM gives structural image evidence:

```text
How similar is the inspection region
compared with the golden reference?
```

The two signals therefore answer different questions and can be combined in the inspection pipeline.

## 23. Example

Suppose the golden board contains:

```text
8 connectors
```

but the inspection image produces:

```text
7 connectors
```

The detector can provide evidence for:

```text
Expected = 8
Detected = 7
Possible missing connector
```

Structural similarity can then provide additional evidence for the same region before the final inspection decision.

## 24. Dataset Quality Checklist

Before a future training run, verify:

```text
✓ Image and label filenames match
✓ Every label uses exactly 5 detection values
✓ Class IDs are within 0–7
✓ Coordinates are valid and normalized
✓ No unexpected segmentation labels remain
✓ No corrupt images
✓ No accidental duplicates
✓ Train/validation/test separation is correct
✓ Class distribution is understood
✓ Bounding boxes visually match objects
```

## 25. Current Project Status

### Completed

```text
✅ Dataset collection
✅ Source class mapping
✅ 8-class master dataset
✅ Train/validation/test splits
✅ Annotation cleanup
✅ One YOLO11n training run
✅ best.pt generation
✅ Test prediction on 340 images
✅ First evaluation
```

### Not Completed

```text
❌ Retraining after annotation cleanup
❌ Final benchmark on the cleaned dataset
```

## 26. Future ML Improvements

### Clean-dataset retraining

Run a fresh YOLO11n training job using the fully detection-only dataset and compare its metrics with the original baseline.

### Target weak classes

Collect more diverse examples for classes with weaker performance, especially:

```text
capacitor
resistor
connector
seal
gold_pin_connector
```

### Reduce domain gap

Public datasets may differ in:

```text
lighting
camera angle
background
object scale
image quality
```

Real images from the intended inspection environment can help reduce this gap.

### Real-world validation

A future benchmark should include images captured under the actual VisionForge inspection setup, not only public datasets.

## 27. Interview-Ready Explanation

> "For VisionForge, I created a unified object-detection dataset by combining PCB, battery, screw, seal, and gold-finger datasets. Because each source dataset used different class IDs, I remapped them into a common 8-class label space. The final dataset contained 3,393 training images, 715 validation images, and 340 test images. I fine-tuned pretrained YOLO11n for 100 epochs at 640×640 with batch size 16 on a Tesla T4. The run took about 2.4 hours and produced a best checkpoint. During post-training evaluation, I found that some source labels were segmentation polygons instead of detection boxes, so I converted those annotations into standard YOLO detection format and verified the cleaned dataset. I did not complete a second training run, so the reported metrics are baseline results from the original run."

## 28. Key Engineering Lesson

```text
Good Model
   +
Good Training
   +
Good Evaluation
   +
Clean Annotations
   =
Useful Computer Vision System
```

The main lesson from VisionForge is simple:

> **The reliability of an object detector depends heavily on the quality and consistency of the data used to train and evaluate it.**

YOLO11n provides the component-detection layer. VisionForge then combines those detections with structural image evidence to support hardware inspection.
