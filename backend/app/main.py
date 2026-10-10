from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import Base, engine
from app.models import flight, clearance, safety_event
from app.api import flights, clearances

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(title="RADAR", version="0.1.0", lifespan=lifespan,
    description="""## RADAR Mock API 명세
관제 지시(ATC) → 복명복창(Readback) → Cockpit 설정값을 **하나의 Clearance**로 관리합니다.
ALT(feet)와 HDG(degrees)는 정확 일치로 비교합니다. 실제 STT·Vision AI·SDR 연결은 이번 PoC 범위에 포함하지 않습니다.

### Swagger 테스트 순서
1. **비행 세션 시작**으로 `flight_id`를 받습니다.
2. **ATC 지시 생성**에 해당 ID를 사용하여 `clearance_id`를 받습니다.
3. 같은 Clearance에 **Readback**, **Cockpit**을 입력합니다.
4. 오류가 나면 해당 **reverify** API에 수정값을 입력합니다.
5. **Safety Trace**에서 이벤트 이력을 확인한 뒤 **비행 세션 종료**를 호출합니다.

### 상태와 오류
`WAITING_READBACK` → `WAITING_COCKPIT` → `VERIFIED`가 정상 흐름입니다.
오류는 `READBACK_ERROR` 또는 `SETTING_ERROR`, 수정 흐름은 `REVERIFYING` → `RESOLVED`입니다.
Readback 비교가 우선이며, 복명복창 오류 수정은 Cockpit이 없어도 `RESOLVED`가 될 수 있습니다.
`REVERIFYING`은 이벤트에 보존되고 API 응답에는 최종 상태가 표시됩니다.

모든 시간은 **UTC ISO 8601**로 저장합니다. `observed_at` 생략 시 서버 시각, 시간대 생략 시 UTC를 적용합니다.
없는 ID는 **404**, 상태/순서 충돌은 **409**, 입력 형식·범위 오류는 **422**입니다.
""",
    openapi_tags=[
        {"name": "flights", "description": "비행 세션 시작·종료, ATC 지시 생성, 지시 목록과 Safety Trace 조회"},
        {"name": "clearances", "description": "Clearance 단위의 Observation 입력, ALT/HDG 비교 및 오류 재검증"},
    ],
)
app.include_router(flights.router)
app.include_router(clearances.router)
