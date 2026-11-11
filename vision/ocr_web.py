"""Loopback OCR-only service. Run: python -m uvicorn vision.ocr_web:app --port 8765."""
import base64
import io
import threading
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from fastapi import FastAPI,HTTPException,Request
from pydantic import BaseModel,Field
from PIL import Image,UnidentifiedImageError
from .ocr_v3_runtime import OCRv3

@asynccontextmanager
async def lifespan(app):
    import torch
    torch.set_num_threads(4)
    app.state.ocr=OCRv3()
    app.state.lock=threading.Lock()
    yield
app=FastAPI(title='RADAR OCR v3 local demo',lifespan=lifespan)
class Crops(BaseModel):
    hdg:str=Field(max_length=400000)
    alt:str=Field(max_length=400000)

@app.get('/health')
def health():return {'status':'ready','model':'mcp_ocr_v3','control_enabled':False}

@app.post('/infer')
def infer(body:Crops,request:Request):
    result={}
    with request.app.state.lock:
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
    from .auto_windows import locate_windows
    try:
        blob = base64.b64decode(body.image, validate=True)
        with Image.open(io.BytesIO(blob)) as decoded:
            if not (16 <= decoded.width <= 2048 and 16 <= decoded.height <= 1536):
                raise ValueError('Invalid frame dimensions')
            image = decoded.convert('RGB')
    except (ValueError, UnidentifiedImageError, OSError) as exc:
        raise HTTPException(422, 'Invalid camera frame') from exc
    with request.app.state.lock:
        rois = locate_windows(image)
        result = {}
        for kind in ('hdg', 'alt'):
            result[kind] = (request.app.state.ocr.infer(image.crop(rois[kind]), kind) if rois else
                            dict(value=None, model_score=None, reason='WINDOWS_NOT_FOUND_OR_AMBIGUOUS'))
    return dict(observed_at=datetime.now(timezone.utc).isoformat(), rois=rois, **result,
                note='Experimental amber MCP localization; no cockpit control.')

from .webcam_collection import router as collection_router
app.include_router(collection_router)
