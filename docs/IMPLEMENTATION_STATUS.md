# RADAR 구현 현황

확인일: 2026-10-10. 현재 체크아웃 `8a05c1c`, 최신 origin/dev `436c90c`, origin/main `e0a290d`를 직접 확인했다. dev의 PR #2 병합 커밋과 현재 체크아웃의 추적 파일 tree는 동일하다. 에이전트 설정/스펙 문서 및 이후 Vision PoC는 작업 브랜치의 후속 커밋에 포함하며 원격 dev에는 아직 포함되지 않았다. 아래 백엔드 기준선 확인 후 Vision 착수가 추가됐다.

## 구현된 흐름

JSON Mock Observation → Flight/Clearance 관리 → ATC와 Readback 비교 → Cockpit 비교 → 오류 단계 → 수정값 API 입력 → RESOLVED → SQLite Safety Trace 조회.

| 기능 | 현재 구현과 한계 | 코드 근거 |
| --- | --- | --- |
| 비행 시작·조회·종료 | 구현. 종료 후 변경·중복 종료 거부 | `backend/app/services/flight_service.py`, `backend/app/api/flights.py` |
| 지시 생성·목록·상세 | 구현. clearance_id로 입력 연결 | `backend/app/services/clearance_service.py`, `backend/app/api/clearances.py` |
| Observation 수신·검증 | 구현. ALT·HDG·confidence 필수; UTC 시각, 범위/타입 검사 | `backend/app/schemas/observation.py` |
| Readback/Setting 오류 구분 | 구현. ALT·HDG 정확 일치, Readback 우선 | `backend/app/services/validation_service.py` |
| 수정 재검증 | Mock API로 구현. 실제 새 프레임·수정 음성의 freshness는 검사하지 않음 | `backend/app/services/clearance_service.py` |
| Safety Trace 저장·조회 | 기본 이벤트·관측 스냅샷·수정 전후 값 보존. 근거 파일·보류·health·억제·사용자 확인은 없음 | `backend/app/services/safety_trace_service.py`, `backend/app/models/safety_event.py` |
| 경고 | ALERTED 이벤트 저장만 있음. 화면·음성·경고 단계·억제 정책 없음 | `backend/app/core/enums.py`, `backend/app/services/clearance_service.py` |
| Swagger | 13개 메서드별 API 엔드포인트 | `backend/app/main.py` 및 API 라우터 |

`RECOGNIZED`라는 이벤트명은 실제 AI 인식 성공을 의미하지 않는다. 현재 API에 전달한 JSON 값을 기록하는 이름이다. Readback 수정의 RESOLVED는 복명복창 오류 해소이며 Cockpit이 없으면 전체 3단계 검증 완료는 아니다.

## 기능 스펙 기준 진행 상황

| 스펙 | 이미 있는 기반 | 목표 기준 남은 일 |
| --- | --- | --- |
| SPEC-001 개발 환경 | monorepo 구조·backend 이동·기존 테스트 완료 | 파트별 실행/버전·설정, 반복 가능한 자동 검증 기반 |
| SPEC-002 관측 계약 | 기본 DTO·지시 ID 연결·입력 순서/중복 거부 | 부분 지시·null·health·품질·근거·버전·stale/역순 정책 |
| SPEC-003 Vision | 합성 정지 이미지 ROI·OCR·숫자/단위 검사·null 사유·근거·결과 JSON | 실제 화면/카메라·영상/안정화·품질/장애 감시·서버 연동·실장비 평가 |
| SPEC-004 통신/음성 | 디렉터리만 있음 | 수신·전처리·분리·STT·문맥 구조화·품질 감시 전부 |
| SPEC-005 판정 | 정확 비교·오류 단계·필수 입력 범위 검증 | UNVERIFIED, 추출 후 규칙 교차검사, 품질/freshness 고려 |
| SPEC-006 화면/알림 | backend Flight API와 ALERTED 기록 | React 화면·근거 패널·실시간 표시·음성/억제·경고 단계 |
| SPEC-007 Closed-loop | Mock 수정 API·REVERIFYING/RESOLVED 기록 | Incident 연결·관측 freshness·실입력 수정 재인식·전체 시연 |
| SPEC-008 Trace/Report | 기본 Trace DB·조회 API | 확장 이력·집계·리포트 화면·해결 시간/경고 이력 |
| SPEC-009 평가/시연 | 기존 Mock backend 테스트 | 라벨 영상/음성·거짓 정상/보류/지연 평가·교육 모드·실장비 E2E |
| SPEC-010 선택 확장 | 없음 | 파일 출력·버전별 평가 추세 |

확장 WI는 기존 기반을 재사용한다. 일부 Vision/계약 WI는 implementing이며 전체 완료 조건은 미충족이다. 이미 있는 서버 기능을 모두 미구현이라고 해석하지 않는다. 현재 35개 WI 중 1개 done이라는 수치는 신규 계획의 작업 단위 상태이며 제품 완성도 퍼센트가 아니다.

## 직접 검증한 결과

- `cd backend && .venv/bin/python -m pytest -q`: **17 passed, 1 warning**, 0.31초. 경고는 Starlette TestClient의 httpx deprecation이다.
- 별도 임시 SQLite와 FastAPI TestClient에서 현재 API 13개 확인.
- ATC/Readback/Cockpit 모두 `confidence=0.0`, `observed_at=2020-01-01T00:00:00Z`, 값 일치 → **VERIFIED**. 모델 신뢰도와 관측 freshness가 현재 판정에 적용되지 않는다는 실행 근거다.
- `altitude=null` → **422**. 판독 불가 Observation 전달 미지원.
- heading만 전달 → **422**. 부분 지시 미지원.
- frontend/communication/tests/integration/scripts는 골격이다. 이후 추가된 Vision 정지 이미지 PoC와 계약 초안은 [Vision 검증 기록](../vision/evaluation/README.md) 참조: 테스트 13개, 합성 고정 기대 사례 5개 통과. 서버 전송·실장비는 미구현.
- 이전 실제 Uvicorn HTTP 시연 결과는 SPEC-001-WI-01 참조. 이번 추가 확인은 TestClient 검증이며 실제 카메라·마이크·통신 검증이 아니다.

## 다음 구현 순서

1. SPEC-002-WI-01: 판독 불가·부분 지시·품질·health·근거를 포함한 계약 확정.
2. 김세현: SPEC-003-WI-01부터 실제 화면·ROI·정답 이미지 준비. 이후 카메라/인식/품질/근거/전송.
3. Backend: SPEC-002-WI-02와 SPEC-005로 계약 수신·stale 처리·3상태 판정.
4. 통신/음성과 UI를 연결한 뒤 중간점검 E2E를 별도 검증.

검토 범위는 이 저장소의 현재 체크아웃과 원격 dev/main이다. 팀원의 미푸시 코드나 다른 저장소의 작업은 포함하지 않는다.

## 공유 문서와 최종 Vision 검증

사용자 요청으로 사진·결과·재현 안내를 [MCP Vision 문서](vision/README.md)에 보존했다. 현재 Vision 테스트 29개 및 합성 고정 사례 5개 통과, 참고 사진 ALT 10000/HDG 270/speed 250 인식 확인. 중복 output 81개(약 8.7MB) 정리. 실제 카메라/서버 연동은 미구현이다.
