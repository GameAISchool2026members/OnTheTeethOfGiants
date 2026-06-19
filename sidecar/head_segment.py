"""
Head isolation via MediaPipe multiclass selfie segmentation (CPU).

Keeps only the head (hair + face skin) and removes everything else
(background, neck/body, clothes). Used to stream just the round face + hair.

Model (download once, next to face_landmarker.task):
    curl -L -o selfie_multiclass_256x256.tflite \
      https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite

Class indices (selfie_multiclass_256x256):
    0 background | 1 hair | 2 body-skin | 3 face-skin | 4 clothes | 5 others
"""

import numpy as np
import cv2
import mediapipe as mp

# Category indices
BACKGROUND, HAIR, BODY_SKIN, FACE_SKIN, CLOTHES, OTHERS = range(6)


class HeadSegmenter:
    """Segment the head and composite it over a flat colour (background removed).

    classes : which category indices count as "head". Default = hair + face skin.
              Add OTHERS for glasses/hats, or BODY_SKIN to keep the neck.
    feather : odd Gaussian kernel size to soften the mask edge (0 = hard edge).
    """

    def __init__(self,
                 model_path="selfie_multiclass_256x256.tflite",
                 classes=(HAIR, FACE_SKIN),
                 feather=7):
        BaseOptions           = mp.tasks.BaseOptions
        ImageSegmenter        = mp.tasks.vision.ImageSegmenter
        ImageSegmenterOptions = mp.tasks.vision.ImageSegmenterOptions
        RunningMode           = mp.tasks.vision.RunningMode

        self._classes = list(classes)
        self._feather = feather | 1 if feather else 0   # force odd
        self._k = np.ones((3, 3), np.uint8)

        opts = ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.IMAGE,
            output_category_mask=True,
            output_confidence_masks=False,
        )
        self._seg = ImageSegmenter.create_from_options(opts)

    def mask(self, frame_bgr):
        """Return an HxW uint8 mask (0..255): 255 = head, 0 = removed."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = self._seg.segment(mp_img)
        cat = res.category_mask.numpy_view()            # HxW uint8 of class ids

        m = np.isin(cat, self._classes).astype(np.uint8) * 255
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, self._k)   # drop speckle
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, self._k)  # fill pinholes
        if self._feather:
            m = cv2.GaussianBlur(m, (self._feather, self._feather), 0)
        return m

    def apply(self, frame_bgr, bg_color=(0, 0, 0)):
        """Composite the head over *bg_color*, removing the background.
        Returns the masked BGR frame (same size as input)."""
        m = self.mask(frame_bgr)
        a = (m.astype(np.float32) / 255.0)[..., None]
        bg = np.empty_like(frame_bgr)
        bg[:] = bg_color
        out = frame_bgr.astype(np.float32) * a + bg.astype(np.float32) * (1.0 - a)
        return out.astype(np.uint8)

    def close(self):
        self._seg.close()