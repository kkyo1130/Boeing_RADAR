"""Artifacts for the existing v2 workflow, not separate operations/decision APIs."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.services import media_v2, receiving_v2
from app.services.reports.v2 import report

router = APIRouter(prefix='/api/v2/flights', tags=['v2 artifacts'])


@router.get('/{flight_id}/report')
def get_report(flight_id: str, db: Session = Depends(get_db)):
    return report(db, flight_id)


@router.get('/{flight_id}/report.json')
def export(flight_id: str, db: Session = Depends(get_db)):
    return JSONResponse(report(db, flight_id), headers={'Content-Disposition': 'attachment; filename="radar-report.json"'})


@router.post('/{flight_id}/media', status_code=201)
async def upload(flight_id: str, request: Request, db: Session = Depends(get_db)):
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > media_v2.MAX_BYTES:
            raise receiving_v2.ReceivingError(413, 'INVALID_PAYLOAD', 'Evidence exceeds 20 MiB')
        chunks.append(chunk)
    return media_v2.upload(db, flight_id, b''.join(chunks), request.headers.get('content-type', '').split(';')[0])


@router.delete('/{flight_id}/media/{evidence_id}')
def delete(flight_id: str, evidence_id: str, db: Session = Depends(get_db)):
    return media_v2.delete(db, flight_id, evidence_id)
