"""Opt-in local demonstration bridge. No remote models or device control."""
import base64
import os
from pathlib import Path
from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas.observation_v2 import UtcTimestamp
from app.services.demo import adapters as demo


def enabled():
    if os.getenv('RADAR_DEMO_ENABLED') != '1': demo.error('Demo adapter is disabled',404)

router=APIRouter(prefix='/api/demo',dependencies=[Depends(enabled)],tags=['local demo'])

class Model(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Calibration(Model):
    image:str=Field(max_length=6000000)
    rois:dict[str,tuple[int,int,int,int]]

class Frame(Model):
    image:str=Field(max_length=6000000)
    token:str=Field(max_length=128)
    captured_at:UtcTimestamp
    target_revision:int=Field(ge=0)

class Speech(Model):
    audio:str=Field(max_length=8000000)
    started_at:UtcTimestamp
    ended_at:UtcTimestamp
    atc_input_id:str=Field(max_length=128)

class Scenario(Model):
    started_at:UtcTimestamp
    ended_at:UtcTimestamp

@router.get('/status')
def status():
    return dict(ner_enabled=bool(os.getenv('RADAR_NER_MODEL') or os.getenv('RADAR_NER_BACKEND')),
                ner_backend=os.getenv('RADAR_NER_BACKEND', 'v7'),
                ner_model_present=Path(os.getenv('RADAR_NER_MODEL','/nonexistent'),'model.safetensors').is_file(),
                speech_ready=Path(os.getenv('RADAR_WHISPER_MODEL','/nonexistent'),'model.bin').is_file(),
                camera_ready=Path(os.getenv('RADAR_OCR_BINARY','/nonexistent')).is_file(),
                scenarios=demo.SCENARIOS)

@router.get('/scenarios/{scenario}/audio')
def audio(scenario:str):
    if scenario not in demo.SCENARIOS: demo.error('Unknown scenario')
    path=Path(os.environ['RADAR_DEMO_AUDIO'])/(scenario+'.wav')
    if not path.is_file(): demo.error('Run demo setup to generate scenario audio',503)
    return FileResponse(path,media_type='audio/wav')

@router.post('/{flight}/calibration')
def calibrate(flight:str,body:Calibration,db:Session=Depends(get_db)):
    demo.profile(db,flight)
    if set(body.rois)!= {'ALT','HDG'}: demo.error('Select both ALT and HDG')
    return demo.calibrate(flight,body.image,body.rois)

@router.post('/{flight}/frame')
def frame(flight:str,body:Frame,db:Session=Depends(get_db)):
    return demo.camera(db,flight,body.model_dump())

@router.post('/{flight}/readback')
def readback(flight:str,body:Speech,db:Session=Depends(get_db)):
    try: data=base64.b64decode(body.audio,validate=True)
    except ValueError: demo.error('Invalid WAV encoding')
    return demo.receive_speech(db,flight,body.model_dump(),data)

@router.post('/{flight}/scenario/{scenario}')
def scenario(flight:str,scenario:str,body:Scenario,db:Session=Depends(get_db)):
    if scenario not in demo.SCENARIOS: demo.error('Unknown scenario')
    data=(Path(os.environ['RADAR_DEMO_AUDIO'])/(scenario+'.wav')).read_bytes()
    return demo.receive_speech(db,flight,body.model_dump(),data,scenario=scenario)


class Transcript(Model):
    text: str = Field(min_length=1, max_length=2048)


@router.post('/speech/extract')
def extract_transcript(body: Transcript):
    """Diagnostics only: NER spans do not create targets or change Cockpit state."""
    from app.services.speech.ner import extract_atc, ExtractionError
    try:
        return extract_atc(body.text)
    except ExtractionError as exc:
        code = str(exc)
        demo.error(code, 422 if code in {'EMPTY_TRANSCRIPT', 'TRANSCRIPT_TOO_LONG', 'NER_TOKEN_LIMIT'} else 503)
    except Exception:
        demo.error('NER_MODEL_UNAVAILABLE', 503)
