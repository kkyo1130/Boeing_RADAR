import random
import numpy as np
from PIL import Image,ImageDraw
from vision.camera_effects import camera_effects


def test_bloom_is_seeded_and_spreads_bright_strokes():
    image=Image.new('RGB',(120,80),(20,20,20));ImageDraw.Draw(image).rectangle((50,20,60,60),fill=(255,200,100))
    first,metadata=camera_effects(image,random.Random(3));second,other=camera_effects(image,random.Random(3))
    assert np.array_equal(np.asarray(first),np.asarray(second)) and metadata==other
    assert first.size==image.size
    reference,_=camera_effects(Image.new('RGB',image.size,(20,20,20)),random.Random(3))
    assert np.asarray(first)[20:60,47:50,0].mean()>np.asarray(reference)[20:60,47:50,0].mean()
