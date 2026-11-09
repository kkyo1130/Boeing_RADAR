# SPEC-004: 관제·복명복창 음성 입력과 구조화

## 기본 정보

- 요구사항 버전: 1
- 상태: draft (목표 초안; 현재 구현과 미정 사항은 별도 표시)
- Priority: P0
- 근거: [서비스 방향](../service/overview.md), [요구사항 매핑](../service/requirements-map.md)
- 기능 전체 검증: SPEC-004-WI-04 (SPEC-010은 서로 독립된 두 선택 기능이므로 각 WI 자체 검증)

## 목적과 범위

음성 구간과 지시 의미를 구조화하고 품질/불확실성을 보존한다.

포함 범위는 아래 workitem의 산출물이다. 실제 항공기 제어·QNH/Baro와 다른 기능의 소유 계약은 제외한다. 새 제품 코드는 이번 문서 정리 요청에서 구현하지 않는다.

## 동작·계약·미정 사항

공통 단위·ID·시각·null·품질·근거는 [SPEC-002](002-observation-contracts.md), 판정은 [SPEC-005](005-safe-validation.md)를 따른다. 해당 계약 확장 전 현재 API가 지원한다고 가정하지 않는다.
미정 사항 Q-01~Q-05와 영향 범위는 [서비스 방향](../service/overview.md#결정이-필요한-항목)에 있다. workitem의 선행 결과와 필수 결정이 확보된 범위만 구현한다. fixture 성공과 실카메라·마이크·수신 성공을 구분한다.

## 완료 조건

| ID | 입력·전제와 관찰 가능한 기대 결과 | 검증 | 담당 workitem |
| --- | --- | --- | --- |
| AC-01 | 선행: SPEC-001-WI-01, SPEC-002-WI-01. 실제 수신/파일 예비 입력을 구분하고 원본 참조·전처리 결과·구간 ID·시각·역할 근거를 생성한다 | 허용된 녹음 기반 분리·전처리 검증 후 선택한 실제 수신 장비 검증; Q-02 | [SPEC-004-WI-01](#wi-01) |
| AC-02 | 선행: SPEC-004-WI-01, SPEC-002-WI-02. 음성→Transcript→ALT/HDG·호출부호·조건/순서를 구조화하고 누락/모호함은 null/사유로 보존한다 | 고정 음성 fixture와 실제 ATC 파일·Pilot 마이크; 제공자/모델은 Q-03 | [SPEC-004-WI-02](#wi-02) |
| AC-03 | 선행: SPEC-004-WI-01, SPEC-004-WI-02. 마이크 입력 없음·약신호·중첩·잡음에서 health/quality/불확실 사유를 반환한다. 불충분 근거로 ATC/Pilot 역할이나 숫자를 확정하지 않는다 | 정답 음성 악조건·중단·경고 재유입 사례 검증; 최소 health는 P0, 상세 품질 탐지는 P1 | [SPEC-004-WI-03](#wi-03) |
| AC-04 | 선행: SPEC-004-WI-02, SPEC-004-WI-03, SPEC-005-WI-02. ATC/Pilot 구간이 같은 지시에 연결되고 정상·Readback 오류·저품질 재확인이 원본 음성과 함께 서버 상태에 반영된다 | 녹음 E2E와 실제 수신/마이크 E2E 분리 기록; 실제 수신 미실행이면 통합 완료 아님 | [SPEC-004-WI-04](#wi-04) |

## Work items

진행 상태의 원본은 [TODO](todo.md)다. 아래 담당자는 기획 역할 기준 제안이며 작업 예약은 아니다.

<a id="wi-01"></a>

### SPEC-004-WI-01: 음성 수신·전처리·구간 분리

- Priority: P0; 담당 제안: 이예찬
- 완료 조건: AC-01
- 선행 작업·산출물: SPEC-001-WI-01, SPEC-002-WI-01
- 수정 영역: `communication/`
- 산출물·개별 완료 조건: 실제 수신/파일 예비 입력을 구분하고 원본 참조·전처리 결과·구간 ID·시각·역할 근거를 생성한다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 허용된 녹음 기반 분리·전처리 검증 후 선택한 실제 수신 장비 검증; Q-02
- 기능 전체 검증: 아니오; 해당 WI 조건만 확인한다.

#### 결과·검증·리뷰·인수인계

- 구현: 미착수; 코드 기준·변경 파일은 수행 후 기록.
- 검증: 미실행; 실제 명령·환경·기대/관찰 결과·통과/실패/차단을 수행 후 기록.
- 리뷰: 미수행; 계약·범위·회귀·근거 검토와 지적 해결 여부를 수행 후 기록.
- 인수인계: 담당 세션 미배정; 선행 결과와 해당 미정 사항 확인 후 이 WI를 지정해 착수.

<a id="wi-02"></a>

### SPEC-004-WI-02: ATC/Pilot STT와 문맥 구조화

- Priority: P0; 담당 제안: 노남경
- 완료 조건: AC-02
- 선행 작업·산출물: SPEC-004-WI-01, SPEC-002-WI-02
- 수정 영역: `backend/app/services/speech/`
- 산출물·개별 완료 조건: 음성→Transcript→ALT/HDG·호출부호·조건/순서를 구조화하고 누락/모호함은 null/사유로 보존한다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 고정 음성 fixture와 실제 ATC 파일·Pilot 마이크; 제공자/모델은 Q-03
- 기능 전체 검증: 아니오; 해당 WI 조건만 확인한다.

#### 결과·검증·리뷰·인수인계

2026-11-08 사용자 요청 범위: 학습된 v7 NER의 영어 추출 함수와 현재 RADAR STT 연결. 기준 dev `2e3dd77`, 브랜치 `codex/v7-stt-integration`. 원래 작업 폴더의 미커밋 변경은 보존하고 독립 worktree에서 구현했다.

- 구현: `speech/ner.py`는 local-only safetensors/config/manifest를 검사하고 모델·fast tokenizer를 프로세스별 캐시한다. 첫 subtoken 라벨을 원문 단어/문자구간에 정렬, raw BIO와 비보정 모델 점수 반환. 128토큰 초과/빈 입력/illegal BIO를 정상 처리하지 않음. `scripts/extract-atc.py` 및 opt-in `POST /api/demo/speech/extract` 제공.
- 연결: `demo/adapters.py`의 LocalWhisper 결과를 v7에 전달. 등록 호출부호/전체 문장 문법으로 변환된 값과 NER 후보가 일치해야 기존 PASS 가능. 등록 ATC 시나리오도 같은 gate를 사용하나 실제 ATC STT라고 표현하지 않음. `RADAR_NER_MODEL`을 지정하면 모델 실패/후보 불일치 시 fields를 비우고 NEEDS_REVIEW; 미지정 시 기존 동작 유지. 원본 transcript, 음성근거, segment/attempt/ATC ID·역할과 후속 수신/구조 검사 보존.
- 검증: backend에서 전용 Python3.11 환경으로 `python -m pytest -q`: 506 passed, 1 skipped(실제 모델 opt-in), Starlette TestClient deprecation 경고1. `RADAR_TEST_NER_MODEL=<final-v7> python -m pytest -q tests/test_ner_v7.py`: 실제 가중치 포함8 passed. 주입 ASR의 raw transcript 전달/모델 실패 후 비정상 상태, 미지원 suffix·오디오 품질 보류, 호출부호/숫자 불일치, 잘못된BIO/NaN/길이초과 검사. 실제v7+speech_payload 직접 smoke에서 Radar123/ALT3000/HDG270의 기존 문법과 NER 일치 PASS 확인.
- 리뷰: 자체 검토. NER 점수를 검증된 정확도로 표현하지 않음, 신경망 결과만으로 숫자 승인/상태 정상/설정 변경하지 않음. 동일 transcript의 두 검사는 독립 안전 채널 아님. 유효 BIO라도 잘못된 의미 추출 가능. 기존 parser의 미지원 문법을 임의 제거/확장하지 않음. weight/pickle/원음은 커밋하지 않음.
- 인수인계: `backend/requirements-ner.txt`, `RADAR_NER_MODEL`, `docs/v7-stt-integration.md` 참고. v7 함수와 현재 데모 STT 결과 연결만 요청 범위에서 구현. 실제 사용자 마이크/Whisper 원음 E2E, 더 넓은 관제 문법/숫자 정규화, 전체 AC-02 인수는 미완료. 코드 PR 검토 대상이며 WI 전체 완료를 주장하지 않는다.

#### BERT+규칙 STT 추가 연결 · 2026-11-09

- 범위/기준: 사용자 요청에 따라 SPEC-004-WI-02의 기존 STT 구조화 경로를 확장했다. 기준 `origin/dev` `4a6fd74`, 독립 브랜치 `codex/bert-hybrid-stt`. 기존 작업 폴더의 변경은 보존했다. 상태는 reviewing이며 WI 전체 AC-02 완료를 뜻하지 않는다.
- 구현: `speech/hybrid.py`는 로컬 BERT의 CALLSIGN과 이전 비교 실험에서 보완한 `hybrid_rules.py`/`hybrid_baseline.py`의 ACTION·ALT·HDG를 합친다. `hybrid_prefixes.json`은 실제 UWB 학습400개에서 얻은46개 접두어이며 별도 출처·라이선스 고지를 포함한다. BERT는 기존 검증99개의 전체일치 기준으로 seed13을 선택했고 재학습하지 않았다. 모델·tokenizer6개 파일의 SHA-256과 정확한 라벨 구성을 검사한다.
- 연결/계약: `RADAR_NER_BACKEND=bert-hybrid`에서 LocalWhisper→원문→BERT+규칙 후보→기존 전체 문법/등록 호출부호/숫자 검사→기존 저장·판정으로 이어진다. 원문/문자 오프셋/모델 원시 라벨과 정규화 입력을 보존한다. 규칙 결과는 `source=rule, model_score=null`; BERT 점수는 정확도로 표현하지 않는다. 모델 로딩 실패, 잘못된 BIO, 조건/정정/충돌·필수 호출부호 누락은 fields를 비우고 검토로 남긴다. 명시적 backend 설정에 모델이 없어도 규칙만으로 조용히 통과하지 않는다. 기본 설정의 v7은 유지한다.
- STT 표현 보완: 실제 Whisper가 생성한 쉼표·`3,000`·`2-7-0`을 처리한다. BERT 입력의 단어 끝 문장부호만 제거하고 원문은 유지한다. 숫자 슬롯에서 정확히3자리 하이픈 표기만 허용하며 `270-280`, `2-7`, `-90`, `2--7-0` 등은 거부한다.
- 자동 검증: 작업 worktree의 `backend/`에서 실제 두 모델 경로를 지정해 `RADAR_TEST_BERT_MODEL=<prepared-bert> RADAR_TEST_NER_MODEL=<v7> ../.venv/bin/python -m pytest -q` 실행: **532 passed**, skipped 없음, Starlette TestClient deprecation 경고1. 실제 BERT/v7 로딩, artifact 변조, 원문 정렬·점수 출처, 규칙 수정, 잘못된 BIO/조건/단위/숫자 표기/명시 설정 실패 처리와 기존 서버 회귀를 포함한다. 별도로 기존487문장×3seed의 캐시 예측1461개를 옮긴 결합 함수와 대조해 라벨·오프셋 일치를 확인했다. 이 비교는 새 추론 정확도 평가가 아니다.
- HTTP 검증: 실제 실행 서버에서 `.venv/bin/python scripts/test-hybrid-stt.py --audio .demo/audio --output .demo/hybrid-http-verified --recorded-wav <previous-microphone.wav>`를 실행했다. ASR stub 없이 faster-whisper base.en과 BERT가 동작했다. 합성 정상 음성은 RADAR123/3000ft/270°, 구조PASS·복창NORMAL; 합성290° 음성은 기대270° 대비 MISMATCH; 무음은 NEEDS_REVIEW/UNVERIFIED. 이전 사용자 마이크 WAV의 `Eight thousand feet, heading 270.`는 호출부호/명령 누락으로 NEEDS_REVIEW/UNVERIFIED였다. 정상 복창도 Cockpit 관측이 없으므로 비행 전체 상태는 UNVERIFIED다. frontend5176의 `/api/demo/status`가 backend8013의 bert-hybrid를 반환하는 proxy 연결도 확인했다.
- 자체 리뷰: 동일 전사의 검사들은 독립 안전 채널이 아니다. 하이픈 처리가2자리 범위까지 받아들이던 초기 구현을 정확히3자리로 제한하고 회귀 테스트를 추가했다. 명시 설정 실패의 묵시적 규칙 fallback, 속도/상승률의 고도 혼동, BERT 점수의 규칙 점수 전용, 출처 누락 위험을 검토했다. 외부 사람/자동 PR 리뷰는 아직 미수행이다.
- 인수인계: [실행·검증 안내](../bert-hybrid-stt-integration.md), `scripts/prepare-hybrid-model.py`, `scripts/run-hybrid-backend.sh`, `scripts/test-hybrid-stt.py` 참고. 가중치·오디오·DB·원시 보고서는 로컬 `.demo/`에만 보존한다. 새 실시간 마이크 녹음, 실제 ATC 원음 STT, 카메라 통합/전체 AC-02는 미실행이다. PR 검토 후 병합 여부를 결정하며 자동 병합하지 않는다.

<a id="wi-03"></a>

### SPEC-004-WI-03: 음성 품질·입력 건전성과 불확실성

- Priority: P0/P1; 담당 제안: 이예찬·노남경
- 완료 조건: AC-03
- 선행 작업·산출물: SPEC-004-WI-01, SPEC-004-WI-02
- 수정 영역: `communication/, backend/app/services/speech/`
- 산출물·개별 완료 조건: 마이크 입력 없음·약신호·중첩·잡음에서 health/quality/불확실 사유를 반환한다. 불충분 근거로 ATC/Pilot 역할이나 숫자를 확정하지 않는다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 정답 음성 악조건·중단·경고 재유입 사례 검증; 최소 health는 P0, 상세 품질 탐지는 P1
- 기능 전체 검증: 아니오; 해당 WI 조건만 확인한다.

#### 결과·검증·리뷰·인수인계

- 구현: 미착수; 코드 기준·변경 파일은 수행 후 기록.
- 검증: 미실행; 실제 명령·환경·기대/관찰 결과·통과/실패/차단을 수행 후 기록.
- 리뷰: 미수행; 계약·범위·회귀·근거 검토와 지적 해결 여부를 수행 후 기록.
- 인수인계: 담당 세션 미배정; 선행 결과와 해당 미정 사항 확인 후 이 WI를 지정해 착수.

<a id="wi-04"></a>

### SPEC-004-WI-04: 음성 경로 전체 통합 검증

- Priority: P0; 담당 제안: 이예찬·노남경
- 완료 조건: AC-04
- 선행 작업·산출물: SPEC-004-WI-02, SPEC-004-WI-03, SPEC-005-WI-02
- 수정 영역: `tests/integration/`
- 산출물·개별 완료 조건: ATC/Pilot 구간이 같은 지시에 연결되고 정상·Readback 오류·저품질 재확인이 원본 음성과 함께 서버 상태에 반영된다
- 제외: 위 범위 밖의 기능 구현·실제 항공 운용 보장
- 검증 방법: 녹음 E2E와 실제 수신/마이크 E2E 분리 기록; 실제 수신 미실행이면 통합 완료 아님
- 기능 전체 검증: 예; 이 스펙의 모든 AC를 대조하되 환경과 mock/실입력을 구분한다.

#### 결과·검증·리뷰·인수인계

- 구현: 미착수; 코드 기준·변경 파일은 수행 후 기록.
- 검증: 미실행; 실제 명령·환경·기대/관찰 결과·통과/실패/차단을 수행 후 기록.
- 리뷰: 미수행; 계약·범위·회귀·근거 검토와 지적 해결 여부를 수행 후 기록.
- 인수인계: 담당 세션 미배정; 선행 결과와 해당 미정 사항 확인 후 이 WI를 지정해 착수.

## 변경 기록

- v1 · 2026-10-10: 사용자 제공 기획·Priority·자문과 현재 코드로 최초 작업 초안 작성. 문서 작성 권한과 기능 구현 권한은 구분한다.
