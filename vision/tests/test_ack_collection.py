import hashlib,json,time
from vision.collect_ack_frames import fresh_frame


def test_fresh_frame_rejects_old_or_inconsistent_pixels(tmp_path):
    image=tmp_path/'latest.jpg';meta=tmp_path/'latest.json';raw=b'test-frame';image.write_bytes(raw);now=time.time()
    data=dict(request_started=now,sha256=hashlib.sha256(raw).hexdigest());meta.write_text(json.dumps(data))
    assert fresh_frame(image,meta,now-1)[0]==raw
    assert fresh_frame(image,meta,now+1) is None
    data['request_started']=now-10;meta.write_text(json.dumps(data));assert fresh_frame(image,meta,now-20) is None
    data['request_started']=now;meta.write_text(json.dumps(data));image.write_bytes(b'other-frame');assert fresh_frame(image,meta,now-1) is None
