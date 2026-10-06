from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.core.enums import Source
from app.schemas.clearance import ClearanceResponse
from app.schemas.observation import ObservationInput
from app.services.clearance_service import get_clearance, submit

router = APIRouter(prefix="/api/clearances", tags=["clearances"])

@router.get("/{clearance_id}", response_model=ClearanceResponse, summary='관제 지시 상세 조회', description='clearance_id에 연결된 최신 ATC, Readback, Cockpit, status, errors를 반환합니다. 아직 입력하지 않은 Observation은 null이며 errors는 field, expected, actual로 구성됩니다.', responses={404: {'description': '해당 ID의 비행 또는 관제 지시가 존재하지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Resource not found'}}}}})
def get(clearance_id: str, db: Session = Depends(get_db)):
    return get_clearance(db, clearance_id)

@router.post("/{clearance_id}/readback", response_model=ClearanceResponse, summary='Readback 최초 입력 및 비교', description='복명복창 Observation을 최초 입력하고 READBACK_RECOGNIZED 이벤트를 저장합니다. ATC와 ALT/HDG를 정확 일치 비교하여 불일치하면 READBACK_ERROR와 필드별 오류 및 ALERTED 이벤트를 기록합니다. 일치하면 WAITING_COCKPIT입니다. 이미 입력한 Readback은 오류 상태에서 reverify API로 수정합니다. source는 READBACK입니다.', responses={404: {'description': '해당 ID의 비행 또는 관제 지시가 존재하지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Resource not found'}}}}, 409: {'description': '비행이 종료되었거나 입력 순서, 중복 입력, 재검증 대상 상태가 올바르지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Flight has ended'}}}}})
def readback(clearance_id: str, payload: ObservationInput, db: Session = Depends(get_db)):
    return submit(db, clearance_id, payload, Source.READBACK)

@router.post("/{clearance_id}/cockpit", response_model=ClearanceResponse, summary='Cockpit 최초 입력 및 비교', description='Readback 입력 후 Cockpit 설정값을 최초 입력하고 COCKPIT_RECOGNIZED 이벤트를 저장합니다. ATC ↔ Readback 비교를 먼저 수행하며 복명복창이 틀리면 READBACK_ERROR가 우선입니다. 복명복창이 정상이고 Cockpit이 다르면 SETTING_ERROR와 ALERTED, 모두 일치하면 VERIFIED 이벤트를 기록합니다. source는 COCKPIT입니다.', responses={404: {'description': '해당 ID의 비행 또는 관제 지시가 존재하지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Resource not found'}}}}, 409: {'description': '비행이 종료되었거나 입력 순서, 중복 입력, 재검증 대상 상태가 올바르지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Flight has ended'}}}}})
def cockpit(clearance_id: str, payload: ObservationInput, db: Session = Depends(get_db)):
    return submit(db, clearance_id, payload, Source.COCKPIT)

@router.post("/{clearance_id}/readback/reverify", response_model=ClearanceResponse, summary='Readback 오류 수정 및 재검증', description='READBACK_ERROR 상태에서만 호출할 수 있습니다. REVERIFYING 이벤트를 기록하고 수정 Observation 및 READBACK_UPDATED 이력을 저장한 후 재비교합니다. 복명복창 오류가 해소되면 Cockpit 미입력 상태에서도 RESOLVED입니다(복명복창 오류의 해소). Cockpit이 이미 있으면 함께 비교하여 설정 오류가 남으면 SETTING_ERROR입니다. 이후 최초 Cockpit 입력으로 VERIFIED 또는 SETTING_ERROR를 판정할 수 있습니다.', responses={404: {'description': '해당 ID의 비행 또는 관제 지시가 존재하지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Resource not found'}}}}, 409: {'description': '비행이 종료되었거나 입력 순서, 중복 입력, 재검증 대상 상태가 올바르지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Flight has ended'}}}}})
def reverify_readback(clearance_id: str, payload: ObservationInput, db: Session = Depends(get_db)):
    return submit(db, clearance_id, payload, Source.READBACK, True)

@router.post("/{clearance_id}/cockpit/reverify", response_model=ClearanceResponse, summary='Cockpit 설정 오류 수정 및 재검증', description='SETTING_ERROR 상태에서만 호출할 수 있습니다. REVERIFYING 이벤트와 수정 Observation, COCKPIT_UPDATED 이력을 저장한 뒤 다시 비교합니다. 세 값이 모두 일치하면 RESOLVED 이벤트를 기록합니다. 불일치가 남으면 SETTING_ERROR 및 ALERTED를 다시 기록합니다. REVERIFYING은 트랜잭션 중간 상태이므로 응답에는 최종 판정 상태가 반환됩니다.', responses={404: {'description': '해당 ID의 비행 또는 관제 지시가 존재하지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Resource not found'}}}}, 409: {'description': '비행이 종료되었거나 입력 순서, 중복 입력, 재검증 대상 상태가 올바르지 않습니다.', 'content': {'application/json': {'example': {'detail': 'Flight has ended'}}}}})
def reverify_cockpit(clearance_id: str, payload: ObservationInput, db: Session = Depends(get_db)):
    return submit(db, clearance_id, payload, Source.COCKPIT, True)
