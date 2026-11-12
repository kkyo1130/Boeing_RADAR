"""Loopback OCR-only service. Run: python -m uvicorn vision.ocr_web:app --port 8765."""
import os
import time
import hashlib
import json
import base64
import io
import threading
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime,timezone
from fastapi import FastAPI,HTTPException,Request
from pydantic import BaseModel,Field
from PIL import Image,UnidentifiedImageError
from .ocr_v3_runtime import OCRv3

@asynccontextmanager
async def lifespan(app):
    import torch
    torch.set_num_threads(4)
    character=os.getenv('RADAR_CHARACTER_CHECKPOINT')
    if character:
        from pathlib import Path
        from .character_runtime import CharacterRuntime
        expected=os.getenv('RADAR_CHARACTER_SHA256')
        if expected and hashlib.sha256(Path(character).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Active character checkpoint hash differs from frozen candidate')
        app.state.ocr=CharacterRuntime(character)
        app.state.vision_engine='character_cnn_glare_v4'
    else:
        app.state.ocr=OCRv3(os.getenv("RADAR_VISION_CHECKPOINTS"))
        app.state.vision_engine='mcp_ocr_v3' 
    app.state.lock=threading.Lock()
    yield
app=FastAPI(title='RADAR OCR v3 local demo',lifespan=lifespan)
class Crops(BaseModel):
    hdg:str=Field(max_length=400000)
    alt:str=Field(max_length=400000)

@app.get('/health')
def health():return {'status':'ready','model':getattr(app.state,'vision_engine','mcp_ocr_v3'),'control_enabled':False}

@contextmanager
def processing_slot(lock):
    if not lock.acquire(blocking=False):
        raise HTTPException(429, 'OCR busy; use a new frame after the current request completes')
    try:
        yield
    finally:
        lock.release()


@app.post('/infer')
def infer(body:Crops,request:Request):
    result={}
    with processing_slot(request.app.state.lock):
        for kind in ('hdg','alt'):
            try:
                blob=base64.b64decode(getattr(body,kind),validate=True)
                with Image.open(io.BytesIO(blob)) as image:
                    if image.width>2048 or image.height>1024 or image.width<8 or image.height<8:
                        raise ValueError('Invalid ROI dimensions')
                    image.load()
                    result[kind]=request.app.state.ocr.infer(image,kind)
            except (ValueError,UnidentifiedImageError,OSError) as exc:
                raise HTTPException(422,'Invalid ROI image') from exc
    return {'observed_at':datetime.now(timezone.utc).isoformat(),**result,
            'note':'Uncalibrated model scores; simulated demo only. No cockpit control.'}


class CameraFrame(BaseModel):
    image: str = Field(max_length=2500000)


@app.post('/infer-frame')
def infer_frame(body: CameraFrame, request: Request):
    request_started = time.time()
    from .auto_windows import locate_windows
    try:
        blob = base64.b64decode(body.image, validate=True)
        with Image.open(io.BytesIO(blob)) as decoded:
            if not (16 <= decoded.width <= 2048 and 16 <= decoded.height <= 1536):
                raise ValueError('Invalid frame dimensions')
            image = decoded.convert('RGB')
    except (ValueError, UnidentifiedImageError, OSError) as exc:
        raise HTTPException(422, 'Invalid camera frame') from exc
    with processing_slot(request.app.state.lock):
        debug_path = os.getenv('RADAR_VISION_DEBUG_FRAME')
        if debug_path:
            from pathlib import Path
            destination = Path(debug_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix('.partial.jpg')
            image.save(temporary, format='JPEG', quality=95)
            digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
            temporary.replace(destination)
            metadata = destination.with_suffix('.json')
            pending = metadata.with_suffix('.partial.json')
            pending.write_text(json.dumps(dict(request_started=request_started, saved_at=time.time(), sha256=digest)))
            pending.replace(metadata)
        rois = locate_windows(image)
        result = {}
        for kind in ('hdg', 'alt'):
            result[kind] = (request.app.state.ocr.infer(image.crop(rois[kind]), kind) if rois else
                            dict(value=None, model_score=None, reason='WINDOWS_NOT_FOUND_OR_AMBIGUOUS'))
            if rois:
                from .text_windows import read_crop
                fallback = read_crop(image.crop(rois[kind]), kind)
                primary = result[kind]
                if fallback and primary.get('value') is None:
                    result[kind] = {**fallback, 'primary_reason': primary.get('reason')}
                elif fallback and primary['value'] != fallback['value']:
                    result[kind] = dict(value=None, model_score=None, reason='OCR_ENGINE_DISAGREEMENT')
    return dict(observed_at=datetime.now(timezone.utc).isoformat(), rois=rois, **result,
                note='Experimental amber MCP localization; no cockpit control.')

from .webcam_collection import router as collection_router
app.include_router(collection_router)
