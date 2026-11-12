"""Failure and validity regressions without loading private checkpoints."""
import base64
import io
import threading
from unittest.mock import patch
import torch
from PIL import Image
from fastapi.testclient import TestClient
from vision.ocr_v3_runtime import OCRv3
from vision.ocr_web import app

def encode(image):
    buf=io.BytesIO();image.save(buf,format='PNG')
    return base64.b64encode(buf.getvalue()).decode()

def test_blank_is_missing_not_zero():
    runtime=OCRv3.__new__(OCRv3);runtime.models={}
    result=runtime.infer(Image.new('RGB',(108,48)), 'hdg')
    assert result=={'value':None,'model_score':None,'reason':'NO_AMBER_DIGITS'}

def test_heading_range_and_zero():
    runtime=OCRv3.__new__(OCRv3)
    def output(digit):
        x=torch.zeros(1,3,10);x[:,:,digit]=10;return x
    image=Image.new('RGB',(108,48))
    with patch('vision.ocr_v3_runtime.align',return_value=image):
        runtime.models={'hdg':lambda x:output(9)}
        assert runtime.infer(image,'hdg')['reason']=='OUT_OF_RANGE'
        runtime.models={'hdg':lambda x:output(0)}
        assert runtime.infer(image,'hdg')['value']=='000'

def test_invalid_images_rejected_and_fields_independent():
    class Fake:
        def infer(self,image,kind):
            return {'value':'000' if kind=='hdg' else None,'model_score':None,'reason':None}
    app.state.ocr=Fake();app.state.lock=threading.Lock()
    client=TestClient(app)
    assert client.post('/infer',json={'hdg':'bad','alt':'bad'}).status_code==422
    blob=encode(Image.new('RGB',(108,48)))
    response=client.post('/infer',json={'hdg':blob,'alt':blob})
    assert response.status_code==200
    assert response.json()['hdg']['value']=='000'
    assert response.json()['alt']['value'] is None
    assert response.json()['observed_at'].endswith('+00:00')


def test_uncertain_model_output_is_not_a_stable_numeric_candidate():
    runtime=OCRv3.__new__(OCRv3)
    runtime.models={'alt':lambda x:torch.zeros(1,5,10)}
    with patch('vision.ocr_v3_runtime.align',return_value=Image.new('RGB',(180,48))):
        result=runtime.infer(Image.new('RGB',(180,48)),'alt')
    assert result['value'] is None
    assert result['reason']=='LOW_MODEL_SCORE'
