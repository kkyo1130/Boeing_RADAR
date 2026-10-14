# SPEC-005: 규칙 재검증과 3상태 교차검증

## 기본 정보

- 요구사항 버전: 1
- 상태: draft (목표 초안; 현재 구현과 미정 사항은 별도 표시)
- Priority: P0
- 근거: [서비스 방향](../service/overview.md), [요구사항 매핑](../service/requirements-map.md)
- 기능 전체 검증: SPEC-005-WI-03 (SPEC-010은 서로 독립된 두 선택 기능이므로 각 WI 자체 검증)

## 목적과 범위

검증 가능한 입력으로 오류 단계를 판정하고 불확실하면 보류한다.

포함 범위는 아래 workitem의 산출물이다. 실제 항공기 제어·QNH/Baro와 다른 기능의 소유 계약은 제외한다. 2026-10-13 후속 요청으로 WI-01 결정론적 검사 함수를 구현한다. 2026-10-14 WI-02에서 v1 API 최종 3상태 판정도 연결한다.

## 동작·계약·미정 사항

공통 단위·ID·시각·null·품질·근거는 [SPEC-002](002-observation-contracts.md), 판정은 [SPEC-005](005-safe-validation.md)를 따른다. 해당 계약 확장 전 현재 API가 지원한다고 가정하지 않는다.
미정 사항 Q-01~Q-05와 영향 범위는 [서비스 방향](../service/overview.md#결정이-필요한-항목)에 있다. workitem의 선행 결과와 필수 결정이 확보된 범위만 구현한다. fixture 성공과 실카메라·마이크·수신 성공을 구분한다.

## 이미 구현된 기반

validation_service.py의 ALT/HDG 정확 비교·Readback 우선·오류 단계와 스키마 범위 검증이 있다. SPEC-002 v1 경로는 UNVERIFIED와 품질/시각 정보를 보존한다. 이번 WI-01은 추출 후 결정론적 검사 함수를 추가하며 WI-02에서 명시 설정을 요구하는 3상태 판정·API 연결을 구현했다. 전체 기능 회귀 WI-03과 실입력 인수는 후속 작업이다. 상세 실행 근거는 [구현 현황](../IMPLEMENTATION_STATUS.md)을 참조한다. 아래 WI는 확장 요구까지 포함하므로 이 기반만으로 done 처리하지 않는다.

## 완료 조건

| ID | 입력·전제와 관찰 가능한 기대 결과 | 검증 | 담당 workitem |
| --- | --- | --- | --- |
| AC-01 | 선행: SPEC-002-WI-02. HDG 범위·FL 형식/상한·호출부호·조건/순서·비정상 급변을 PASS/INVALID/NEEDS_REVIEW로 검사한다 | 허용/경계/위반/문맥 충돌 fixture; 급변·상한은 시연 정책과 근거를 확정 | [SPEC-005-WI-01](#wi-01) |
| AC-02 | 선행: SPEC-005-WI-01. 가용·fresh·검증된 입력만 비교하고 보류를 Readback/Setting 오류와 구분한다. 확인 가능한 Readback 오류는 우선하고 Cockpit 미인식은 해당 단계 보류로 표시한다 | 정상·두 오류·부분 지시·null·stale·낮은 품질·규칙 충돌 회귀; 기존 RESOLVED와 VERIFIED 의미 보존 | [SPEC-005-WI-02](#wi-02) |
| AC-03 | 선행: SPEC-005-WI-02. 불확실/장애 입력과 혼합 오류 사례가 잘못된 VERIFIED를 만들지 않고 판정 근거/보류 사유가 조회된다 | 완료 조건 전체 fixture·API 검증; 실제 입력 전체 검증은 SPEC-009 | [SPEC-005-WI-03](#wi-03) |

## Work items

진행 상태의 원본은 [TODO](todo.md)다. 아래 담당자는 기획 역할 기준 제안이며 작업 예약은 아니다.

<a id="wi-01"></a>

### SPEC-005-WI-01: 독립 결정론적 구조화 검사

- Priority: P0; 담당 제안: 노남경
- 완료 조건: AC-01
- 선행 작업·산출물: SPEC-002-WI-02
- 수정 영역: `backend/app/services/validation/, contracts/`
- 산출물·개별 완료 조건: HDG 범위·FL 형식/상한·호출부호·조건/순서·비정상 급변을 PASS/INVALID/NEEDS_REVIEW로 검사한다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 허용/경계/위반/문맥 충돌 fixture; 급변·상한은 시연 정책과 근거를 확정
- 기능 전체 검증: 아니오; 해당 WI 조건만 확인한다.

#### 결과·검증·리뷰·인수인계

- 구현: 2026-10-13 후속 요청으로 `backend/app/services/validation/__init__.py`, `rules.py`, `backend/tests/test_extraction_rules.py`, [검사 계약](../../contracts/extraction-rules.md), [모의 정책](../../contracts/rule-policy-demo.json) 추가. `python` 브랜치 `2e75703`로 커밋·푸시하고 PR #4에 반영한 선행 구현. 기존 비교 서비스·API·원본 관측을 수정하지 않고 결과·문제 목록 반환.
- 검증: backend에서 `/private/tmp/radar-contract-venv/bin/python -m pytest tests ../tests/integration -q`: **115 passed, 1 warning**(Starlette/httpx deprecation). 기존 84개+새 31개: HDG 0/359/360·raw 충돌/O 문자·FL 형식/줄바꿈/변환/상한·부분 지시·누락·호출부호/조건/순서·시각/원본/지시 연결·급변 임계값과 359→0·잘못된 정책·입력 불변 확인. `git diff --check`와 문서 로컬 링크 검사 통과. 실제 카메라/마이크/STT/OCR·외부 HTTP 및 운용 임계값 검증은 미실행.
- 리뷰: 단일 에이전트가 역할 지침 적용. 숫자 추측·자동 보정 없음, 시각/원문/확인된 문맥 부족은 NEEDS_REVIEW, 명시적 계약/구조 충돌은 INVALID, 급변은 불일치로 단정하지 않음. 고도 상한은 raw 누락 시에도 검사함. 같은 추출 기반 검사를 완전히 독립된 안전 채널로 표현하지 않음. PASS는 최종 정상/정확도 보장이 아니며 정책·확인 문맥 없이 음성 PASS를 만들지 않음.
- 인수인계: 다음 WI-02에서 rules 결과·freshness·health/quality를 v1 서버의 NORMAL/MISMATCH/UNVERIFIED와 오류 단계에 연결. 시연 정책 mock-demo/1은 60000ft/6000ft/90°/10초 경계 fixture용 명시 정책이며 실장비 인수 Q-04는 미정. 호출부호/조건/행동 문맥은 확인된 지시에서 전달하고 같은 추출에서 복사하지 않음. 자유 발화 의미 해석은 SPEC-004 범위. 커밋·푸시·PR 갱신 미실행, 사용자 `.gitignore` 변경 보존.

<a id="wi-02"></a>

### SPEC-005-WI-02: NORMAL/MISMATCH/UNVERIFIED와 오류 단계

- Priority: P0; 담당 제안: 노남경
- 완료 조건: AC-02
- 선행 작업·산출물: SPEC-005-WI-01
- 수정 영역: `backend/app/services/, core/, schemas/`
- 산출물·개별 완료 조건: 가용·fresh·검증된 입력만 비교하고 보류를 Readback/Setting 오류와 구분한다. 확인 가능한 Readback 오류는 우선하고 Cockpit 미인식은 해당 단계 보류로 표시한다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 정상·두 오류·부분 지시·null·stale·낮은 품질·규칙 충돌 회귀; 기존 RESOLVED와 VERIFIED 의미 보존
- 기능 전체 검증: 아니오; 해당 WI 조건만 확인한다.

#### 결과·검증·리뷰·인수인계

- 구현: 2026-10-14 후속 요청으로 `services/validation/decision.py`, `schemas/validation_settings.py`, `schemas/validation_result.py`, `tests/test_three_state_decision.py` 추가. `services/contract_service.py`, `api/contract_observations.py`, `models/contract_observation.py`, `app/migrate_contract_storage.py` 및 계약/구현 안내 갱신. 정책·확인 문맥 1회 등록, 단계/필드별 검사·NORMAL/MISMATCH/UNVERIFIED·오류 우선순위·새 관측 해결·규칙/비교/설정 근거 조회 구현. [판정 계약](../../contracts/three-state-validation.md) 참조. `python` 브랜치 `2e75703` 기준 미커밋.
- 검증: backend에서 `/private/tmp/radar-contract-venv/bin/python -m pytest tests ../tests/integration -q`: **143 passed, 1 warning**(Starlette/httpx deprecation), 기존 115개+신규 28개. 정상/두 오류/혼합 오류·Readback 우선·부분 지시/0·null/stale/미상/낮은 점수·품질·규칙/호출부호/조건/순서 충돌·근거 누락·score 임계값·급변·장애/복구 새 프레임·거부된 최신 입력·새 지시·종료·중간 보류 수정 후 해결 검증. 기존 v1 DB 보존과 설정 테이블 마이그레이션 2회 확인. 중간 마이그레이션 테스트의 Flight PK 조회 혼동은 올바른 flight_id 조회로 수정했고 최종 전체 검사 통과. OpenAPI 설정 요청·3상태/확인 문맥 응답 스키마, `git diff --check`, 로컬 링크 검사 통과.
- 리뷰: 단일 에이전트가 역할 지침 적용. 설정/확인 문맥 없는 관측은 계속 UNVERIFIED, Readback 자체 action 목록을 기대값으로 복사하지 않음. 확인 가능한 숫자 불일치만 errors, 불확실한 규칙/시각/품질 문제는 해당 필드/단계 보류. 장치 available health만으로 이전 VERIFIED를 복원하지 않고 새 관측 요구. 수신 accepted·규칙 PASS·전체 NORMAL·단계 RESOLVED를 구분하며 Readback만 해결된 경우 verdict=UNVERIFIED/status=RESOLVED 보존. 이전 Mock API·규칙 서비스 유지.
- 인수인계: 다음 WI-03에서 완료 조건 전체와 거짓 정상 경계를 별도 회귀 검증. 실제 카메라/음성/SDR/모델 어댑터·외부 HTTP·다른 DB 검증은 미실행. 명시 모의 정책/모델 점수 기준은 Q-04 실장비 인수 기준이 아니며 실제 확률/정확도로 표현하지 않음. 확인 주체는 표시용이며 인증 구현 아님. Incident/최종 판정 이벤트 수명주기는 SPEC-007/008 범위. 커밋·푸시·PR 갱신 미실행, 사용자 `.gitignore` 변경 보존.

<a id="wi-03"></a>

### SPEC-005-WI-03: 판정 전체 회귀·거짓 정상 확인

- Priority: P0; 담당 제안: 노남경
- 완료 조건: AC-03
- 선행 작업·산출물: SPEC-005-WI-02
- 수정 영역: `backend/tests/, tests/integration/`
- 산출물·개별 완료 조건: 불확실/장애 입력과 혼합 오류 사례가 잘못된 VERIFIED를 만들지 않고 판정 근거/보류 사유가 조회된다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 완료 조건 전체 fixture·API 검증; 실제 입력 전체 검증은 SPEC-009
- 기능 전체 검증: 예; 이 스펙의 모든 AC를 대조하되 환경과 mock/실입력을 구분한다.

#### 결과·검증·리뷰·인수인계

- 구현: 미착수; 코드 기준·변경 파일은 수행 후 기록.
- 검증: 미실행; 실제 명령·환경·기대/관찰 결과·통과/실패/차단을 수행 후 기록.
- 리뷰: 미수행; 계약·범위·회귀·근거 검토와 지적 해결 여부를 수행 후 기록.
- 인수인계: 담당 세션 미배정; 선행 결과와 해당 미정 사항 확인 후 이 WI를 지정해 착수.

## 변경 기록

- v1 · 2026-10-10: 사용자 제공 기획·Priority·자문과 현재 코드로 최초 작업 초안 작성. 문서 작성 권한과 기능 구현 권한은 구분한다.

- 2026-10-13: WI-01 검사 함수·명시 모의 정책·31개 회귀 사례 추가. AC-01 모의 범위 완료, API 최종 판정은 WI-02에서 구현.

- 2026-10-14: WI-02 명시 정책·확인 문맥·단계별 3상태 판정 및 새 관측 해결 구현. AC-02 모의 환경 검증 완료, WI-03 전체 회귀 및 실입력 인수는 별도.
