# 보조 음성·입력 우선순위 계약 · SPEC-006-WI-03

기존 v2 수신·판정·Incident를 그대로 사용한다. 서버가 현재 안내 자격·발생 건·한 문장의 구성·우선순위·완료 이력을 소유한다. 브라우저는 값을 비교하거나 오류를 해결하지 않는다. 정적 한국어 WAV6개를 Web Audio로 재생하며 실행 중 외부 TTS API/마이크 권한이 필요하지 않다. `tools/generate_advisory_voice.py`는 macOS Yuna185wpm로 해당 문장만 재생성한다. 개인 녹음이 아니다.

## 자격과 순서

- READBACK: 최신 지시가 채택되고 필수 복창 항목이 모두 확인 가능한 상태일 때, 현재 MISMATCH인 OPEN 발생 건을 같은 지시의 `복명복창 내용을 확인하세요` 문장으로 묶는다. 새 지시 등록부터 새 복창 확인까지 기존 설정 음성은 보류한다.
- SETTING: 현재 서버 field verdict가 MISMATCH이고 OPEN·미완료인 발생 건만 사용한다. 최초 설정5초 대기·판독 불가·stale에는 설정 오류 음성이 없다. 같은 지시 ALT+HDG 동시 미완료는 `고도와 방위 설정을 확인하세요`, 각각은 `고도 설정을 확인하세요`/`방위 설정을 확인하세요`다. 완료한 ALT가 계속 틀려 있어도 새 HDG만 안내한다. 부분 ALT 지시 교체로 기존 HDG 발생 건·완료 상태를 초기화하지 않는다.
- CAMERA: 확인된 DISCONNECTED에서 장치 발생 건을 생성하고 즉시 `카메라 연결을 확인하세요`. 추가5초 대기 없음. AVAILABLE health만으로 종료하지 않으며 발생 시각 뒤 새 frame_id/관측 시각의 최신 프레임을 받아야 복구한다. 숫자 판독 불가여도 영상 자체 복구와 구분하고 복구 음성은 없다.
- VISIBILITY: 명시적 `roi_occluded` 사유의 최신 관측만 계기판 가림으로 인정한다. generic blank_roi·타임아웃·low quality를 가림으로 추측하지 않는다. 화면은 즉시, 같은 연속 발생 건의 탐지 시각부터5초 후 `계기판이 보이도록 해주세요`. stale 상태는 복구로 보지 않되 현재 가림을 확인할 수 없으므로 음성을 보류한다. 새 최신 읽기 가능한 관측으로 복구 후 다시 가려지면 새 발생 건·새5초다.
- 순서: CAMERA → 재생 시점이 된 VISIBILITY → READBACK → SETTING. 가림5초 전에는 이미 유효한 방위 안내를 기다리게 하지 않는다. 서버 claim도 현재 첫 후보만 허용한다. 첫 문장 완료와 둘째 문장 중단은 별도 기록한다.
- 같은 OPEN/장치 발생 건의 `voice_completed_at`은 끝까지 재생한 결과를 서버가 접수한 때만 설정한다. 값·관측 ID·렌더 변경으로 다시 말하지 않는다. 새 유효 관측에 의한 해결·새 지시 대체·비행 종료·현재 보류 전환으로 자격이 없어지면 이전 문장을 재생하지 않는다. 해결 후 재불일치는 기존 Incident가 새 occurrence_id를 만든다.

운용용 오차/심각도 임계값은 정해지지 않았다. 임의 경고 단계·강한 경고음·비상 판단은 구현하지 않는다. 불확실/장애는 수치 오류로 승격하지 않는다. 설정값 자동 변경은 없다.

## API·저장

GET `/api/v2/flights/{flight_id}/state`의 `voice`:

- version1, candidates(순서대로), inputs, active_attempt, episodes, history(최근50재생 시도).
- candidate: candidate_id(문구+정렬한 발생 건 ID의 안정 해시), phrase_key, text, occurrence_ids, instruction_id, asset_url.
- episodes: CAMERA/VISIBILITY의 occurrence_id·detected_at·voice_completed_at. device 발생 건은 수치 오류 Incident와 구분한다.
- attempt: 위 후보+attempt_id/status/started_at/lease_until/cancel_requested/finished_at. PLAYING은 예약/재생 진행이며 청취 완료가 아니다. GET의 lease_expired는 현재 예약 만료 여부를 보여주며 DB를 쓰지 않는다.

POST `.../voice/claims` `{attempt_id, candidate_id}` →201. 트랜잭션 안에서 최신 판정·후보·입력·현재 예약을 다시 검사한다. 현재 첫 후보가 아니거나 입력/다른 예약이 있으면409 INVALID_SEQUENCE. 같은 attempt_id/후보는 기존 결과, 다른 후보는409 ID_CONTENT_CONFLICT. 종료 비행409. 한 비행에 예약은 하나다. 예약10초는 재생 제어용 제한이며 운용 경고 임계값이 아니다.

POST `.../voice/attempts/{attempt_id}` `{status: COMPLETED|INTERRUPTED|FAILED}` →200. 같은 terminal 상태 재전송은 동일 결과, 다른 terminal 상태409, 다른 비행/없는 시도404. 서버 최신 자격이 없거나 종료된 문장은 CANCELLED, 중단/실패/만료는 완료가 아니다. COMPLETED만 연결된 발생 건의 voice_completed_at을 바꾼다. 만료 후 지연된 완료 보고는409 또는 취소이며 정상 완료로 승격하지 않는다. 비행 종료 뒤에도 기존 시도의 중단 보고를 허용한다.

POST `.../voice/inputs` `{event_id, token, kind: ATC|PILOT|SIMULATION|EVIDENCE, action: BEGIN|END}` →200. 같은 event_id/내용 재전송은 동일 receipt, 내용 충돌409. ATC/PILOT 동시 입력과 ATC/PILOT token 중 새 EVIDENCE 입력은409로 차단하며 예약하지 않는다. BEGIN은 현재 안내에 중단 요청을 표시하고 모든 안내 claim을 억제한다. END는 같은 token/kind를 닫는다. ATC token은 재생·수음 여유 시간 전체를 포함해야 한다. 자동 타이머로 입력 완료를 추정하지 않는다. 입력 종료 응답을 잃으면 같은 event_id로 재시도한다. 새로고침 후에도 서버 token과 종료 버튼이 남는다.

strict DTO는 추가 필드·임의 result/resolve/status를422로 거부한다. 기존 ContractErrorV2 code를 사용한다. SQLite BEGIN IMMEDIATE/기존 row lock으로 직렬화하고 revision·VOICE_CLAIM/VOICE_INPUT/VOICE_RESULT·VOICE_POLICY_CHANGED Trace와 JSON 상태를 같은 트랜잭션에 저장한다. DB commit 실패는 모두 rollback한다. 미디어/원본 DB 구조 변경은 없으며 기존 비행 JSON은 최초 갱신 때 voice를 초기화한다. history 응답은50개지만 원본 JSON/Trace 보관 수명주기는 SPEC-008 범위다.

## 브라우저·입력 어댑터

`음성 안내 켜기`의 사용자 동작에서 AudioContext.resume을 수행한다. 활성 문장 하나만 소유하며 실제 source.onended 뒤 COMPLETED를 보낸다. stop은 onended를 분리한 뒤 동기 stop해 중단을 완료로 세지 않는다. 로딩/디코딩 뒤에도 세대·연결·입력·lease 여유를 확인해 늦은 응답이 음성을 시작하지 못하게 한다. 예약 응답 전체 왕복 시간과150ms 여유를 뺀 제한 내에 파일 전체가 재생될 때만 시작한다. 해당 기한 전에 stop 타이머를 설정한다.

자동재생 차단·파일/디코딩 실패·AudioContext suspend는 `음성 사용 불가`와 명시적 다시 켜기로 처리한다. 실패를 완료로 표시하지 않는다. 결과 저장 응답 유실은 동일 attempt/status로 재전송하고 미확정 동안 다음 claim을 시작하지 않는다. 서버 단절/새 지시/현재 자격 소실은 재생을 중단한다. 페이지 종료/장애로 보고를 못 하면 다음 command의 서버 lease 만료 처리로 INTERRUPTED가 된다.

실제 입력 구현자는 `audioFocus.begin('ATC'|'PILOT', startCallback)`을 사용한다. 이 호출은 안내·근거 음성을 **동기 중단한 뒤** 서버 입력 허가를 요청하고 성공했을 때만 callback을 호출한다. 차단/실패에는 실제 입력을 시작하거나 예약하지 않는다. 끝나면 `audioFocus.end(input)`을 호출한다. 접수된 BEGIN 뒤 callback 시작 실패는 자동 END로 정리하며 END 저장 실패 때만 보류 token을 유지한다. callback이 일부 시작한 실제 장치의 취소/실패 정리와 ATC tail 완료는 입력 어댑터 책임이다. 원격 생산자가 API만 호출하고 이 어댑터를 건너뛴 경우 현재 UI의 갱신 주기(1초 poll+통신)에 따라 중단되므로 즉시 로컬 오디오 우선순위를 보장하지 않는다. 실제 PTT/STT는 SPEC-004에서 이 어댑터와 연결해야 한다.

패널의 원본 음성도 EVIDENCE token을 열어 안내와 겹치지 않는다. native play 요청에서 일단 pause→안내 stop→서버 token→사용자 재생을 이어간다. pause/end/error/패널 닫기/새 선택은 token을 닫고, ATC/PILOT 시작은 원본 음성을 우선 중단한다. 저장 실패 시 안내를 보수적으로 계속 보류하며 종료 재확인 버튼을 제공한다. BEGIN 응답 유실 후 END409이면 GET으로 해당 token 부재가 확인된 경우에만 로컬 보류를 푼다.

UI의 `입력 우선순위 모의 시험`은 입력 token만 주입한다. 녹음·ASR·관제 원본 재생을 구현한 것으로 표시하지 않는다. 실물 스피커 출력·마이크 재유입/잔향·실카메라 가림/분리·실제 모의 단계 신호·다른 브라우저/기기 인수는 별도다. 복구 음성·운용 강도 임계값은 추가하지 않는다.
