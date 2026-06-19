"""
Lightweight tongue-position measurement (CPU-only). No calibration required.

Detection uses a FIXED redness threshold (a_thresh) plus a spatial mask:
search the mouth opening + small extensions ABOVE and BELOW it (lips cut out),
so the tongue can be seen whether it goes up over the upper lip or down over
the lower lip. The upward extension is capped just below the nose (using the
nose landmarks) so the nostrils never get mistaken for tongue. Returns the
tongue centroid as a normalized (dx, dy) offset.

States: up / down / left / right / closed  (no center).
'closed' = tongue not out.  A detected tongue always resolves to a direction.

UP/DOWN are decided by where the tongue crosses the lips, not just by the
averaged centroid: when the tongue sticks up over the UPPER lip the in-mouth
base would otherwise drag the centroid down, so we bias the vertical signal by
how much of the tongue lies above the upper lip (or below the lower lip). Tune
v_gain if up/down feels too eager or too reluctant.

If your lighting changes a lot and detection degrades, just edit a_thresh
by hand (higher = stricter/less bleed, lower = more sensitive).
"""

import numpy as np
import cv2

INNER_LIP = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308,
             324, 318, 402, 317, 14, 87, 178, 88, 95]
OUTER_LIP = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291,
             375, 321, 405, 314, 17, 84, 181, 91, 146]
# Nose-base landmarks (subnasale + the two nostril/ala bottoms). Their lowest
# point is the floor of the nose; the upward search is capped below it so the
# nostrils never enter the mask.
NOSE_BOTTOM = [2, 98, 327]


class TongueTracker:
    def __init__(self, a_thresh=150, min_area=130, v_gain=2.0):
        self.a_thresh = a_thresh     # FIXED redness cutoff; hand-tune if lighting changes
        self.min_area = min_area     # min blob pixels to count as "tongue out"
        self.v_gain = float(v_gain)  # how hard crossing a lip pushes up/down
        self.ox = 0.0                # neutral offset (set only by recenter)
        self.oy = 0.0
        self._k = np.ones((3, 3), np.uint8)

    def _pts(self, frame, lms, idx):
        h, w = frame.shape[:2]
        return np.array([[int(lms[i].x * w), int(lms[i].y * h)] for i in idx],
                        dtype=np.int32)

    def _redness(self, frame):
        return cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)[:, :, 1]   # a* channel

    def _masks(self, frame, lms):
        """search_mask (lip flesh removed), mouth center, mouth (bw, bh)."""
        h, w = frame.shape[:2]
        inner = self._pts(frame, lms, INNER_LIP)
        outer = self._pts(frame, lms, OUTER_LIP)

        opening = np.zeros((h, w), np.uint8)
        cv2.fillPoly(opening, [inner], 255)

        outer_mask = np.zeros((h, w), np.uint8)
        cv2.fillPoly(outer_mask, [outer], 255)

        lip_band = cv2.bitwise_and(outer_mask, cv2.bitwise_not(opening))
        lip_band = cv2.dilate(lip_band, self._k, iterations=3)

        x, y, bw, bh = cv2.boundingRect(outer)
        # upward search ceiling: reach toward the upper lip but stop below the
        # nose so nostrils never enter the mask. Anchor to the nose landmarks
        # (scale-adaptive) and fall back to a fixed fraction if the nose sits
        # oddly (e.g. a bad frame).
        up_limit = y - int(0.70 * bh)
        nose_floor = float(self._pts(frame, lms, NOSE_BOTTOM)[:, 1].max())
        if nose_floor < y:                                   # nose is above the mouth
            ceiling = nose_floor + 0.30 * (y - nose_floor)   # keep a 30% buffer below it
            up_limit = max(up_limit, int(ceiling))
        # downward extension (tongue down, over the lower lip / toward chin)
        ext_dn = np.array([
            [x - int(0.10 * bw), y + bh - int(0.10 * bh)],
            [x + bw + int(0.10 * bw), y + bh - int(0.10 * bh)],
            [x + bw + int(0.10 * bw), y + bh + int(0.70 * bh)],
            [x - int(0.10 * bw), y + bh + int(0.70 * bh)],
        ], dtype=np.int32)
        # upward extension (tongue up, over the upper lip), capped below the nose
        ext_up = np.array([
            [x - int(0.10 * bw), up_limit],
            [x + bw + int(0.10 * bw), up_limit],
            [x + bw + int(0.10 * bw), y + int(0.10 * bh)],
            [x - int(0.10 * bw), y + int(0.10 * bh)],
        ], dtype=np.int32)

        search = opening.copy()
        cv2.fillPoly(search, [ext_dn], 255)
        cv2.fillPoly(search, [ext_up], 255)
        search = cv2.bitwise_and(search, cv2.bitwise_not(lip_band))

        cx, cy = inner.mean(0)
        return search, (float(cx), float(cy)), (bw, bh)

    def _raw_measure(self, frame, lms):
        search, (mcx, mcy), (bw, bh) = self._masks(frame, lms)
        inner = self._pts(frame, lms, INNER_LIP)
        top_y = float(inner[:, 1].min())     # upper inner-lip line
        bot_y = float(inner[:, 1].max())     # lower inner-lip line

        a = self._redness(frame)
        tongue = ((a > self.a_thresh).astype(np.uint8) * 255)
        tongue = cv2.bitwise_and(tongue, search)
        tongue = cv2.morphologyEx(tongue, cv2.MORPH_OPEN, self._k)

        n, labels, stats, cents = cv2.connectedComponentsWithStats(tongue)
        if n <= 1:
            return None
        # Keep EVERY sizeable blob, not just the biggest: when the tongue goes
        # up, the upper-lip cut splits it into a tip (above the lip) and a base
        # (inside the mouth). Taking only the largest blob throws the tip away
        # and the lone base reads as "down". Union all blobs above a small
        # floor so the tip still counts; specks are already gone after OPEN.
        keep_min = max(self.min_area // 4, 40)
        keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= keep_min]
        if not keep:                                  # fall back to the largest
            keep = [1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))]
        area = int(sum(stats[i, cv2.CC_STAT_AREA] for i in keep))
        if area < self.min_area:
            return None

        clean = np.where(np.isin(labels, keep), 255, 0).astype(np.uint8)

        ys, xs = np.where(clean > 0)
        tx, ty = float(xs.mean()), float(ys.mean())

        # How much of the tongue sticks out ABOVE the upper lip / BELOW the
        # lower lip. "Tongue over the upper lip" -> strong up, even when the
        # in-mouth base would otherwise pull the centroid back down.
        up_frac = float(np.mean(ys < top_y))
        dn_frac = float(np.mean(ys > bot_y))

        scale = bw * 0.5 + 1e-6
        dx = (tx - mcx) / scale
        dy = (ty - mcy) / scale
        dy += self.v_gain * (dn_frac - up_frac)   # bias toward the lip crossed
        dy = float(np.clip(dy, -2.0, 2.0))         # keep analog range sane for Unity

        conf = min(1.0, area / (bw * bh + 1e-6))
        return float(dx), float(dy), float(conf), clean

    def recenter(self, frame, lms):
        """OPTIONAL. Capture the current tongue position as the directional
        zero. Does NOT change detection."""
        self.ox = self.oy = 0.0
        raw = self._raw_measure(frame, lms)
        if raw is not None:
            self.ox, self.oy = raw[0], raw[1]
            print(f"recentered (neutral set to dx={self.ox:+.2f}, dy={self.oy:+.2f})")
        else:
            print("recenter skipped: no tongue detected")
        return self.ox, self.oy

    def measure(self, frame, lms):
        raw = self._raw_measure(frame, lms)
        if raw is None:
            return None
        dx, dy, conf, clean = raw
        return dx - self.ox, dy - self.oy, conf, clean


def classify_direction(dx, dy, conf):
    """Return one of: 'up', 'down', 'left', 'right', 'closed'.
    'closed' = tongue not out (conf == 0). A detected tongue always resolves
    to a direction; there is no 'center' state.
    y grows downward; the frame is mirrored, so 'left' is screen-left."""
    if conf <= 0.0:
        return "closed"
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


def mouth_crop(frame, lms, pad=0.15):
    """Crop *frame* to the mouth region — for streaming to the dino game.

    Spans the outer-lip box widened by *pad* on the sides, extended DOWN past
    the lower lip (where the tongue droops) and UP toward the nose, capped just
    below the nostrils with the same nose buffer the detector uses. The crop
    therefore covers the full range the tongue can reach, up or down.

    Returns a numpy view; falls back to the full frame if the box is degenerate.
    NOTE: this is purely what the dino side *receives* — landmarks/detection run
    on the full frame, so cropping never changes detection accuracy here.
    """
    h, w = frame.shape[:2]
    outer = np.array([[lms[i].x * w, lms[i].y * h] for i in OUTER_LIP])
    x0, y0 = outer.min(0)
    x1, y1 = outer.max(0)
    bw, bh = x1 - x0, y1 - y0
    if bw < 2 or bh < 2:                       # degenerate / no mouth
        return frame

    cx0 = x0 - pad * bw                        # sideways padding
    cx1 = x1 + pad * bw
    cy1 = y1 + 0.70 * bh                       # down toward the chin
    cy0 = y0 - 0.70 * bh                       # up toward the nose...
    nose_floor = max(lms[i].y * h for i in NOSE_BOTTOM)
    if nose_floor < y0:                        # ...capped below the nostrils
        cy0 = max(cy0, nose_floor + 0.30 * (y0 - nose_floor))

    px0, px1 = int(max(0, cx0)), int(min(w, cx1))
    py0, py1 = int(max(0, cy0)), int(min(h, cy1))
    if px1 <= px0 or py1 <= py0:
        return frame
    return frame[py0:py1, px0:px1]