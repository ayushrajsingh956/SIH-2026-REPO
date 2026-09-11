import logging
import time
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def preprocess_image(image_bytes: bytes) -> tuple[bytes, dict[str, Any]]:
    """Preprocesses a raw image byte buffer using OpenCV.

    Pipeline:
    1. Decode image array (validates against corrupt/poison image bytes)
    2. Grayscale conversion
    3. Denoising (fastNlMeans or median filter)
    4. Adaptive thresholding
    5. Deskew via minAreaRect
    6. Encode preprocessed image to PNG bytes

    Returns:
        tuple of (processed_png_bytes, preprocessing_metadata)
    Raises:
        ValueError if the image bytes are corrupt or unreadable.
    """
    if not image_bytes or len(image_bytes) == 0:
        raise ValueError("Cannot preprocess empty image bytes.")

    t0 = time.perf_counter()

    # 1. Decode image
    np_buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(np_buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image. File may be corrupted, truncated, or malicious.")

    orig_h, orig_w = img.shape[:2]

    # 2. Grayscale conversion
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. Denoising
    # For large images, Gaussian blur or median blur is fast and effective
    if orig_h * orig_w > 1_500_000:
        denoised = cv2.GaussianBlur(gray, (3, 3), 0)
    else:
        try:
            denoised = cv2.fastNlMeansDenoising(
                gray, None, h=10, templateWindowSize=7, searchWindowSize=21
            )
        except Exception:
            denoised = cv2.GaussianBlur(gray, (3, 3), 0)

    # 4. Contrast enhancement using CLAHE (preserves font edges and anti-aliasing)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # 5. Deskew detection using Otsu binarization (for angle computation only)
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inv_thresh = cv2.bitwise_not(thresh)
    pts = cv2.findNonZero(inv_thresh)
    deskew_angle = 0.0

    output_img = enhanced

    if pts is not None and len(pts) > 100:
        rect = cv2.minAreaRect(pts)
        angle = rect[-1]

        # Normalize angle according to OpenCV conventions
        if angle < -45.0:
            angle = -(90.0 + angle)
        elif angle > 45.0:
            angle = -(angle - 90.0)
        else:
            angle = -angle

        if 0.5 <= abs(angle) <= 45.0:
            deskew_angle = round(angle, 2)
            center = (orig_w // 2, orig_h // 2)
            rot_mat = cv2.getRotationMatrix2D(center, deskew_angle, 1.0)
            output_img = cv2.warpAffine(
                enhanced,
                rot_mat,
                (orig_w, orig_h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=255,
            )

    # 6. Encode to PNG bytes
    success, encoded = cv2.imencode(".png", output_img)
    if not success or encoded is None:
        raise ValueError("Failed to encode preprocessed image to PNG format.")

    duration_ms = round((time.perf_counter() - t0) * 1000, 2)
    meta = {
        "original_width": orig_w,
        "original_height": orig_h,
        "deskew_angle_deg": deskew_angle,
        "preprocess_duration_ms": duration_ms,
    }

    return encoded.tobytes(), meta
