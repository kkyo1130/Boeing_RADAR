"""Shared camera ROI -> aligned RGB -> CNN grayscale contract.
Saved aligned crops must never run camera normalization/alignment a second time.
"""
from PIL import Image, ImageOps

def prepare_camera_crop(image, kind):
    try:
        from .camera_digit_preprocess import camera_to_amber
        from .preprocess_mcp_ocr import align
    except ImportError:
        from camera_digit_preprocess import camera_to_amber
        from preprocess_mcp_ocr import align
    return align(camera_to_amber(image),kind)

def normalize_aligned(image, kind):
    if kind not in ('hdg','alt'):
        raise ValueError('Unknown readout kind')
    return ImageOps.exif_transpose(image).convert('L').resize(
        (36*(3 if kind=='hdg' else 5),48),Image.Resampling.BILINEAR)
