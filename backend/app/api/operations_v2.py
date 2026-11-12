"""Artifacts for the existing v2 workflow, not separate operations/decision APIs."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from app.db import get_db
from app.services import media_v2, receiving_v2
from app.services.reports.v2 import report

router = APIRouter(prefix='/api/v2/flights', tags=['v2 artifacts'])


@router.get('/{flight_id}/report')
def get_report(flight_id: str, request: Request, db: Session = Depends(get_db)):
    from app.services.reports.access import authorize
    authorize(db,flight_id,request)
    return JSONResponse(report(db,flight_id),headers={'Cache-Control':'no-store'})


@router.get('/{flight_id}/report.json')
def export(flight_id: str, request: Request, db: Session = Depends(get_db)):
    from app.services.reports.access import authorize
    authorize(db,flight_id,request)
    return JSONResponse(report(db, flight_id), headers={'Content-Disposition': 'attachment; filename="radar-report.json"','Cache-Control':'no-store'})


@router.get('/{flight_id}/report.pdf')
def export_pdf(flight_id: str, request: Request, db: Session = Depends(get_db)):
    from app.services.reports.access import authorize
    from app.services.reports.pdf import render_pdf
    authorize(db,flight_id,request)
    data=report(db,flight_id)
    if not data['terminal']:
        raise receiving_v2.ReceivingError(409,'INVALID_SEQUENCE','End the flight before downloading a PDF')
    date=data['safety']['ended_at'][:10]
    return Response(render_pdf(data['safety']),media_type='application/pdf',headers={
        'Content-Disposition':f'attachment; filename="Flight_Safety_Report_{date}.pdf"',
        'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


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


@router.post('/{flight_id}/report-access')
def recover_report_access(flight_id: str, payload: dict, request: Request, db: Session = Depends(get_db)):
    import re
    import secrets
    from fastapi import HTTPException
    from app.services.reports.access import COOKIE,digest
    from app.models.operations_v2 import V2ReportOwner
    token=payload.get('token','')
    row=db.get(V2ReportOwner,flight_id)
    if not isinstance(token,str) or not re.fullmatch(r'[0-9a-f]{64}',token) or not row or not secrets.compare_digest(row.owner_hash,digest(token)):
        raise HTTPException(403,'Invalid report access code')
    response=JSONResponse({'status':'AUTHORIZED'},headers={'Cache-Control':'no-store'})
    response.set_cookie(COOKIE,token,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=31536000,path='/')
    return response
