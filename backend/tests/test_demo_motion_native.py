"""Opt-in YOLO + CNN motion check; local images are not a live webcam test."""
import base64
import io
import json
import os
from pathlib import Path
import pytest
from PIL import Image
from app.services import receiving_v2 as intake
from test_demo import flight

REQUIRED=('RADAR_MOTION_PILOT_FRAME','RADAR_MOTION_MCP_FRAME','RADAR_YOLO_WEIGHTS','RADAR_CHARACTER_CHECKPOINT')

@pytest.mark.skipif(not all(os.getenv(key) and Path(os.environ[key]).is_file() for key in REQUIRED),reason='Provide two local frames and trained YOLO/CNN checkpoints')
def test_image_motion_with_yolo_cnn_and_real_intake(client,flight,monkeypatch,tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    def encoded(path):
        with Image.open(path) as image:
            buffer=io.BytesIO();image.convert('RGB').save(buffer,format='JPEG',quality=92)
        return base64.b64encode(buffer.getvalue()).decode()
    pilot=encoded(os.environ['RADAR_MOTION_PILOT_FRAME']);zoom=encoded(os.environ['RADAR_MOTION_MCP_FRAME'])
    buffer=io.BytesIO();Image.new('RGB',(1342,760),'black').save(buffer,format='JPEG');blank=base64.b64encode(buffer.getvalue()).decode()
    response=client.post(f'/api/demo/{flight}/auto-calibration',json={'image':pilot})
    assert response.status_code==200,response.text
    assert response.json()['status']=='READY',response.text
    token=response.json()['token'];sequence=0;results=[]
    for stage,image in [('pilot',pilot),('zoom',zoom),('lost',blank),('return',pilot)]:
        for index in range(3):
            sequence+=1
            response=client.post(f'/api/demo/{flight}/frame',json={'token':token,'target_revision':0,'image':image,'media_time':float(sequence),'captured_at':intake.stamp(intake.utc_now())})
            assert response.status_code==200,response.text
            data=response.json();results.append({'stage':stage,'index':index,'rois':data['rois'],'fields':data['fields'],'tracking_status':data['tracking_status']})
            if stage=='lost':
                assert data['rois'] is None and all(field['value'] is None for field in data['fields'].values())
            else:
                assert data['fields']['heading']['value']==(int(os.getenv('RADAR_MOTION_EXPECTED_HDG','123')) if index==2 else None),data
                assert data['fields']['altitude']['value']==(int(os.getenv('RADAR_MOTION_EXPECTED_ALT','15000')) if index==2 else None),data
    assert results[0]['rois']!=results[3]['rois']
    (tmp_path/'yolo_cnn_camera_motion.json').write_text(json.dumps(results,indent=2))
