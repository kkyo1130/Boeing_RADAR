import base64
import io
import json
from unittest.mock import Mock
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from vision.ocr_web import app
from vision import webcam_collection as collection

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(collection,'ROOT',tmp_path/'captures')
    monkeypatch.setattr(collection,'DRAFTS',{})
    monkeypatch.setattr(collection,'locate_windows',lambda image:{'hdg':[10,10,40,30],'alt':[50,10,90,30]})
    app.state.ocr=Mock(side_effect=AssertionError('Collection must not infer labels'))
    return TestClient(app)

def capture(client,session='a'*32):
    buf=io.BytesIO();Image.new('RGB',(100,50),'orange').save(buf,format='JPEG')
    response=client.post('/dataset/preview',json={'image':base64.b64encode(buf.getvalue()).decode(),'session_id':session})
    assert response.status_code==200,response.text
    return response.json()

def test_only_verified_save_writes_frozen_frame_crops_and_labels(client):
    preview=capture(client)
    assert not collection.ROOT.exists()
    assert set(preview['crops'])=={'hdg','alt'}
    assert 'hdg' not in {key:val for key,val in preview.items() if key!='crops'}
    body={'token':preview['token'],'hdg':'000','alt':'03000','confirmed':True}
    response=client.post('/dataset/save',json=body)
    assert response.status_code==200,response.text
    assert response.json()['training_started'] is False
    assert response.json()['session_samples']==1
    directory=collection.ROOT/('a'*32)/preview['token']
    metadata=json.loads((directory/'label.json').read_text())
    assert metadata['labels']=={'hdg':'000','alt':'03000'}
    assert metadata['label_source']=='human_verified'
    assert metadata['split']=='unassigned'
    assert Image.open(directory/'frame.jpg').size==(100,50)
    assert Image.open(directory/'hdg.jpg').size==(30,20)
    assert Image.open(directory/'alt.jpg').size==(40,20)
    assert client.post('/dataset/save',json=body).json()==response.json()
    assert len(list(collection.ROOT.glob('*/*/label.json')))==1
    assert client.post('/dataset/save',json={**body,'hdg':'001'}).status_code==409

def test_invalid_labels_and_confirmation_never_write(client):
    preview=capture(client)
    body={'token':preview['token'],'hdg':'270','alt':'03000','confirmed':True}
    for patch in ({'hdg':'360'},{'hdg':'27'},{'hdg':'２７０'},{'alt':'3000'},{'alt':'abcde'},{'confirmed':False},{'hdg':270}):
        assert client.post('/dataset/save',json={**body,**patch}).status_code==422
    assert not collection.ROOT.exists()

def test_cancel_expiry_invalid_frame_and_session_paths(client,monkeypatch):
    token=capture(client)['token']
    client.delete('/dataset/preview/'+token).raise_for_status()
    body={'token':token,'hdg':'270','alt':'03000','confirmed':True}
    assert client.post('/dataset/save',json=body).status_code==410
    token=capture(client)['token'];collection.DRAFTS[token]['created']-=601
    assert client.post('/dataset/save',json={**body,'token':token}).status_code==410
    assert client.post('/dataset/preview',json={'image':'bad','session_id':'../bad'}).status_code==422
    assert client.post('/dataset/preview',json={'image':'bad','session_id':'a'*32}).status_code==422
    monkeypatch.setattr(collection,'locate_windows',lambda image:None)
    buf=io.BytesIO();Image.new('RGB',(100,50)).save(buf,format='PNG')
    assert client.post('/dataset/preview',json={'image':base64.b64encode(buf.getvalue()).decode(),'session_id':'a'*32}).status_code==409
    assert not collection.ROOT.exists()

def test_failed_save_can_retry_and_sessions_are_separate(client,monkeypatch):
    token=capture(client)['token']
    body={'token':token,'hdg':'270','alt':'03000','confirmed':True}
    original=collection.os.rename
    monkeypatch.setattr(collection.os,'rename',Mock(side_effect=OSError('disk full')))
    assert client.post('/dataset/save',json=body).status_code==503
    assert not list(collection.ROOT.glob('**/label.json'))
    monkeypatch.setattr(collection.os,'rename',original)
    assert client.post('/dataset/save',json=body).status_code==200
    token2=capture(client,session='b'*32)['token']
    second=client.post('/dataset/save',json={**body,'token':token2})
    assert second.status_code==200 and second.json()['session_samples']==1
