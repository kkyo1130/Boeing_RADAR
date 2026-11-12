"""Explicit camera-crop adapter for a versioned CharacterOCR checkpoint."""
from .mcp_character_ocr import CharacterOCR
from .mcp_preprocessing import prepare_camera_crop


class CharacterRuntime:
    def __init__(self, checkpoint):
        self.model=CharacterOCR(checkpoint)

    def infer(self, image, kind):
        aligned=prepare_camera_crop(image,kind)
        if aligned is None:return dict(value=None,model_score=None,reason='PREPROCESSING_FAILED')
        return {**self.model.infer_aligned(aligned,kind),'source':'character_cnn'}
