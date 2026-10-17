# 실시간 근거 패널·사용자 확인 계약

SPEC-006-WI-02의 v2 실행 계약이다. 서버 [수신](receiving-v2.md)·[판정](validation-v2.md)·[Incident](incidents-v2.md)를 유지한다. 값/단위/불일치/보류는 패널 열기 전에도 표시한다. 근거 열람·사용자 확인은 새 입력 수정의 선행 조건이나 오류 해결이 아니다.

## 선택과 조회

GET `/api/v2/flights/{flight_id}/evidence/{observation_id}?instruction_id=...&stage=READBACK|SETTING&field=ALT|HDG|CALLSIGN`

현재 서버 field verdict의 flight/instruction/stage/field/observation ID가 모두 일치해야 한다. 다른 지시·다른 비행·새 관측으로 교체된 선택은409 CONTEXT_MISMATCH, 원본 미저장은404, query 형식 오류는422다. 원본 샘플의 품질이 낮거나 판독 불가여도 근거 자체를 정상값으로 승격하지 않고 조회한다. GET은 상태/Trace를 쓰지 않는다.

응답은 schema_version2·선택 ID·verdict와 groups.ATC/OBSERVED다. 각 group은 원본 observation_id/observed_at/time_reason/source/transcript, 선택 필드 reading(호출부호는 callsign), applied/intake_reason, assets와 evidence_unavailable_reason을 담는다. ATC는 해당 필드 target의 source_observation_id로 선택하며 최신 ALT 지시를 기존 HDG의 근거로 섞지 않는다.

assets는 field=null 또는 선택 field의 EvidenceRef만 노출한다. evidence_id/kind/field/roi, 같은 출처 content URL 또는 null/unavailable_reason을 반환한다. 원본 ref의 임의 URL·로컬 절대 경로는 브라우저에 실행 가능한 src로 전달하지 않는다. TRANSCRIPT는 텍스트로 표시하고 HTML로 실행하지 않는다. 모델 점수는 보정된 확률/검증된 정확도가 아니며 입력 품질과 구분한다.

## 근거 파일

개발자가 `RADAR_EVIDENCE_ROOT`를 신뢰하는 근거 디렉터리로 지정한다. 생산자는 `ref="media:relative/path.png"` 같은 상대 참조를 제공한다. root 미설정·누락·범위 밖/symlink 탈출·절대/.. 경로·HTTP/file/data 참조·읽기 불가·지원하지 않는 파일은 원본 근거를 열 수 없는 이유로 표시한다. 서버가 원격 URL을 대신 요청하지 않는다.

허용 형식은 PNG/JPEG/WebP 이미지와 WAV/MP3/OGG 음성, 파일당 최대20MiB다. FRAME/ROI는 이미지, AUDIO는 음성 형식이어야 한다. SVG/HTML 등 active content는 제공하지 않는다. ROI 파일은 생산자가 제공하는 해당 ROI 이미지이며 좌표를 함께 표시한다. 서버가 다른 프레임을 임의로 잘라 대체하지 않는다.

GET `/api/v2/flights/{flight_id}/evidence/{observation_id}/media/{ATC|OBSERVED}/{evidence_id}?instruction_id=...&stage=...&field=...`도 같은 선택 문맥을 다시 검사한다. metadata에서 받은 URL이어도 새 지시/관측으로 대체됐으면409다. 파일 불가/종류 충돌은404 ContractErrorV2이며 FileResponse는 no-store·nosniff를 설정한다. 표준 media controls/Range 동작을 사용하고 원본 음성은 사용자 조작으로만 재생한다.

브라우저는 API가 제공한 같은 flight/observation의 상대 media URL만 사용한다. 파일이 없거나 재생이 차단/실패하면 정상 완료로 표시하지 않고 이유를 알린다. 패널 닫기·선택 변경·새 관측·서버 단절 시 플레이어를 제거/정지한다. 새 관측에는 과거 자료를 자동 재연결하지 않는다.

## 명시적 열람·확인 기록

POST `/api/v2/flights/{flight_id}/interactions`

```json
{
  "event_id": "client-generated-unique-id",
  "instruction_id": "INS-example",
  "observation_id": "obs-example",
  "stage": "READBACK",
  "field": "ALT",
  "action": "ACKNOWLEDGED"
}
```

action은 ACKNOWLEDGED 또는 EVIDENCE_OPENED다. Identifier/enum은 strict DTO를 따르며 추가 임의 result/resolve 값은422다. 현재 활성 비행·현재 선택 문맥을 검사하고 ACKNOWLEDGED는 현재 MISMATCH/UNVERIFIED에서만 허용한다. EVIDENCE_OPENED는 패널 자료를 연 사실이며 실제 미디어 재생 완료를 뜻하지 않는다. 종료 비행/오래된 선택/정상 항목 ACK는409다.

첫 기록201, 같은 비행의 같은 event_id·동일 내용 재전송200(기존 접수 시각/Trace ID 반환), 다른 내용은409다. 클라이언트는 응답 유실 재시도에 같은 ID를 사용한다. 서버는 UTC 시각·원본 요청·당시 verdict·연결 가능한 OPEN occurrence_id를 USER_ACKNOWLEDGED/EVIDENCE_OPENED Trace에 저장한다. 기존 flight writer 트랜잭션으로 revision/Trace를 원자 저장하며 실패 시 rollback한다. 현재 프로토타입은 별도 로그인 사용자 신원 인증을 제공하지 않는다.

응답은 schema_version/event_id/recorded_at/action/observation_id다. NORMAL/RESOLVED/음성 완료 필드를 포함하지 않는다. targets/current/validation_memory/Incident 상태·notified_at/voice_completed_at은 변경하지 않는다. 파일이 없어도 확인/새 수정 입력을 막지 않으며, 확인하지 않고 새 Pilot 구간이나 카메라 관측을 보내도 기존 서버 재검증이 수행된다.

실제 PTT 녹음·STT 제공자 연결은 SPEC-004, 안내 음성/교신 우선순위·재생 완료 이력은 SPEC-006-WI-03, 원본 수명주기/리포트는 SPEC-008에서 추가한다. 이 WI는 화면의 수정 안내와 v2 생산자 수정 경로를 검증하며 마이크 녹음/ASR을 구현한 것으로 표시하지 않는다.
