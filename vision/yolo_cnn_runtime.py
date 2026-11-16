"""Shared image-only YOLO MCP localization and trained CNN OCR. No OS OCR."""
from functools import lru_cache
from pathlib import Path
from threading import RLock
import hashlib
import json
import os
import time
import numpy as np
import cv2
from .mcp_yolo_gate import PanelGate,detect_panel_readouts,validate_detector
from .mcp_window_readouts import detect_mcp_readouts
from .character_runtime import CharacterRuntime


def model_configuration():
    root=Path(__file__).resolve().parents[1]
    metadata=root/'.demo/active-vision.json'
    active=json.loads(metadata.read_text()) if metadata.is_file() else {}
    defaults={
        'yolo': (root.parent/'Boeing_RADAR-vision/vision/checkpoints/mcp_yolo_blind_v2/fit/weights/best.pt', 'RADAR_YOLO_WEIGHTS', 'RADAR_YOLO_SHA256', 'yolo_checkpoint', 'yolo_sha256'),
        'cnn': (root/'vision/checkpoints/glare_character_frozen_20261112/character_best.pt', 'RADAR_CHARACTER_CHECKPOINT', 'RADAR_CHARACTER_SHA256', 'checkpoint', 'sha256'),
    }
    result={}
    for kind,(fallback,path_env,hash_env,path_key,hash_key) in defaults.items():
        explicit=os.getenv(path_env)
        path=Path(explicit or active.get(path_key) or fallback)
        if not path.is_absolute():path=(Path.cwd() if explicit else root)/path
        digest=os.getenv(hash_env) or (active.get(hash_key) if not os.getenv(path_env) else None)
        result[kind]=(path,digest)
    return result


def model_paths():
    configuration=model_configuration()
    return configuration['yolo'][0],configuration['cnn'][0]


class YoloCnnRuntime:
    def __init__(self,yolo_path,cnn_path,yolo_sha256=None,cnn_sha256=None):
        for path in (yolo_path,cnn_path):
            if not Path(path).is_file():raise FileNotFoundError(f'Required trained checkpoint missing: {Path(path).name}')
        os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parents[1]/'.demo/ultralytics'))
        from ultralytics import YOLO
        import torch
        torch.set_num_threads(4)
        self.detector=YOLO(str(yolo_path));validate_detector(self.detector)
        self.ocr=CharacterRuntime(cnn_path);self.lock=RLock()
        self.yolo_sha256=hashlib.sha256(Path(yolo_path).read_bytes()).hexdigest()
        self.cnn_sha256=hashlib.sha256(Path(cnn_path).read_bytes()).hexdigest()
        for name,actual,expected in [('RADAR_YOLO_SHA256',self.yolo_sha256,yolo_sha256),('RADAR_CHARACTER_SHA256',self.cnn_sha256,cnn_sha256)]:
            expected=os.getenv(name) or expected
            if expected and expected!=actual:raise ValueError(f'{name} checkpoint hash mismatch')
        # Warm both detector input sizes before the HTTP service accepts frames.
        # This prevents first-request initialization from exceeding freshness limits.
        for size in (960,640):
            self.detector.predict(np.zeros((720,1280,3),dtype=np.uint8),conf=.1,verbose=False,imgsz=size,device='cpu')

    def locate(self,image):
        frame=cv2.cvtColor(np.asarray(image.convert('RGB')),cv2.COLOR_RGB2BGR)
        # Spatial checks use the existing .5 score/ambiguity/edge policy. The
        # producer owns fresh-frame geometry resets and 3-value confirmation.
        found_panel=None;reason='LOW_OR_MISSING_PANEL_SCORE'
        with self.lock:
            for size in (960,640):
                gate=PanelGate(stable_frames=1)
                boxes,reason=detect_panel_readouts(self.detector,frame,gate,detect_mcp_readouts,device='cpu',imgsz=size)
                if reason == 'AMBIGUOUS_PANELS' or (reason and reason.startswith('DETECTOR_ERROR')):
                    return dict(rois=None,panel=None,reason=reason,detector_imgsz=size)
                if gate.previous:found_panel=list(gate.previous)
                if boxes:
                    rois={kind:[x,y,x+w,y+h] for kind,(x,y,w,h) in boxes.items()}
                    return dict(rois=rois,panel=found_panel,reason=None,detector_imgsz=size)
        return dict(rois=None,panel=found_panel,reason=reason,detector_imgsz=None)

    def read(self,image,rois):
        result={}
        with self.lock:
            for kind in ('hdg','alt'):
                box=rois.get(kind)
                if not box or not (0<=box[0]<box[2]<=image.width and 0<=box[1]<box[3]<=image.height):
                    result[kind]=dict(value=None,model_score=None,reason='READOUT_OUTSIDE_FRAME',source='character_cnn')
                else:result[kind]=self.ocr.infer(image.crop(box),kind)
        return result

    def infer(self,image):
        started=time.monotonic();located=self.locate(image)
        result=(self.read(image,located['rois']) if located['rois'] else
                {kind:dict(value=None,model_score=None,reason=located['reason'] or 'READOUTS_MISSING_OR_AMBIGUOUS',source='character_cnn') for kind in ('hdg','alt')})
        return dict(**located,**result,pipeline='yolo11n_character_cnn',apple_vision_enabled=False,
                    elapsed_ms=round((time.monotonic()-started)*1000))


@lru_cache(maxsize=2)
def _runtime(yolo,cnn,yolo_sha256,cnn_sha256):return YoloCnnRuntime(yolo,cnn,yolo_sha256,cnn_sha256)

def get_runtime():
    configuration=model_configuration()
    return _runtime(str(configuration['yolo'][0].resolve()),str(configuration['cnn'][0].resolve()),configuration['yolo'][1],configuration['cnn'][1])

def locate_windows(image):return get_runtime().locate(image)['rois']

def read_fields(image,rois):
    readings=get_runtime().read(image,{'hdg':rois['HDG'],'alt':rois['ALT']})
    return {'fields':{name:dict(value=int(item['value']) if item.get('value') is not None else None,
        model_score=item.get('model_score'),reason=item.get('reason'),raw_text=item.get('raw_value',item.get('value')),source='character_cnn')
        for name,item in [('heading',readings['hdg']),('altitude',readings['alt'])]}}
