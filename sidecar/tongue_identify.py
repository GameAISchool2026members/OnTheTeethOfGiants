"""
Lightweight tongue-direction tracker (CPU-only).

MediaPipe Face Landmarker locates the mouth; tongue_colour isolates the tongue
by redness inside the mouth region and reports its position as up/down/left/
right plus a continuous (dx, dy). A Kalman filter (tongue_kalman) smooths the
offset and stabilises the direction. Press 'c' (tongue out, centered) to
re-center to your tongue and lighting; Esc to quit.

Setup:
    pip install mediapipe opencv-python numpy
    curl -L -o face_landmarker.task \
      https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task

Run:
    python tongue_identify.py
"""
import time
import cv2
import mediapipe as mp
from tongue_colour import TongueTracker, classify_direction
from tongue_kalman import TongueKalman

# ---- Config ----
MODEL_PATH = "face_landmarker.task"
CAM_INDEX  = 1

# ---- Face Landmarker setup (Tasks API, VIDEO mode) ----
BaseOptions           = mp.tasks.BaseOptions
FaceLandmarker        = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
RunningMode           = mp.tasks.vision.RunningMode

options = FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=RunningMode.VIDEO,
    num_faces=1,
)


def main():
    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam (index {CAM_INDEX}).")
    print("Webcam opened. Stick tongue out + press 'c' to re-center. Esc to quit.")

    tracker = TongueTracker()
    kf = TongueKalman()                # smooths (dx, dy); see tongue_kalman.py
    last_ts = -1

    with FaceLandmarker.create_from_options(options) as landmarker:
        t0 = time.perf_counter()
        t_prev = t0                    # for real dt between frames
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)     # mirror -> feels natural

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            # VIDEO mode needs a strictly increasing timestamp (ms).
            ts_ms = int((time.perf_counter() - t0) * 1000)
            if ts_ms <= last_ts:
                ts_ms = last_ts + 1
            last_ts = ts_ms

            result = landmarker.detect_for_video(mp_image, ts_ms)

            now = time.perf_counter()
            dt = now - t_prev
            t_prev = now

            display = frame.copy()         # draw overlays here; keep `frame` clean for recenter
            if result.face_landmarks:
                # ---- raw measurement (or None) ----
                meas = None
                tmask = None
                m = tracker.measure(frame, result.face_landmarks[0])
                if m is not None:
                    rdx, rdy, conf, tmask = m
                    meas = (rdx, rdy, conf)

                # ---- Kalman smoothing ----
                dx, dy, valid = kf.step(meas, dt)
                direction = classify_direction(dx, dy, 1.0) if valid else "closed"

                if tmask is not None:
                    display[tmask > 0] = (0, 255, 0)   # detected tongue
                    display = cv2.addWeighted(display, 0.4, frame, 0.6, 0)

                if valid:
                    cv2.putText(display,
                                f"{direction}   dx={dx:+.2f}  dy={dy:+.2f}",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                (0, 255, 0), 2)
                else:
                    cv2.putText(display, "closed", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                kf.step(None, dt)                           # let the filter coast/close
                cv2.putText(display, "no face", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("tongue tracker", display)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:                                      # Esc
                break
            elif key == ord("c") and result.face_landmarks:    # optional re-center
                tracker.recenter(frame, result.face_landmarks[0])
                kf.reset()                                     # avoid a lurch at the new zero

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()