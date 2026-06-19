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
    def __init__(self, features=None, margin=0.28, min_area=120,
                 model_name="dinov2_vits14_reg", grid=8, threads=None,
                 reach=(0.6, 1.0, 1.8), v_gain=2.0):
        self.fx = features or DinoFeatures(model_name=model_name,
                                           grid=grid, threads=threads)
        self.grid = self.fx.grid
        self.margin = margin            # cos(tongue) - cos(bg) needed to fire
        self.min_area = min_area
        # How far past the mouth box the tongue may reach, as fractions of mouth
        # width/height: (sideways, up, down). The envelope both crops what DINO
        # sees and gates the final mask, so a side/up/down tongue must fit inside
        # it. Up reaches toward the nose; it is capped below the nostrils in
        # _geometry so the nostrils never enter the search region.
        self.reach_x, self.reach_up, self.reach_dn = reach
        self.v_gain = float(v_gain)     # how hard crossing a lip pushes up/down
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
        # Generous envelope around the mouth: the tongue may protrude in any
        # direction, sometimes a long way. This both bounds the DINO crop and
        # gates the final mask, so it MUST contain a fully-extended tongue --
        # including the extreme up/down poses. We deliberately do NOT cap the
        # upward reach at the nose: unlike the colour tracker, the tongue-vs-
        # background prototype score rejects nostrils/skin on its own, so a nose
        # cap would only clip an extreme up-tongue reaching toward the nose.
        mx = int(self.reach_x * bw)
        dn = int(self.reach_dn * bh)
        ex0, ey0 = x - mx, y - int(self.reach_up * bh)
        ex1, ey1 = x + bw + mx, y + bh + dn
        env = np.array([[ex0, ey0], [ex1, ey0], [ex1, ey1], [ex0, ey1]],
                       dtype=np.int32)

        # Search region = the envelope. NOTE: we deliberately do NOT subtract the
        # lip band here (unlike the colour tracker). A side/up/down tongue lies on
        # top of the lip, so cutting the lips out would clip it; the tongue-vs-bg
        # prototype score is what keeps lips/skin from firing.
        search = np.zeros((h, w), np.uint8)
        cv2.fillPoly(search, [env], 255)

        cx, cy = inner.mean(0)
        x0 = max(0, ex0)
        y0 = max(0, ey0)
        x1 = min(w, ex1)
        y1 = min(h, ey1)
        return {
            "opening": opening, "lip_cut": lip_cut, "outer_mask": outer_mask,
            "search": search, "box": (x0, y0, x1, y1),
            "mcx": float(cx), "mcy": float(cy), "bw": bw, "bh": bh,
            "inner_top": float(inner[:, 1].min()),   # upper inner-lip line
            "inner_bot": float(inner[:, 1].max()),   # lower inner-lip line
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

        # Bootstrap for EXTREME poses: once a tongue prototype exists, also count
        # patches anywhere in the envelope that already look like tongue. In an
        # extreme up/down pose the tongue has left the inner-lip opening, so the
        # opening alone labels nothing -- this lets you hold the pose, press the
        # enroll key, and grow the prototype to cover it. (These patches are also
        # excluded from background below via `& ~is_tongue`.)
        pt, pb = self._protos()
        if pt is not None:
            sc = feat @ pt
            if pb is not None:
                sc = sc - feat @ pb
            in_env = self._sample(g["search"], centres)
            is_tongue = is_tongue | (in_env & (sc > self.margin))

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
        # Keep EVERY sizeable blob, not just the biggest. When the tongue goes up
        # the tip (over the upper lip) can separate from the in-mouth base after
        # morphology; taking only the largest blob throws the tip away and the
        # lone base reads as "down". Union all blobs above a small floor.
        keep_min = max(self.min_area // 4, 40)
        keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= keep_min]
        if not keep:                                   # fall back to the largest
            keep = [1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))]
        area = int(sum(stats[i, cv2.CC_STAT_AREA] for i in keep))
        if area < self.min_area:
            return None

        clean = np.where(np.isin(labels, keep), 255, 0).astype(np.uint8)

        ys, xs = np.where(clean > 0)
        tx, ty = float(xs.mean()), float(ys.mean())

        # How much of the tongue sticks out ABOVE the upper lip / BELOW the lower
        # lip. "Tongue over the upper lip" -> strong up, even when the in-mouth
        # base would otherwise pull the centroid back down.
        up_frac = float(np.mean(ys < g["inner_top"]))
        dn_frac = float(np.mean(ys > g["inner_bot"]))

        scale = g["bw"] * 0.5 + 1e-6
        dx = (tx - g["mcx"]) / scale
        dy = (ty - g["mcy"]) / scale
        dy += self.v_gain * (dn_frac - up_frac)        # bias toward the lip crossed
        dy = float(np.clip(dy, -2.0, 2.0))             # keep analog range sane

        conf = min(1.0, area / (g["bw"] * g["bh"] + 1e-6))
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