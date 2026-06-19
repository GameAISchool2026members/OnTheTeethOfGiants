"""
TCP video server for the tongue sidecar.

Streams JPEG-compressed, length-prefixed webcam frames to Unity over TCP.
The sidecar is the SERVER (start it first); Unity connects as a client and
reconnects automatically. Accepting runs on a background thread so the camera
loop never blocks.

Wire format per frame:  [4-byte big-endian length][JPEG bytes]
"""

import socket
import struct
import threading
import cv2


class VideoServer:
    def __init__(self, host="127.0.0.1", port=5006, width=480, quality=60):
        self.width = width
        self.quality = quality
        self._lock = threading.Lock()
        self._client = None
        self._running = True

        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((host, port))
        self._srv.listen(1)
        threading.Thread(target=self._accept_loop, daemon=True).start()
        print(f"Video server listening on TCP {host}:{port}")

    @property
    def connected(self):
        """True when a Unity client is currently connected."""
        with self._lock:
            return self._client is not None

    def _accept_loop(self):
        while self._running:
            try:
                conn, _ = self._srv.accept()           # blocks for a client
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                with self._lock:
                    if self._client:
                        try: self._client.close()
                        except OSError: pass
                    self._client = conn
                print("Unity connected to video stream")
            except OSError:
                break

    def _resize(self, frame):
        h, w = frame.shape[:2]
        if w != self.width:                            # downscale, keep aspect
            frame = cv2.resize(frame, (self.width, int(h * self.width / w)))
        return frame

    def frame_for_stream(self, frame, jpeg=True):
        """Return the exact image Unity receives for *frame*: resized, and
        (when jpeg=True) round-tripped through the same JPEG compression so
        the artifacts are visible. Intended for a local debug preview."""
        frame = self._resize(frame)
        if jpeg:
            ok, buf = cv2.imencode(".jpg", frame,
                                   [cv2.IMWRITE_JPEG_QUALITY, self.quality])
            if ok:
                frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return frame

    def send(self, frame):
        """Encode and send *frame* to the connected client.
        Returns True if bytes were sent, False otherwise (no client / error)."""
        with self._lock:
            conn = self._client
        if conn is None:
            return False

        frame = self._resize(frame)
        ok, buf = cv2.imencode(".jpg", frame,
                               [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        if not ok:
            return False
        data = buf.tobytes()
        try:
            conn.sendall(struct.pack(">I", len(data)) + data)
        except OSError:                                # client went away
            with self._lock:
                if self._client is conn:
                    self._client = None
            return False
        return True

    def close(self):
        self._running = False
        try: self._srv.close()
        except OSError: pass
        with self._lock:
            if self._client:
                try: self._client.close()
                except OSError: pass