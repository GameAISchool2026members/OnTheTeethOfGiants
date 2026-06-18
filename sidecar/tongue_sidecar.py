"""
Lightweight tongue-direction tracker -> UDP sidecar for Unity.

This process OWNS the webcam, detects tongue direction, Kalman-smooths it, and
streams "dx,dy,conf" as a UDP datagram to Unity (127.0.0.1:5005) every frame.
Unity only listens; it does NOT open the camera.

Press 'c' (tongue out, centered) to re-center; Esc to quit.
Run this FIRST, then press Play in Unity.
"""

import time
import socket
import cv2
import mediapipe as mp
from video_server import VideoServer
from tongue_colour import TongueTracker, classify_direction
from tongue_kalman import TongueKalman

MODEL_PATH  = "face_landmarker.task"
CAM_INDEX   = 0
UNITY_HOST  = "127.0.0.1"
UNITY_PORT  = 5005
SHOW_WINDOW = True          # set False to run headless (no re-center key then)

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
    print(f"Webcam opened. Streaming to {UNITY_HOST}:{UNITY_PORT}. "
          f"Tongue out + 'c' to re-center. Esc to quit.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tracker = TongueTracker()
    kf = TongueKalman()                 # smooths (dx, dy); see tongue_kalman.py
    video = VideoServer(width=480, quality=60)

    last_ts = -1
    last_conf = 0.0                     # held during brief coasts so conf stays > 0

    with FaceLandmarker.create_from_options(options) as landmarker:
        t0 = time.perf_counter()
        t_prev = t0                     # for real dt between frames
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)     # mirror -> feels natural

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            ts_ms = int((time.perf_counter() - t0) * 1000)
            if ts_ms <= last_ts:
                ts_ms = last_ts + 1
            last_ts = ts_ms

            result = landmarker.detect_for_video(mp_image, ts_ms)

            now = time.perf_counter()
            dt = now - t_prev
            t_prev = now

            # ---- raw measurement (or None) ----
            meas = None
            tmask = None
            if result.face_landmarks:
                m = tracker.measure(frame, result.face_landmarks[0])
                if m is not None:
                    rdx, rdy, conf, tmask = m
                    meas = (rdx, rdy, conf)
                    last_conf = conf

            # ---- Kalman smoothing ----
            dx, dy, valid = kf.step(meas, dt)
            if valid:
                direction = classify_direction(dx, dy, 1.0)
                conf_out = meas[2] if meas is not None else last_conf
            else:
                direction = "closed"
                conf_out = 0.0

            # ---- stream smoothed estimate to Unity every frame ----
            sock.sendto(f"{dx:.4f},{dy:.4f},{conf_out:.4f}".encode("ascii"),
                        (UNITY_HOST, UNITY_PORT))
            video.send(frame)                          # raw frame, no debug overlay

            if SHOW_WINDOW:
                display = frame.copy()                 # keep `frame` clean for recenter
                if tmask is not None:
                    display[tmask > 0] = (0, 255, 0)
                    display = cv2.addWeighted(display, 0.4, frame, 0.6, 0)
                if valid:
                    cv2.putText(display,
                                f"{direction}  dx={dx:+.2f} dy={dy:+.2f} conf={conf_out:.2f}",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    cv2.putText(display, "closed", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.imshow("tongue tracker (sidecar)", display)

                key = cv2.waitKey(1) & 0xFF
                if key == 27:                                    # Esc
                    break
                elif key == ord("c") and result.face_landmarks:  # re-center
                    tracker.recenter(frame, result.face_landmarks[0])   # clean frame, not the overlay
                    kf.reset()                                   # avoid a lurch at the new zero

    video.close()
    sock.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()