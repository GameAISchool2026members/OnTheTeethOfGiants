"""
2-D Kalman filter for smoothing the tongue offset (dx, dy).

The raw centroid from tongue_colour jitters frame-to-frame and occasionally
drops out for a frame or two. This filter:

  * smooths (dx, dy) and stabilises the up/down/left/right classification,
  * trusts confident measurements more (R grows as conf shrinks),
  * coasts through brief dropouts (up to `max_coast` frames) so a one-frame
    miss doesn't flicker the direction,
  * reports "closed" once dropouts exceed the budget, and resets so the next
    tongue-out starts clean.

MODEL CHOICE — constant position (random walk), not constant velocity.
The tongue snaps to a pose and *holds* it. A constant-velocity model assumes
steady motion, so velocity builds up during each snap and then overshoots the
hold (measured: it does worse than the raw signal on this data). A random-walk
model has no velocity to fling, never overshoots a held pose, and when it
coasts through a dropout it simply holds the last position -- exactly the
right guess for a momentary detection miss. On synthetic data matching this
pipeline it cut steady-state jitter ~35% and direction flips from ~4 to ~1
per gesture (the remaining flip being the real one).

State:        x = [px, py]        (position = the dx, dy offset)
Measurement:  z = [px, py]
dt is the real wall-clock gap between frames (clamped), so behaviour is the
same whether the camera runs at 12 or 30 fps.

Tuning (two knobs that matter):
  q  bigger -> more responsive, lets more jitter through
  r  bigger -> smoother, more lag
The ratio q/r sets responsiveness. Tune on your real footage and lighting.
Latencies with the defaults at ~18 fps: ~1 frame to follow a snap; "closed"
fires within `max_coast` frames of the tongue going back in.
"""

import numpy as np


class TongueKalman:
    def __init__(self,
                 q=8.0,            # process-noise rate (bigger -> more responsive)
                 r=0.04,           # base measurement-noise variance at conf == 1
                 use_conf=True,    # scale R by 1/conf (set False if it over-smooths)
                 conf_floor=0.10,  # clamp so tiny-conf frames don't blow R up
                 max_coast=3,      # frames to hold through a dropout before "closed"
                 dt_max=0.10):     # clamp dt so a pause can't jerk the estimate
        self.q = float(q)
        self.r = float(r)
        self.use_conf = bool(use_conf)
        self.conf_floor = float(conf_floor)
        self.max_coast = int(max_coast)
        self.dt_max = float(dt_max)

        self.x = None             # state (2,), None until first measurement
        self.P = None             # covariance (2, 2)
        self._miss = 0            # consecutive frames without a measurement

    def reset(self):
        self.x = None
        self.P = None
        self._miss = 0

    def update(self, dx, dy, conf, dt):
        """Fold in a fresh measurement. Returns smoothed (dx, dy)."""
        if self.x is None:                          # first sighting: jump to it
            self.x = np.array([dx, dy], dtype=float)
            self.P = np.eye(2) * self.r
            self._miss = 0
            return float(dx), float(dy)

        dt = float(np.clip(dt, 1e-3, self.dt_max))

        # predict  (F = I; position persists, uncertainty grows)
        self.P = self.P + np.eye(2) * (self.q * dt)

        # update   (H = I; R larger when the detection is less confident)
        r = self.r / max(conf, self.conf_floor) if self.use_conf else self.r
        S = self.P + np.eye(2) * r
        K = self.P @ np.linalg.inv(S)
        self.x = self.x + K @ (np.array([dx, dy]) - self.x)
        self.P = (np.eye(2) - K) @ self.P

        self._miss = 0
        return float(self.x[0]), float(self.x[1])

    def coast(self, dt):
        """No measurement this frame. Hold the last position if still within
        the coast budget. Returns (dx, dy, still_out):
            still_out True  -> coasted estimate; treat tongue as still out
            still_out False -> give up; caller should report 'closed'."""
        if self.x is None or self._miss >= self.max_coast:
            self.reset()
            return 0.0, 0.0, False

        self._miss += 1
        dt = float(np.clip(dt, 1e-3, self.dt_max))
        self.P = self.P + np.eye(2) * (self.q * dt)   # F = I, so x is unchanged
        return float(self.x[0]), float(self.x[1]), True

    def step(self, measurement, dt):
        """One-call wrapper for the frame loop.
            measurement = (dx, dy, conf) if a tongue was detected this frame,
                          or None if it wasn't.
        Returns (dx, dy, valid); valid == False means 'closed'."""
        if measurement is None:
            return self.coast(dt)
        dx, dy, conf = measurement
        sx, sy = self.update(dx, dy, conf, dt)
        return sx, sy, True