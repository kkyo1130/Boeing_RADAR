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

#### 실제 마이크 후속 검증 · 2026-11-09 23:07–23:10 KST

MacBook Air 마이크(48kHz mono PCM16) 신규 녹음3회를 실제 HTTP STT 경로로 전달했다. 1회 약신호로 빈 전사·보류, 2회 고도/방위 구간은 추출됐으나 전사에 호출부호가 없어 보류, 3회 전체 문장에서 Whisper가 `two`를 `to`로 전사했다. 3회 BERT CALLSIGN/규칙 ALT는 추출됐지만 hybrid HDG가 누락되어 구조 NEEDS_REVIEW(MENTION_SCOPE_UNKNOWN)·복창/전체 UNVERIFIED였다. 기존 문법의 후보값3000/270이 있어도 정상 복창으로 승인하지 않았다. 연결은 실제 입력으로 확인했으나 전체 정상 판정 성공은0/3이다. 앞부분 누락의 원인은 확정하지 않았다. 브라우저 마이크 권한/MediaRecorder 경로·실제 ATC·카메라는 여전히 미실행이다. 코드 변경 없이 [검증 안내](../bert-hybrid-stt-integration.md)에 기록하며 원음·전체응답은 Git-ignored `.demo/live-mic-20261109-*`에 보존했다. 동음어 처리 불일치는 미해결 후속 항목이며 테스트 통과를 위해 입력을 보정하지 않았다.

#### 숫자 동음어 보완·원본 재시험 · 2026-11-09

사용자 요청에 따라 `speech/numeric_slots.py`에서 기존 숫자 grammar의 동음어 사전을 후보 추출에도 적용했다. heading/flight level 뒤의 정확한3자리(heading359이하), 고도 명령+명시 feet 단위의 지원 숫자에만 적용하며 CALLSIGN·원문·BERT 입력은 변경하지 않는다. 원래 토큰과 후보·위치·문맥을 `numeric_normalizations`에 반환한다. 조건/범위/미지원 꼬리문구/누락 검사는 유지한다. 실제 BERT 포함 전용42개, 전체 backend549개 통과(skip0, 기존경고1). 최초 루트 실행은 app import경로로 실패해 정해진 backend 위치에서 다시 실행했다.

신규 녹음3개 원본 WAV를 실제 Whisper/BERT HTTP 경로로 재시험했다. 전사3개 모두 이전과 동일했다. 마지막20초 녹음에서 `heading to seven, zero.`를 보존한 채 HDG 후보의 to→two를 기록하여 RADAR123/3000ft/270°, 구조PASS·복창NORMAL을 확인했다. 앞의 약신호/호출부호 누락2개는 계속 보류됐다. Cockpit 부재로 전체 상태UNVERIFIED를 유지했다. 입력 SHA-256/원문/전체응답은 `.demo/homophone-replay/`에 보존하며 새 독립 정확도나 새 마이크 녹음으로 표현하지 않는다. 자체 리뷰에서 전역치환·정답주입·호출부호보완 없음과 기존 보류 조건을 확인했다. 같은 PR #21에 추가하며 외부리뷰/병합 전 reviewing 유지.

#### 병합 전 리뷰·CI 보완 · 2026-11-09

PR #21 자동 Codex 리뷰는 최초 구현 `98e6015`에 지적 없음으로 완료됐으며 GitHub APPROVED 제출과는 구분한다. 미해결 review thread는0개다. 이후 `e7b1e9e`까지의 숫자 동음어 변경은 자체 추가 검토로 원문/점수 출처 보존, 숫자 슬롯 한정, 조건·누락 보류를 확인했다. 최신 원격 Python fixtures는 Ubuntu/macOS 모두 성공했으나 frontend Chromium E2E가 기존 pilot 테스트의 Mac 전용 `/private/tmp` 캡처 경로 때문에 Linux에서3건 실패했다. 테스트 기대값은 유지하고 `testInfo.outputPath`로 캡처 경로만 바꿔 OS별 임시경로 의존과 실행 간 파일 충돌을 제거한다. 사용자 요청에 따라 최신 CI 성공과 head/충돌 여부 확인 후 squash merge한다. 자동 리뷰가 최신 코드를 재검토했다고 표현하지 않는다.

#### ATC 수음 / 파일럿 복창 분리 · 2026-11-10

- 범위·기준: PR #21 squash merge 후 `origin/dev` `d267d4b`, 별도 `codex/atc-microphone-modes` worktree. SPEC-004-WI-02의 실제 ATC 입력을 확장한다. 기존 사용자 작업 폴더·다른 WI는 변경하지 않는다.
- 구현: `api/demo.py`의 `/atc`는 PCM WAV와 두 가지 입력 경로 표시만 받고 서버가 ATC ID/역할을 만든다. `demo/adapters.py`는 사전 등록 전사를 거치지 않고 실제 LocalWhisper→선택된 NER/규칙→기존 구조/품질 검사를 재사용한다. ASR lock을 미디어/segment 쓰기 앞에서 획득해 busy 요청의 상태 변경을 막는다. 기존 Pilot 경로는 현재 ATC ID를 요구한다.
- UI: `DemoPanel.jsx`에 ATC/파일럿 모드, 관제 파일 재생+실제 마이크 캡처, 외부 재생 수음, 원문 구분을 추가했다. 녹음/처리 중 모드 전환 금지, 재생 후0.5초 수음 여유, 28초 초과 파일·29초 제한 입력 취소, 실패/취소/늦은 응답의 이전 지시 재사용 방지. `demo-audio.js`에서 ATC 수음의 echo cancellation/noise suppression을 끄고 Pilot에서 복구한다. `DemoResults.jsx`는 새 입력 확인 중 보류 문구를 표시한다. 서버 health 이벤트가 이전 복창 근거를 해제한다.
- 검증: backend에서 `RADAR_TEST_BERT_MODEL=<BERT 경로> RADAR_TEST_NER_MODEL=<v7 경로> ../.venv/bin/python -m pytest -q` → **560 passed**, skip0, 기존 Starlette deprecation1. 신규11개는 stub ASR로 두 경로 실제 ASR 호출, ATC→Pilot ID 연결, 조건부/인식 실패/엔진 장애, busy 무부작용, 정답/역할 주입 거절, 잘못된 WAV 거절을 확인한다. 실제 모델 smoke는 위 전체 실행에 포함된다.
- UI 검증: Node24에서 frontend `npm test` **53 passed**, `npm run test:e2e` **7 passed**, `npm run build` 성공. 신규 fake-device 브라우저 시험은 선택 파일 바이트 대신 캡처 WAV 전송, 재생 후 자동종료, 모드 고정, ATC 채택 후 Pilot 연결, 취소와 새로고침 후 과거 지시 차단을 확인한다. 실제 브라우저 하드웨어 수음 시험과 혼동하지 않는다.
- 실제 음원·장비: UWB-ATCC `_AT` 3개를 추론 전에 고정. 원음 파일3개와 MacBook Air 스피커→내장 마이크3개 모두 HTTP 저장/전사/보류 경로 완료, **지시 채택은 각0/3**. 원음에서도 호출부호·명령 오인식이 있어 현재 Whisper base.en의 실제 무전 전사 개선이 필요하다. 음소거였던 최초 하드웨어 시도는 별도 진단으로 남기고, 음소거 해제·볼륨50 재시험 후 이전 설정을 복원했다. 품질 임계값/정답 주입 없이 실패를 보존했다. [원본 출처·해시·결과](../evaluation/atc-playback-2026-11-10.json).
- 자체 리뷰: 역할을 추측하지 않는지, 요청이 바쁠 때 새 ATC가 생기지 않는지, 새 ATC 실패/취소/지연·연결 끊김 시 이전 정상 복창이 재사용되지 않는지 검토했다. 추가로 새로고침의 이전 ATC 버튼 활성화, 자동 시간 제한의 완료 오인, 이전 재생 콜백이 새 녹음을 종료할 가능성을 발견해 차단했다. 외부 리뷰/CI는 PR 제출 후 별도 확인한다.
- 인수인계: [실행 안내와 한계](../atc-microphone-modes.md). branch `codex/atc-microphone-modes`, 구현 커밋 `67852b8`, [PR #22](https://github.com/kkyo1130/Boeing_RADAR/pull/22). 마지막 콜백 보호 변경 후 관련 브라우저1개와 빌드를 재통과했다. 이번 사용 음원은 train split이고 학습 중복 미감사이므로 독립 성능평가가 아니다. ATCO2 미사용. 새 Pilot 육성/카메라/실제 무선 수신 전체 E2E는 미실행이며 WI-04 완료로 표시하지 않는다. 다음 판단은 고정된 음원으로 STT 모델·전처리를 비교하는 것이다.

#### 등록 호출부호 문맥을 STT에 전달 · 2026-11-10

- 범위/선행: 사용자 요청의 첫 개선 단계. `origin/dev` d267d4b에서 독립 `codex/atc-callsign-context`를 만들고 기존 ATC 수음 PR #22의 da0f219를 fast-forward 의존성으로 가져왔다. 원격 병합이나 기존 사용자 작업 수정은 하지 않는다. 기본 STT 모델·BERT 가중치·숫자 규칙은 그대로다.
- 확보 정보: 기존 ATC 데모 설정 및 SQLite의 마지막 세 세션에 RADAR123/GWI7P/DLH1KK/BAW820과 발음5개가 동일하게 등록돼 있음을 읽기 전용으로 확인했다. 실시간 주변 항공기 API/비행계획 연동은 없다. 후자3개는 과거 실제 녹음 데모에 맞춘 등록값이므로 이번 독립 현장 정보처럼 표현하지 않는다.
- 구현: `speech/context.py`에서 전체 세션 등록 발음의 문자/길이/개수 검증과 해시를 만들고 `speech/local.py`의 요청별 hotwords에 전달한다. `demo/adapters.py`의 ATC/Pilot 음성 경로에서 연결하며 transcript 후처리·강제 prefix·정답 주입은 없다. `stt_context` API 응답에 근거를 남기고 `/api/demo/status`에서 기능 설정을 확인한다. `scripts/run-context-backend.sh`로 opt-in 실행한다. context 사용 시 `callsign_context_requires_review`로 자동 지시 채택을 보류한다. 기존 CLI 음성 생산기는 이번 범위 밖이다.
- 비교 설계: 과거 등록 데모3개 + 목록 밖 실제12개 + 호출부호 없는 실제8개 + 합성무음1개, 같은 모델/설정으로 hotwords 유무48회. 결과를 보기 전에 seed20261112와 정답/설정/음원/가중치 해시를 고정했다. 개발/회귀 자료이며 새 독립 정확도 시험이 아니다. 전사 라벨은 기존 어시스턴트 검토를 재사용하며 항공 전문가 검수 없음.
- 검증/결과: 48회 비교 추론 및 실제 모델 ASGI2회 완료. 호출부호 등록 데모0/3→1/3, 목록 밖3/12 유지. 실제20개 부정 비교에서 등록 호출부호 삽입0/20, 기존 CALLSIGN 오검출2/8은 유지. [문맥 평가 보고서](../atc-callsign-context.md)와 고정 실측 JSON에 원문/후단 후보/채점·입력 감사를 기록했다. 실제 BERT/v7 포함 backend571 passed, 기존 Starlette deprecation 경고1. 최초 전체 실행은 잘못 지정한 v7 경로로1개 실패했으며 올바른 경로로 단독 재확인 후 최종 전체571개를 다시 통과했다. 첫 ASGI 요청은 UTC +00:00 표기가 계약의 Z 형식과 달라 모델 실행 전에 거절돼 수정했다. 새 하드웨어 수음·실시간 교통 목록·프런트 브라우저 검증은 미실행.
- 자체 리뷰: 모든 등록 항공기 동일 취급, 공유 모델의 세션 문맥 유출 없음, 설정 변경과 기존 세션 스냅샷 분리, 호출부호/무음 누락을 채우지 않음, 힌트가 있는 고점수 결과도 자동 채택하지 않음을 테스트했다. API 응답의 문맥 metadata는 Observation DB에 별도 영속화하지 않았다. 원음·가중치·DB·개인 절대 경로는 Git 제외. 조건부 효과와 데모 정답에서 미리 만든 등록 목록의 한계를 보고서에 명시한다.
- 인수인계: 구현/실측 커밋 `7a5da03`, [PR #27](https://github.com/kkyo1130/Boeing_RADAR/pull/27) 제출. base는 미병합 PR #22의 `codex/atc-microphone-modes`이며 선행 병합 후 dev로 전환한다. 외부 리뷰/병합 대기. WI 전체 AC-02 완료와 구분한다. 다음에는 실제 시연 전에 정한 항공기 목록 또는 연동된 교통 목록을 확보해야 일반화된 문맥 효과를 평가할 수 있다. 이번 요청에서 숫자 규칙 수정·STT 추가 학습은 수행하지 않는다.

#### 음성 고도·방위 숫자 문법 보완 및 고정 전사 재시험 · 2026-11-10

- 범위/기준: 사용자 요청의 두 번째 개선 단계. 최신 dev d267d4b에서 `codex/atc-numeric-rules`를 만들고 앞 단계 PR #27의203e5e0을 의존성으로 가져왔다. 원격 병합·기존 사용자 작업 수정 없음. 변경은 고도/방위 숫자 문법과 같은 녹음의 후단 재시험이며 STT/BERT 재학습·전사 수정은 하지 않았다.
- 구현/계약: `structure_rules.py`가 명시 FL2/3자리·one~nine hundred, 음성 heading360→0을 해석한다. `numeric_slots.py`가 고도 명령 뒤 compact/spaced FL 및 heading 뒤 단일 ah/uh/um 후보를 보완한다. 후자는 전체 구조 검사와 hybrid 둘 다 검토 사유를 남겨 자동 채택하지 않는다. 원문/offset/규칙 점수null 보존. `hybrid.py`는 rules-v3, `ner.py`는 새 버전의 보류를 처리한다. wire/target/OCR 범위는 그대로이며 관련 계약2개·문형 fixture24개·기존 smoke 기대 버전을 갱신했다. 원시값360을 정상값으로 고치는 변경이 아니다.
- 자료/실행: PR #26의88개 정답/ASR176조건과 PR #27의24개 문맥유무48조건을 고정 전사로 재사용했다. 실제 중복제외91음원+합성무음1개다. `replay_numeric_rules.py`에서 실제 BERT222회와 빈 무음2조건 처리, `publish_numeric_rules.py`에서224조건 커버리지·음원/전사/정답/가중치/소스 해시·채점·집계·호출부호 불변을 감사했다. 새 전사나 새 독립 시험이 아니며 방위13개 진단·기존 데모3개의 제약을 유지한다.
- 결과: ASR 고도11/15→13/15, 방위7/13→10/13. 정답 전사 고도12/15→14/15, 방위12/13→13/13. 기존 정답 필드 회귀0, 호출부호 예측 모두 불변. 방위 개선2개는 머뭇거림 후보/보류이며 자동 승인 성공이 아니다. 호출부호+숫자 전체 정답은 ASR 고도4/15·방위0/7 그대로다. 미해결 연속 숫자/obama/q/kel/heading 손상은 [보고서](../atc-numeric-rules.md)에 분리했다.
- 검증: backend에서 실제 BERT/v7 경로와 OMP_NUM_THREADS=4로 `../.venv/bin/python -m pytest -q`: **623 passed**, skip0, 기존 Starlette 경고1. 전용 숫자 경계47개와 wire360 거부/원문360→0/0과결측/unknown 삽입·꼬리/NER 없는 서버의 보류를 검증했다. 최초 집중 실행의 FL30 거부 기대1개는 새 계약에 맞게 FL30 허용·FL3 거부로 바꾼 뒤 전체 재검증했다. `contracts/check_v2.py`: Schema6/fixture21 PASS. 컴파일·diff 검사 통과. 서버 경계는 주입 STT fixture이며 실제 모델의 고정 전사 재추론과 구분한다.
- 자체 리뷰: 기존 조건/부정·상한·급변·호출부호·품질 gate 유지, 추출 후보와 서버 채택 구분, 360 변환은 음성 원문에만 제한, 361/720/음수·한 자리FL·불명확 꼬리 거부, 같은 평가 자료 재사용을 새 정확도로 주장하지 않음 확인. 기존 baseline/가중치/ASR 코드는 불변. 원음/가중치/DB는 Git 제외. 새 마이크·STT 재실행·브라우저·전문가/외부 리뷰는 미실행.
- 인수인계: 별도 커밋/PR 제출 후 reviewing. PR #27에 의존하며 선행 병합 후 dev로 base를 전환한다. WI 전체 AC-02 완료나 실제 운항 인수로 보지 않는다. 남은 핵심은 호출부호 STT 손상이며 이번 요청에서 추가 모델/규칙 튜닝으로 평가 표본을 반복 맞추지 않는다.

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
