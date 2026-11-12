from PIL import Image
import vision.character_runtime as runtime


def test_runtime_passes_only_image_and_kind_and_preserves_leading_zero(monkeypatch):
    image=Image.new('RGB',(80,40));calls=[]
    monkeypatch.setattr(runtime,'prepare_camera_crop',lambda frame,kind: image)
    class Model:
        def infer_aligned(self,frame,kind):
            calls.append((frame,kind));return dict(value='000',model_score=.9,reason=None)
    engine=runtime.CharacterRuntime.__new__(runtime.CharacterRuntime);engine.model=Model()
    result=engine.infer(image,'hdg')
    assert calls==[(image,'hdg')] and result['value']=='000' and result['source']=='character_cnn'


def test_runtime_does_not_call_model_on_missing_preprocessing(monkeypatch):
    monkeypatch.setattr(runtime,'prepare_camera_crop',lambda frame,kind: None)
    engine=runtime.CharacterRuntime.__new__(runtime.CharacterRuntime)
    assert engine.infer(Image.new('RGB',(80,40)),'alt')['value'] is None
