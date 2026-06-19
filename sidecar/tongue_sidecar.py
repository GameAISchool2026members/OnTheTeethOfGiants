"""
Lightweight tongue-direction tracker -> UDP sidecar for Unity.

This process OWNS the webcam, detects tongue direction, and streams
"dx,dy,conf" as a UDP datagram to Unity (127.0.0.1:5005) every frame.
Unity only listens; it does NOT open the camera.

Press 'c' (tongue out, centered) to calibrate; Esc to quit.
Run this FIRST, then press Play in Unity.

Debug windows:
  SHOW_WINDOW  – full annotated webcam frame (detection overlay)
  SHOW_STREAM  – exactly what is sent to Unity (cropped + JPEG), with a
                 "Unity: connected / waiting" status banner

REMOVE_BACKGROUND is OFF by default (it adds a second model per frame and is
heavy on CPU). Flip it to True to keep only the head (hair + face); that needs
head_segment.py and the selfie_multiclass_256x256.tflite model.
"""

import time
import socket
import cv2
import mediapipe as mp
from video_server import VideoServer
from tongue_colour import TongueTracker as _ColourTracker, classify_direction, mouth_crop
from tongue_dino import TongueDinoTracker as _DinoTracker

# ── Swap tracker backend here ──────────────────────────────────────────────────
TRACKER = "dino"   # "colour"  →  redness threshold (fast, CPU, no extra deps)
                   # "dino"    →  DINOv2 feature tracker (more robust)
# ──────────────────────────────────────────────────────────────────────────────
TongueTracker = {"colour": _ColourTracker, "dino": _DinoTracker}[TRACKER]

# ── Swap what gets streamed to the dino game ───────────────────────────────────
CROP = "face"     # "mouth" →  just the mouth region (tight; easiest for dino)
                   # "face"  →  padded head/face crop (respects REMOVE_BACKGROUND)
                   # "full"  →  whole mirrored frame
# ──────────────────────────────────────────────────────────────────────────────

MODEL_PATH        = "face_landmarker.task"
SEG_MODEL_PATH    = "selfie_multiclass_256x256.tflite"
CAM_INDEX         = 0
PROC_WIDTH        = 640             # cap processing resolution. High-res webcams
                                    # are downscaled to this width so the dino
                                    # tracker sees the same scale on any camera.
                                    # Set to 0 to use the camera's native size.
UNITY_HOST        = "127.0.0.1"
UNITY_PORT        = 5005
SHOW_WINDOW       = True            # annotated webcam frame
SHOW_STREAM       = True            # what Unity actually receives
MIRROR_STREAM     = True            # flip the crop horizontally before sending to
                                    # Unity. The detection frame is already mirrored
                                    # (selfie view); this flips the STREAM back to
                                    # the true camera orientation, independently, so
                                    # detection / dx signs are untouched.
FACE_PAD          = 0.25            # padding around face crop (fraction of box)
MOUTH_PAD         = 0.15            # sideways padding around mouth crop
REMOVE_BACKGROUND = False           # OFF: heavy on CPU. True keeps only the head.
BG_COLOR          = (0, 0, 0)       # BGR fill for removed background (if enabled)

BaseOptions           = mp.tasks.BaseOptions
FaceLandmarker        = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
RunningMode           = mp.tasks.vision.RunningMode

options = FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=RunningMode.VIDEO,
    num_faces=1,
)


def crop_face(frame, lms, pad: float = FACE_PAD):
    """Return a padded crop of the face region from *frame*.

    Uses all 478 MediaPipe landmark x/y values to compute the tightest
    bounding box, then expands it by *pad* (fraction of box size) on each
    side.  Falls back to the full frame when the box is degenerate.
    """
    h, w = frame.shape[:2]
    xs = [lm.x for lm in lms]
    ys = [lm.y for lm in lms]
    x0 = max(0.0, min(xs))
    y0 = max(0.0, min(ys))
    x1 = min(1.0, max(xs))
    y1 = min(1.0, max(ys))

    bw, bh = x1 - x0, y1 - y0
    if bw < 0.01 or bh < 0.01:          # degenerate / no face
        return frame

    x0 = max(0.0, x0 - pad * bw)
    y0 = max(0.0, y0 - pad * bh)
    x1 = min(1.0, x1 + pad * bw)
    y1 = min(1.0, y1 + pad * bh)

    px0, py0 = int(x0 * w), int(y0 * h)
    px1, py1 = int(x1 * w), int(y1 * h)
    return frame[py0:py1, px0:px1]


def stream_crop(frame, result, segmenter):
    """Pick what to send to the dino game based on CROP. Falls back to the full
    frame whenever no face is detected (so Unity never sees a stale image)."""
    if not result.face_landmarks:
        return frame
    lms0 = result.face_landmarks[0]
    if CROP == "mouth":
        return mouth_crop(frame, lms0, pad=MOUTH_PAD)
    if CROP == "face":
        out = crop_face(frame, lms0)
        if segmenter is not None:
            out = segmenter.apply(out, bg_color=BG_COLOR)
        return out
    return frame                                    # "full"


def main():
    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {CAM_INDEX}).")

    # Ask the driver for a smaller frame (saves bandwidth). Cameras snap to the
    # nearest supported mode, so the per-frame downscale below still enforces
    # PROC_WIDTH exactly — this is just a hint.
    if PROC_WIDTH:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, PROC_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(PROC_WIDTH * 3 / 4))
    cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera delivers {cam_w}x{cam_h}; "
          f"processing at width {PROC_WIDTH or cam_w}.")
    print(f"Streaming to {UNITY_HOST}:{UNITY_PORT}. "
          f"Tongue out + 'c' to calibrate. Esc to quit.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tracker = TongueTracker()
    last_ts = -1
    video = VideoServer(width=480, quality=60)

    # Background removal only makes sense on the face crop; skip it for mouth/full.
    segmenter = None
    if REMOVE_BACKGROUND and CROP == "face":
        from head_segment import HeadSegmenter
        segmenter = HeadSegmenter(model_path=SEG_MODEL_PATH)
    elif REMOVE_BACKGROUND:
        print(f"REMOVE_BACKGROUND ignored: only applies when CROP == 'face' "
              f"(CROP is '{CROP}').")

    with FaceLandmarker.create_from_options(options) as landmarker:
        t0 = time.perf_counter()
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if PROC_WIDTH and frame.shape[1] > PROC_WIDTH:   # normalize resolution
                h, w = frame.shape[:2]
                frame = cv2.resize(frame, (PROC_WIDTH, int(h * PROC_WIDTH / w)),
                                   interpolation=cv2.INTER_AREA)
            frame = cv2.flip(frame, 1)     # mirror -> feels natural

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            ts_ms = int((time.perf_counter() - t0) * 1000)
            if ts_ms <= last_ts:
                ts_ms = last_ts + 1
            last_ts = ts_ms

            result = landmarker.detect_for_video(mp_image, ts_ms)

            dx = dy = conf = 0.0
            tmask = None
            if result.face_landmarks:
                m = tracker.measure(frame, result.face_landmarks[0])
                if m is not None:
                    dx, dy, conf, tmask = m

            direction = classify_direction(dx, dy, conf)

            # ---- UDP tongue data to Unity ----
            sock.sendto(f"{dx:.4f},{dy:.4f},{conf:.4f}".encode("ascii"),
                        (UNITY_HOST, UNITY_PORT))

            # ---- TCP video: stream the chosen crop (mouth by default) ----
            stream_frame = stream_crop(frame, result, segmenter)
            if MIRROR_STREAM:
                stream_frame = cv2.flip(stream_frame, 1)   # orient for Unity only
            video.send(stream_frame)

            # ---- debug window 1: full annotated frame ----
            if SHOW_WINDOW:
                if tmask is not None:
                    green = frame.copy()
                    green[tmask > 0] = (0, 255, 0)
                    frame = cv2.addWeighted(green, 0.4, frame, 0.6, 0)
                    cv2.putText(frame,
                                f"{direction}  dx={dx:+.2f} dy={dy:+.2f} conf={conf:.2f}",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    cv2.putText(frame, "no tongue", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.imshow("tongue tracker (sidecar)", frame)

            # ---- debug window 2: exactly what Unity receives ----
            if SHOW_STREAM:
                streamed = video.frame_for_stream(stream_frame)   # resized + JPEG round-trip
                up = video.connected
                status = "Unity: connected" if up else "Unity: waiting..."
                colour = (0, 255, 0) if up else (0, 165, 255)
                h2, w2 = streamed.shape[:2]
                cv2.putText(streamed, status, (8, 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 2)
                cv2.putText(streamed, f"{w2}x{h2}  q{video.quality}  [{CROP}]", (8, h2 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
                cv2.imshow("stream -> unity", streamed)

            # ---- single key handler for both windows ----
            if SHOW_WINDOW or SHOW_STREAM:
                key = cv2.waitKey(1) & 0xFF
                if key == 27:                                    # Esc
                    break
                elif key == ord("c") and result.face_landmarks:  # calibrate
                    tracker.recenter(frame, result.face_landmarks[0])
                elif key == ord("e"):
                    tracker.enroll(frame, result.face_landmarks[0])  # Dino tracker only; no-op for colour

    if segmenter is not None:
        segmenter.close()
    video.close()
    sock.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()