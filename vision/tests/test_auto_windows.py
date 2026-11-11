import base64
import io
import threading
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from vision.auto_windows import locate_windows
from vision.ocr_web import app


def panel(offset=(0,0), second=False):
    image=Image.new('RGB',(700,350),'#101820');draw=ImageDraw.Draw(image)
    def row(y):
        for x,n in ((30,3),(180,3),(370,5)):
            for i in range(n):
                xx=x+i*22+offset[0];yy=y+offset[1]
                draw.rectangle((xx,yy,xx+13,yy+29), fill=(255,170,60))
    row(70)
    if second: row(230)
    return image


def test_ias_is_not_heading_and_translation_is_detected():
    for offset in ((0,0),(25,40)):
        rois=locate_windows(panel(offset))
        assert rois is not None
        assert 170+offset[0]<rois['hdg'][0]<190+offset[0]
        assert 360+offset[0]<rois['alt'][0]<380+offset[0]


def test_blank_missing_and_ambiguous_do_not_guess():
    assert locate_windows(Image.new('RGB',(700,350))) is None
    assert locate_windows(panel(second=True)) is None
    image=panel();ImageDraw.Draw(image).rectangle((350,0,699,349),fill='black')
    assert locate_windows(image) is None


def test_full_frame_api_detects_and_does_not_reuse_old_values():
    class Fake:
        def infer(self,image,kind):
            return dict(value='000' if kind=='hdg' else '03000',model_score=.8,reason=None)
    app.state.ocr=Fake();app.state.lock=threading.Lock()
    client=TestClient(app)
    def send(image):
        buf=io.BytesIO();image.save(buf,format='PNG')
        return client.post('/infer-frame',json={'image':base64.b64encode(buf.getvalue()).decode()})
    response=send(panel());assert response.status_code==200
    assert response.json()['hdg']['value']=='000'
    assert response.json()['rois']['alt']
    response=send(Image.new('RGB',(700,350)))
    assert response.json()['hdg']['value'] is None
    assert response.json()['alt']['value'] is None
    assert response.json()['rois'] is None
    assert client.post('/infer-frame',json={'image':'bad'}).status_code==422
    assert send(Image.new('RGB',(2049,20))).status_code==422


def test_desaturated_camera_digits_are_localized_without_color_guessing():
    image=panel()
    import numpy as np
    pixels=np.asarray(image).copy()
    selected=(pixels[:,:,0]>200)&(pixels[:,:,1]>100)
    pixels[selected]=(255,245,190)
    rois=locate_windows(Image.fromarray(pixels))
    assert rois is not None
    assert 170<rois['hdg'][0]<190
    assert 360<rois['alt'][0]<380
