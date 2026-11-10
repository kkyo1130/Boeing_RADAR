from PIL import Image
from vision.generate_mcp import render
from vision.mcp_ocr import SLOTS, extract_slots, build_model

def test_extract_eight_slots():
    import random
    image = render(18000, 240, random.Random(4))
    slots = extract_slots(image)
    assert tuple(slots.shape) == (8, 1, 64, 48)
    assert slots.min() >= 0 and slots.max() <= 1

def test_model_output():
    import torch
    model = build_model().eval()
    with torch.inference_mode():
        result = model(torch.zeros(8, 1, 64, 48))
    assert tuple(result.shape) == (8, 10)

def test_slots_are_eight():
    assert len(SLOTS) == 8
