"""
Feature-extractor tongue tracker (DINOv2, few-shot prototypes). CPU-capable.

Instead of thresholding redness, this scores each image patch by how much it
looks like *tongue* vs *background* in DINOv2 feature space. No training and no
dataset: you "enroll" once with your tongue out, and MediaPipe geometry (not
colour) supplies the weak labels --

  * patches whose centre falls inside the inner-lip opening  -> tongue examples
  * patches on the lips / surrounding skin                   -> background examples

Their averaged, L2-normalised features become two prototypes. At runtime each
patch's score is  cos(patch, tongue) - cos(patch, background); patches above a
margin (and inside the mouth region) form the tongue mask. Centroid -> (dx, dy),
exactly like the colour tracker, so it slots into the same pipeline.

Interface parity with tongue_colour.TongueTracker:
    measure(frame, lms)  -> (dx, dy, conf, mask) | None
    recenter(frame, lms) -> (ox, oy)
Extra:
    enroll(frame, lms)   -> bool      # capture tongue (tongue OUT), repeatable
    save(path) / load(path)           # persist prototypes between runs

Setup:
    pip install torch torchvision        # CPU build is fine
    # weights download automatically on first run (needs internet once)

Notes:
    * First call is slow (model load + weight download). Steady-state speed
      depends on `grid` and CPU; lower grid = faster + coarser mask.
    * Swap into the sidecar/identify scripts with:
          from tongue_dino import TongueDinoTracker as TongueTracker
      (then bind a key to tracker.enroll instead of calibrate/recenter).
"""

import os
import numpy as np
import cv2

# tongue out -> opening is mostly tongue; reuse the proven geometry + labels.
from tongue_colour import INNER_LIP, OUTER_LIP, classify_direction

_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD  = np.array([0.229, 0.224, 0.225], np.float32)


class DinoFeatures:
    """Loads a DINOv2 backbone and returns an L2-normalised patch-feature grid."""

    def __init__(self, model_name="dinov2_vits14_reg", grid=8, threads=None):
        import torch
        self._torch = torch
        if threads:
            torch.set_num_threads(int(threads))
        self.patch = 14
        self.grid = int(grid)
        self.size = self.grid * self.patch          # square input, multiple of 14
        try:
            self.model = torch.hub.load("facebookresearch/dinov2", model_name)
        except Exception as e:
            raise RuntimeError(
                "Could not load DINOv2 via torch.hub. First run needs internet to "
                "fetch the repo + weights, and `pip install torch torchvision`. "
                f"Underlying error: {e!r}")
        self.model.eval()

    def extract(self, crop_bgr):
        """crop_bgr: HxWx3 uint8 BGR. -> (grid, grid, C) float32, unit-norm rows."""
        torch = self._torch
        img = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self.size, self.size), interpolation=cv2.INTER_AREA)
        x = img.astype(np.float32) / 255.0
        x = (x - _MEAN) / _STD
        x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).contiguous()
        with torch.no_grad():
            tok = self.model.forward_features(x)["x_norm_patchtokens"][0]  # (N, C)
        g = self.grid
        feat = tok.reshape(g, g, -1).numpy().astype(np.float32)            # [y, x, C]
        feat /= (np.linalg.norm(feat, axis=2, keepdims=True) + 1e-6)
        return feat


class TongueDinoTracker:
    def __init__(self, features=None, margin=0.04, min_area=150,
                 model_name="dinov2_vits14_reg", grid=8, threads=None):
        self.fx = features or DinoFeatures(model_name=model_name,
                                           grid=grid, threads=threads)
        self.grid = self.fx.grid
        self.margin = margin            # cos(tongue) - cos(bg) needed to fire
        self.min_area = min_area
        self.ox = self.oy = 0.0
        self._k = np.ones((3, 3), np.uint8)
        # prototype accumulators (sums + counts -> running means)
        self._t_sum = None
        self._t_n = 0
        self._b_sum = None
        self._b_n = 0

    # ---- geometry (mirrors the colour tracker so directions stay identical) ----
    def _pts(self, frame, lms, idx):
        h, w = frame.shape[:2]
        return np.array([[int(lms[i].x * w), int(lms[i].y * h)] for i in idx],
                        dtype=np.int32)

    def _geometry(self, frame, lms):
        h, w = frame.shape[:2]
        inner = self._pts(frame, lms, INNER_LIP)
        outer = self._pts(frame, lms, OUTER_LIP)

        opening = np.zeros((h, w), np.uint8)
        cv2.fillPoly(opening, [inner], 255)
        outer_mask = np.zeros((h, w), np.uint8)
        cv2.fillPoly(outer_mask, [outer], 255)
        lip_band = cv2.bitwise_and(outer_mask, cv2.bitwise_not(opening))
        lip_cut = cv2.dilate(lip_band, self._k, iterations=3)

        x, y, bw, bh = cv2.boundingRect(outer)
        ext = np.array([
            [x - int(0.10 * bw), y + bh - int(0.10 * bh)],
            [x + bw + int(0.10 * bw), y + bh - int(0.10 * bh)],
            [x + bw + int(0.10 * bw), y + bh + int(0.70 * bh)],
            [x - int(0.10 * bw), y + bh + int(0.70 * bh)],
        ], dtype=np.int32)

        search = opening.copy()
        cv2.fillPoly(search, [ext], 255)
        search = cv2.bitwise_and(search, cv2.bitwise_not(lip_cut))

        cx, cy = inner.mean(0)
        box = cv2.boundingRect(np.vstack([outer, ext]))     # x, y, w, h
        bx, by, bwid, bhei = box
        pad = int(0.08 * max(bwid, bhei))
        x0 = max(0, bx - pad)
        y0 = max(0, by - pad)
        x1 = min(w, bx + bwid + pad)
        y1 = min(h, by + bhei + pad)
        return {
            "opening": opening, "lip_cut": lip_cut, "outer_mask": outer_mask,
            "search": search, "box": (x0, y0, x1, y1),
            "mcx": float(cx), "mcy": float(cy), "bw": bw, "bh": bh,
        }

    def _patch_centres(self, box):
        """Full-frame (x, y) pixel coords of each patch centre, shape (g, g, 2)."""
        x0, y0, x1, y1 = box
        cw, ch = (x1 - x0), (y1 - y0)
        g, p, s = self.grid, self.fx.patch, self.fx.size
        gy, gx = np.mgrid[0:g, 0:g]
        px = x0 + ((gx + 0.5) * p) * (cw / s)
        py = y0 + ((gy + 0.5) * p) * (ch / s)
        return np.stack([px, py], axis=2)

    def _sample(self, mask, centres):
        """Boolean (g, g): is each patch centre inside `mask`?"""
        h, w = mask.shape
        ix = np.clip(centres[..., 0].astype(int), 0, w - 1)
        iy = np.clip(centres[..., 1].astype(int), 0, h - 1)
        return mask[iy, ix] > 0

    # ---- enrollment ----
    def enroll(self, frame, lms):
        """Capture the current frame (TONGUE OUT) as labelled examples.
        Repeatable -- call from several directions/lighting to strengthen it."""
        g = self._geometry(frame, lms)
        x0, y0, x1, y1 = g["box"]
        crop = frame[y0:y1, x0:x1]
        if crop.size == 0:
            print("enroll skipped: empty crop")
            return False

        feat = self.fx.extract(crop)                      # (g, g, C)
        centres = self._patch_centres(g["box"])
        is_tongue = self._sample(g["opening"], centres)
        is_bg = self._sample(g["lip_cut"], centres) | ~self._sample(g["outer_mask"], centres)

        t = feat[is_tongue]
        b = feat[is_bg & ~is_tongue]
        if t.shape[0] < 1:
            print("enroll skipped: no tongue patches found (stick tongue OUT first)")
            return False

        self._t_sum = t.sum(0) if self._t_sum is None else self._t_sum + t.sum(0)
        self._t_n += t.shape[0]
        if b.shape[0] > 0:
            self._b_sum = b.sum(0) if self._b_sum is None else self._b_sum + b.sum(0)
            self._b_n += b.shape[0]
        print(f"enrolled  (+{t.shape[0]} tongue, +{b.shape[0]} bg; "
              f"totals {self._t_n}/{self._b_n})")
        return True

    def _protos(self):
        if not self._t_n:
            return None, None
        pt = self._t_sum / self._t_n
        pt = pt / (np.linalg.norm(pt) + 1e-6)
        pb = None
        if self._b_n:
            pb = self._b_sum / self._b_n
            pb = pb / (np.linalg.norm(pb) + 1e-6)
        return pt.astype(np.float32), (pb.astype(np.float32) if pb is not None else None)

    # ---- measurement ----
    def _raw_measure(self, frame, lms):
        pt, pb = self._protos()
        if pt is None:
            return None
        g = self._geometry(frame, lms)
        x0, y0, x1, y1 = g["box"]
        crop = frame[y0:y1, x0:x1]
        if crop.size == 0:
            return None

        feat = self.fx.extract(crop)                       # (g, g, C), unit rows
        score = feat @ pt                                  # cosine to tongue
        if pb is not None:
            score = score - feat @ pb                      # minus cosine to bg

        centres = self._patch_centres(g["box"])
        valid = self._sample(g["search"], centres)
        fire = (score > self.margin) & valid
        if not fire.any():
            return None

        # patch grid -> crop pixels -> full frame, then clip to the search region
        mg = (fire.astype(np.uint8) * 255)
        cw, ch = (x1 - x0), (y1 - y0)
        mcrop = cv2.resize(mg, (cw, ch), interpolation=cv2.INTER_NEAREST)
        full = np.zeros(frame.shape[:2], np.uint8)
        full[y0:y1, x0:x1] = mcrop
        full = cv2.bitwise_and(full, g["search"])
        full = cv2.morphologyEx(full, cv2.MORPH_OPEN, self._k)

        n, labels, stats, cents = cv2.connectedComponentsWithStats(full)
        if n <= 1:
            return None
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area < self.min_area:
            return None

        tx, ty = cents[idx]
        scale = g["bw"] * 0.5 + 1e-6
        dx = (tx - g["mcx"]) / scale
        dy = (ty - g["mcy"]) / scale
        conf = min(1.0, area / (g["bw"] * g["bh"] + 1e-6))

        clean = np.zeros_like(full)
        clean[labels == idx] = 255
        return float(dx), float(dy), float(conf), clean

    def recenter(self, frame, lms):
        """OPTIONAL directional zero (does NOT change detection)."""
        self.ox = self.oy = 0.0
        raw = self._raw_measure(frame, lms)
        if raw is not None:
            self.ox, self.oy = raw[0], raw[1]
            print(f"recentered (dx={self.ox:+.2f}, dy={self.oy:+.2f})")
        else:
            print("recenter skipped: no tongue detected")
        return self.ox, self.oy

    def measure(self, frame, lms):
        raw = self._raw_measure(frame, lms)
        if raw is None:
            return None
        dx, dy, conf, clean = raw
        return dx - self.ox, dy - self.oy, conf, clean

    # ---- persistence ----
    def save(self, path="tongue_proto.npz"):
        if not self._t_n:
            print("nothing to save (enroll first)")
            return
        b_sum = self._b_sum if self._b_sum is not None else np.zeros_like(self._t_sum)
        np.savez(path, t_sum=self._t_sum, t_n=self._t_n, b_sum=b_sum, b_n=self._b_n)
        print(f"saved prototypes -> {path}")

    def load(self, path="tongue_proto.npz"):
        if not os.path.exists(path):
            return False
        d = np.load(path)
        self._t_sum = d["t_sum"].astype(np.float32)
        self._t_n = int(d["t_n"])
        self._b_n = int(d["b_n"])
        self._b_sum = d["b_sum"].astype(np.float32) if self._b_n else None
        print(f"loaded prototypes ({self._t_n}/{self._b_n}) <- {path}")
        return True