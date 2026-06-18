"""
Standalone webcam tester for the DINOv2 feature-extractor tongue tracker.
Runs alongside the colour version; nothing here touches tongue_colour.py.

Keys:
    e   enroll  -- stick tongue OUT, then press (repeat from a few directions)
    c   recenter (optional directional zero)
    s   save prototypes to tongue_proto.npz
    r   reset prototypes (start enrollment over)
    Esc quit

First run downloads the DINOv2 weights (needs internet once) and is slow to
start. Saved prototypes auto-load next time.

Setup:
    pip install mediapipe opencv-python numpy torch torchvision
    curl -L -o face_landmarker.task \
      https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task

Run:
    python tongue_identify_dino.py
"""

import time
import cv2
import mediapipe as mp
from tongue_dino import TongueDinoTracker, classify_direction

MODEL_PATH = "face_landmarker.task"
CAM_INDEX  = 0
PROTO_PATH = "tongue_proto.npz"

# Smaller grid = faster + coarser. Try 6 (84px) for speed, 10/12 for finer masks.
GRID  = 12
MODEL = "dinov2_vits14_reg"

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

    print("Loading DINOv2 (first run downloads weights)...")
    tracker = TongueDinoTracker(model_name=MODEL, grid=GRID)
    enrolled = tracker.load(PROTO_PATH)
    if enrolled:
        print("Prototypes loaded. Press 'e' to add more, Esc to quit.")
    else:
        print("No prototypes yet. Stick tongue OUT and press 'e' to enroll. Esc to quit.")

    last_ts = -1
    with FaceLandmarker.create_from_options(options) as landmarker:
        t0 = time.perf_counter()
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)                 # mirror -> feels natural

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            ts_ms = int((time.perf_counter() - t0) * 1000)
            if ts_ms <= last_ts:
                ts_ms = last_ts + 1
            last_ts = ts_ms

            result = landmarker.detect_for_video(mp_image, ts_ms)

            t_infer = 0.0
            if result.face_landmarks:
                lms = result.face_landmarks[0]
                t_start = time.perf_counter()
                m = tracker.measure(frame, lms)
                t_infer = (time.perf_counter() - t_start) * 1000

                dx, dy, conf, tmask = m
                direction = classify_direction(dx, dy, conf)

                # Morphological operations to expand and smooth the mask
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                tmask_morph = cv2.morphologyEx(tmask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
                tmask_morph = cv2.morphologyEx(tmask_morph, cv2.MORPH_OPEN, kernel)

                # Edge detection for better boundary marking
                edges = cv2.Canny(tmask_morph, 100, 200)     # first threshold edge linking, second does edge detection

                # Overlay mask and edges
                green = frame.copy()
                green[tmask_morph > 0] = (0, 255, 0)
                frame = cv2.addWeighted(green, 0.4, frame, 0.6, 0)
                frame[edges > 0] = (0, 0, 255)  # Red edges

                cv2.putText(frame,
                            f"{direction}  dx={dx:+.2f} dy={dy:+.2f} "
                            f"conf={conf:.2f}  {t_infer:.0f}ms",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 255, 0), 2)
                else:
                    msg = "no tongue" if tracker._t_n else "press 'e' (tongue out) to enroll"
                    cv2.putText(frame, msg, (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                cv2.putText(frame, "no face", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("tongue tracker (DINOv2)", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:                                   # Esc
                break
            elif key == ord("e") and result.face_landmarks:  # enroll
                tracker.enroll(frame, result.face_landmarks[0])
            elif key == ord("c") and result.face_landmarks:  # recenter
                tracker.recenter(frame, result.face_landmarks[0])
            elif key == ord("s"):                            # save
                tracker.save(PROTO_PATH)
            elif key == ord("r"):                            # reset
                tracker._t_sum = tracker._b_sum = None
                tracker._t_n = tracker._b_n = 0
                print("prototypes reset")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()