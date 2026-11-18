"""Explicit human-labelled webcam captures, separate from inference/training."""
import base64
import hashlib
import io
import json
import os
import shutil
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError
from .auto_windows import locate_windows

router = APIRouter(prefix='/dataset', tags=['human-labelled captures'])
ROOT = Path(__file__).parent/'data/webcam_labeled'
LOCK = threading.Lock()
DRAFTS = {}
TTL = 600

class Capture(BaseModel):
    image: str = Field(max_length=2500000)
    session_id: str = Field(pattern=r'^[a-f0-9]{32}$')

class Label(BaseModel):
    token: str = Field(pattern=r'^[a-f0-9]{32}$')
    hdg: str = Field(pattern=r'^[0-9]{3}$', strict=True)
    alt: str = Field(pattern=r'^[0-9]{5}$', strict=True)
    confirmed: Literal[True]


def encoded(image):
    buf = io.BytesIO()
    image.save(buf, format='JPEG', quality=95)
    return base64.b64encode(buf.getvalue()).decode()

@router.post('/preview')
def preview(body: Capture):
    try:
        raw = base64.b64decode(body.image, validate=True)
        with Image.open(io.BytesIO(raw)) as original:
            if not (16 <= original.width <= 2048 and 16 <= original.height <= 1536):
                raise ValueError('frame dimensions')
            image = original.convert('RGB')
    except (ValueError, OSError, UnidentifiedImageError) as exc:
        raise HTTPException(422, '카메라 이미지를 확인하세요.') from exc
    rois = locate_windows(image)
    if rois is None:
        raise HTTPException(409, 'HDG·ALT 위치를 찾지 못했습니다. 반사·초점을 확인한 뒤 다시 캡처하세요.')
    crops = {kind: encoded(image.crop(rois[kind])) for kind in ('hdg', 'alt')}
    now = time.monotonic()
    token = uuid4().hex
    with LOCK:
        for key in list(DRAFTS):
            if now-DRAFTS[key]['created'] > TTL:
                del DRAFTS[key]
        if len(DRAFTS) >= 32:
            raise HTTPException(409, '확인 중인 캡처가 많습니다. 취소하거나 잠시 후 다시 시도하세요.')
        DRAFTS[token] = dict(created=now, raw=raw, rois=rois, crops=crops,
                             session_id=body.session_id, observed_at=datetime.now(timezone.utc).isoformat(),
                             receipt=None, labels=None)
    return dict(token=token, rois=rois, crops=crops, expires_in_seconds=TTL)

@router.delete('/preview/{token}')
def discard(token: str):
    with LOCK:
        DRAFTS.pop(token, None)
    return dict(discarded=True)

@router.post('/save')
def save(body: Label):
    if int(body.hdg) > 359:
        raise HTTPException(422, 'HDG 정답은 000~359 범위여야 합니다.')
    with LOCK:
        item = DRAFTS.get(body.token)
        if item is None or time.monotonic()-item['created'] > TTL:
            raise HTTPException(410, '캡처가 만료되었습니다. 새로 캡처하세요.')
        labels = dict(hdg=body.hdg, alt=body.alt)
        if item['receipt']:
            if item['labels'] != labels:
                raise HTTPException(409, '이미 다른 정답으로 저장된 캡처입니다. 새로 캡처하세요.')
            return item['receipt']
        session = ROOT/item['session_id']
        temporary = None
        try:
            session.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix='.capture-', dir=session))
            with Image.open(io.BytesIO(item['raw'])) as image:
                image.convert('RGB').save(temporary/'frame.jpg', quality=95)
            for kind in ('hdg', 'alt'):
                (temporary/f'{kind}.jpg').write_bytes(base64.b64decode(item['crops'][kind]))
            metadata = dict(schema_version='webcam-label/1', session_id=item['session_id'],
                            sample_id=body.token, observed_at=item['observed_at'],
                            labelled_at=datetime.now(timezone.utc).isoformat(),
                            time_basis='SERVER_RECEIVE', source='webcam',
                            label_source='human_verified', confirmed=True,
                            rois=item['rois'], labels=labels, split='unassigned',
                            frame_sha256=hashlib.sha256((temporary/'frame.jpg').read_bytes()).hexdigest(),
                            source_frame_sha256=hashlib.sha256(item['raw']).hexdigest())
            (temporary/'label.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
            os.rename(temporary, session/body.token)
        except OSError as exc:
            if temporary and temporary.exists():
                shutil.rmtree(temporary)
            raise HTTPException(503, '저장하지 못했습니다. 저장 공간과 쓰기 권한을 확인한 뒤 다시 저장하세요.') from exc
        item['labels'] = labels
        item['receipt'] = dict(saved=True, sample_id=body.token, session_id=item['session_id'],
                               session_samples=sum(1 for path in session.glob('*/label.json')),
                               directory='vision/data/webcam_labeled', training_started=False)
        return item['receipt']
