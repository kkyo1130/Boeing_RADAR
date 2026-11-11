"""Convert photographed white/cream MCP digits to the amber domain of OCR v3.

Only intended for an already detected readout ROI. Never treats OCR predictions
as ground truth; inspect real-camera results separately.
"""
import cv2
import numpy as np
from PIL import Image


def camera_to_amber(image):
    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    value = hsv[:, :, 2]
    saturation = hsv[:, :, 1]
    # White/cream pixels on dark display glass, not a generic global threshold.
    # Brightness is measured relative to the dark part of this individual ROI.
    floor = float(np.percentile(value, 30))
    threshold = int(np.clip(max(115, floor + 65), 115, 240))
    mask = ((value >= threshold) & (saturation <= 160)).astype(np.uint8)*255
    # Remove tiny isolated reflections but preserve narrow strokes of digit 1.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    cleaned = np.zeros_like(mask)
    minimum = max(2, round(mask.size * .0008))
    for i in range(1, count):
        if stats[i, cv2.CC_STAT_AREA] >= minimum:
            cleaned[labels == i] = 255
    # Preserve stroke antialiasing with the original luminance.
    alpha = cleaned.astype(np.float32)/255.
    intensity = np.maximum(0, (value.astype(np.float32)-floor)/max(1, 255-floor))
    alpha *= np.clip(intensity * 1.4, .55, 1.)
    bg = np.array([12, 14, 16], dtype=np.float32)
    amber = np.array([255, 175, 55], dtype=np.float32)
    out = bg[None,None,:]*(1-alpha[:,:,None]) + amber[None,None,:]*alpha[:,:,None]
    return Image.fromarray(out.astype(np.uint8), "RGB")
