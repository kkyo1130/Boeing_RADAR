from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db import get_db
from app.schemas.flight import FlightResponse
from app.schemas.clearance import ClearanceResponse
from app.schemas.observation import ObservationInput
from app.schemas.safety_event import SafetyEventResponse
from app.models.clearance import Clearance
from app.services import flight_service, clearance_service, safety_trace_service

router = APIRouter(prefix="/api/flights", tags=["flights"])

@router.post("/start", response_model=FlightResponse, status_code=201, summary='비행 세션 시작', description='새 Flight Session을 ACTIVE 상태로 생성하고 FLIGHT_STARTED 이벤트를 저장합니다. flight_id는 FLT-YYYYMMDD-NNN 형식으로 자동 발급하며 번호는 전체 DB에서 증가합니다. 시간은 UTC ISO 8601입니다.', responses={})
def start(db: Session = Depends(get_db)):
    return flight_service.start(db)

@router.post("/{flight_id}/end", response_model=FlightResponse, summary='비행 세션 종료', description='ACTIVE 비행의 ended_at을 저장하고 상태를 ENDED로 변경합니다. FLIGHT_ENDED 이벤트를 기록합니다. 종료 이후 지시 생성 및 Observation 변경은 거부됩니다. 중복 종료는 409입니다.', responses={404: {'description': '해당 ID의 비행 또는 관제 지시가 존재하지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Resource not found'}}}}, 409: {'description': '비행이 종료되었거나 입력 순서, 중복 입력, 재검증 대상 상태가 올바르지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Flight has ended'}}}}})
def end(flight_id: str, db: Session = Depends(get_db)):
    return flight_service.end(db, flight_id)

@router.get("/{flight_id}", response_model=FlightResponse, summary='비행 세션 조회', description='flight_id에 해당하는 시작 시각, 종료 시각, ACTIVE 또는 ENDED 상태를 반환합니다. 종료 전 ended_at은 null입니다.', responses={404: {'description': '해당 ID의 비행 또는 관제 지시가 존재하지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Resource not found'}}}}})
def get(flight_id: str, db: Session = Depends(get_db)):
    return flight_service.get_flight(db, flight_id)

@router.post("/{flight_id}/clearances", response_model=ClearanceResponse, status_code=201, summary='ATC 지시 생성', description='ACTIVE 비행에 ATC Observation을 입력하여 새 Clearance를 생성합니다. clearance_id는 CLR-NNN 형식이며 각 지시마다 별도로 발급합니다. 초기 상태는 WAITING_READBACK이며 ATC_RECOGNIZED 이벤트를 저장합니다. source는 서버가 ATC로 지정합니다.', responses={404: {'description': '해당 ID의 비행 또는 관제 지시가 존재하지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Resource not found'}}}}, 409: {'description': '비행이 종료되었거나 입력 순서, 중복 입력, 재검증 대상 상태가 올바르지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Flight has ended'}}}}})
def create(flight_id: str, payload: ObservationInput, db: Session = Depends(get_db)):
    return clearance_service.create(db, flight_id, payload)

@router.get("/{flight_id}/clearances", response_model=list[ClearanceResponse], summary='비행의 관제 지시 목록 조회', description='해당 비행의 모든 Clearance를 생성 순서로 반환합니다. 각 항목에는 최신 ATC, Readback, Cockpit Observation과 현재 상태 및 필드별 errors가 포함됩니다. 지시가 없으면 빈 배열을 반환합니다.', responses={404: {'description': '해당 ID의 비행 또는 관제 지시가 존재하지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Resource not found'}}}}})
def clearances(flight_id: str, db: Session = Depends(get_db)):
    flight_service.get_flight(db, flight_id)
    return db.scalars(select(Clearance).where(Clearance.flight_id == flight_id).order_by(Clearance.id)).all()

@router.get("/{flight_id}/safety-trace", response_model=list[SafetyEventResponse], summary='Safety Trace 이벤트 이력 조회', description='최종 결과뿐 아니라 인식, 오류, 경보, 수정, 재검증, 비행 시작·종료 이벤트를 모두 반환합니다. 서버 기록 timestamp 오름차순으로 정렬하며 같은 시각이면 id 순으로 반환합니다. field는 ALT 또는 HDG이며 일반 이벤트에서는 null입니다. observation은 입력 당시 스냅샷으로 수정 전 값도 보존합니다.', responses={404: {'description': '해당 ID의 비행 또는 관제 지시가 존재하지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Resource not found'}}}}})
def trace(flight_id: str, db: Session = Depends(get_db)):
    flight_service.get_flight(db, flight_id)
    return safety_trace_service.trace(db, flight_id)
