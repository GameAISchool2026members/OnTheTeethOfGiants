# On The Teeth Of Giants

A Unity game you play **with your tongue**. A CPU-only Python sidecar watches you through your webcam, figures out which way your tongue is pointing (up / down / left / right / out / no tongue), and streams that to Unity in real time. No GPU required.

Built at **[8th International Summer School for Artificial Intelligence and Games | Leiden, The Netherlands, June 2026](https://school.gameaibook.org/)**.


---

## How it works

The project is split into two processes that talk over local sockets:

```
┌─────────────────────────┐         UDP :5005  (dx, dy, conf)        ┌──────────────────┐
│   Python sidecar        │  ───────────────────────────────────►    │   Unity game     │
│   (owns the webcam)     │                                          │   (listens only) │
│                         │         TCP :5006  (JPEG video)          │                  │
│   MediaPipe + tracker   │  ───────────────────────────────────►    │                  │
└─────────────────────────┘                                          └──────────────────┘
```

- **The Python sidecar owns the camera.** Unity never opens the webcam itself; it only listens. This keeps the game decoupled from the vision stack and avoids camera-contention.
- **Tongue direction** is sent as a tiny UDP datagram every frame: `dx,dy,conf` (comma-separated floats).
- **The webcam video** is streamed separately over TCP as length-prefixed JPEG frames, so Unity can show the player's face in-game.

In every case, **MediaPipe Face Landmarker** (Tasks API, VIDEO mode) locates the mouth first. It provides the geometry — the inner-lip opening, the lip flesh to ignore, and a small downward extension of the search region — that both trackers below build on. Whatever the tracker, the output is the same: the tongue's centroid relative to the mouth centre, as a normalized `(dx, dy)` offset that classifies into **up / down / left / right**, or **closed** when no tongue is out.

---

## Two swappable tongue trackers

Detection is pluggable. There are two interchangeable backends that produce **identical output**, so the rest of the pipeline (the sidecar, the UDP/TCP streams, Unity) doesn't care which one is running.

### 1. Colour blob — `tongue_colour.py` (default)

The simple, fast, dependency-lightest option. Inside the mouth search region, the tongue is isolated purely by **redness** — a fixed threshold on the `a*` channel of LAB colour space. The largest red blob above a minimum area becomes the tongue.

- **Pros:** fast, CPU-only, plug&play.
- **Cons:** sensitive to lighting and skin/lip colour; the threshold (`a_thresh`) sometimes needs hand-tuning.

### 2. DINO feature extractor — `tongue_dino.py`

Instead of thresholding colour, this scores each image patch by how much it *looks like tongue* in **DINOv2** feature space — a self-supervised vision backbone used here as a frozen feature extractor (no training, no dataset).

It works by **few-shot enrollment**. You stick your tongue out once and press a key; MediaPipe geometry supplies the weak labels for free:

- patches whose centre falls inside the inner-lip opening → **tongue** examples
- patches on the lips / surrounding skin → **background** examples

Their averaged, L2-normalised DINOv2 features become two **prototypes**. At runtime each patch is scored by `cos(patch, tongue) − cos(patch, background)`; patches above a margin (and inside the mouth region) form the tongue mask, and its centroid gives the same `(dx, dy)` as the colour tracker.

- **Pros:** far more robust to lighting and colour than a fixed redness threshold; learns *your* tongue; enrollment is repeatable (capture from several angles/lighting to strengthen it) and prototypes persist to disk (`tongue_proto.npz`), auto-loading next run.
- **Cons:** needs `torch` / `torchvision`; the first run downloads DINOv2 weights (internet once) and is slow to start; steady-state speed depends on the patch `grid` and your CPU.

### Why they're interchangeable

Both classes expose the exact same interface, and both return `(dx, dy, conf, mask)` from `measure()`:

```python
measure(frame, lms)  -> (dx, dy, conf, mask) | None
recenter(frame, lms) -> (ox, oy)
```

The DINO tracker just adds a few extra methods — `enroll()`, `save()`, `load()` — for the one-time tongue capture and prototype persistence.

Because the contract is identical, swapping is a **one-line import change**:

```python
# colour blob (default)
from tongue_colour import TongueTracker

# OR the DINO feature extractor — drop-in replacement
from tongue_dino import TongueDinoTracker as TongueTracker
```

When using DINO, there are keybinds to `tracker.enroll(...)` (tongue out) instead of the colour tracker's recenter/calibrate, and `tracker.save(...)` / `tracker.load(...)` to reuse prototypes across runs.

---

## Repository layout

| Path | What's inside |
| --- | --- |
| `On The Teeth Of Giants/` | The Unity project (game logic, scenes, scripts) |
| `Assets/` | Game assets — art, shaders, etc. |
| `sidecar/` | The Python tongue-tracking sidecar (both trackers live here) |

Inside `sidecar/`:

| File | Role |
| --- | --- |
| `tongue_colour.py` | Colour-blob tracker (default) + shared geometry/landmark constants |
| `tongue_dino.py` | DINOv2 feature-extractor tracker (swappable alternative) |
| `tongue_sidecar.py` | The Unity sidecar — owns the camera, streams direction (UDP) + video (TCP) |
| `tongue_identify.py` | Standalone webcam tester for the colour tracker |
| `tongue_identify_dino.py` | Standalone webcam tester for the DINO tracker (with enroll/save keys) |
| `video_server.py` | TCP JPEG video server consumed by Unity |
| `tongue_kalman.py`, `head_segment.py` | Supporting / experimental modules |

**Languages:** ShaderLab, C#, and HLSL (Unity side) · Python (sidecar) · Wolfram Language (prototyping / math).

---

## Getting started

### 1. Run the sidecar first

The sidecar needs Python 3.12+ and a webcam.

```bash
cd sidecar

# colour tracker only:
pip install mediapipe opencv-python numpy

# add these if you want the DINO tracker:
pip install torch torchvision

# download the MediaPipe face landmark model
curl -L -o face_landmarker.task \
  https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task

python tongue_sidecar.py
```

You should see a preview window open with your webcam feed. Stick your tongue out and you'll see it highlighted, along with the detected direction. The sidecar streams to `127.0.0.1` on ports **5005** (direction) and **5006** (video).

**Controls in the preview window:**
- `c` — recenter / calibrate to your current tongue position
- `Esc` — quit

### 2. Then press Play in Unity

Open the `On The Teeth Of Giants/` project in Unity and hit Play. It connects to the sidecar automatically and reconnects if the sidecar restarts.

> Start the sidecar **before** entering Play mode — it's the server for the video stream; Unity is the client.

---

## Standalone tongue testers (no Unity)

To see the detection on its own:

```bash
# colour blob
python tongue_identify.py     # c = recenter, Esc = quit

# DINO feature extractor
python tongue_identify_dino.py # e = enroll (tongue out), c = recenter,
                               # s = save prototypes, r = reset, Esc = quit
```

The DINO tester saves/loads prototypes from `tongue_proto.npz`, so once you've enrolled, later runs start ready to go.

---

## Tuning

**Colour tracker** — the main knob is the redness threshold `a_thresh` in `tongue_colour.py` (`TongueTracker(a_thresh=150)`):
- **Higher** → stricter, less colour bleed
- **Lower** → more sensitive

`min_area` sets the minimum blob size that counts as "tongue out."

**DINO tracker** — `margin` controls how confidently a patch must look like tongue before it fires (raise it if background leaks in). `grid` trades speed for resolution: smaller (e.g. 6 → 84px input) is faster and coarser; larger (10–12) gives finer masks but costs CPU.

---

## Tech stack

- **Unity** — game engine (C# / ShaderLab / HLSL)
- **MediaPipe** Face Landmarker — mouth localization (used by both trackers)
- **OpenCV** + **NumPy** — image handling and the colour-blob tracker
- **PyTorch** + **DINOv2** — the feature-extractor tracker (optional)
- **UDP** for direction, **TCP** for the JPEG video stream

---

*[8th International Summer School for Artificial Intelligence and Games | Leiden, The Netherlands, June 2026](https://school.gameaibook.org/)*