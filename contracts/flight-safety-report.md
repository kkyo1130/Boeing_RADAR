# Flight Safety Report / flight-safety/1

기존 `radar-report/2`의 `safety` 추가 필드다. 지시/검증의 원본은 기존 v2 입력·Trace·Incident이며 새 판정 엔진을 만들지 않는다.

## API와 권한

- `POST /api/v2/flights`: 기존 응답을 유지하고 HttpOnly, SameSite=Strict 브라우저 capability cookie를 설정한다. HTTPS에서는 Secure. DB에는 SHA256만 저장하며 Trace/JSON/PDF에 비밀을 넣지 않는다.
- `GET /api/v2/flights/{id}/report`, `report.json`, `report.pdf`: 생성 브라우저 소유권이 일치해야 한다. ID만 알거나 다른 브라우저 cookie이면403. 사용자 로그인/조직 권한 시스템은 아니며 운영 API 전체의 인증을 대신하지 않는다.
- `report.pdf`: 종료 전409, 종료 후application/pdf 및 attachment. 파일명 `Flight_Safety_Report_<UTC 종료일>.pdf`. PDF 제목은 `Flight Safety Report`이며 제품 브랜드 머리글과 작성자 표기는 넣지 않는다. Cache-Control no-store.
- 이미 종료된 리포트는 V2Report의 고정 데이터를 사용한다. 과거 형식은 고정 관측/Trace에 대해서만 읽기 전용 projection을 추가한다. 재조회로 집계나 생성 시각이 바뀌지 않는다.
- 기존 소유권 없는 세션을 ID로 자동 획득할 수 없다. 로컬 DB 관리자만 `python -m app.services.reports.access --flight <ID>`로 접근 코드를 발급한다. 이미 소유권이 있으면 재할당을 거부한다. `/report?flight=<ID>`의 접근 코드 양식은 `POST /api/v2/flights/{id}/report-access`에 비밀을 본문으로 보내 검증 후 cookie를 설정한다. URL·로그·공유 메시지에 코드를 넣지 않는다. 한 브라우저의 capability 변경은 기존 다른 세션의 접근을 바꿀 수 있다.

## 집계 정의

- instruction_count: 유효하게 적용된 ATC input의 고유 instruction ID 수. 거절/미적용 입력은 원본 관측에 남기되 유효 지시 건수에 포함하지 않는다.
- normal_instruction_count: 해당 지시의 필수 복창·호출부호·설정이 모두 NORMAL인 저장된 검증이 한 번 이상 있고 오류 사건은 없었던 지시 수. 현재 운항의 안전 인증이 아니다.
- error_instruction_count: 오류를 가진 고유 지시 수. 사건 수와 구분한다. 한 지시에서 ALT/HDG 별도 오류가 있으면 사건은2, 오류 지시는1이다.
- unverified_instruction_count: 오류도 없고 전체 일치 완료 기록도 없는 유효 지시 수. 누락/오래됨/품질 저하를 정상으로 세지 않는다.
- incident_count: 고유 occurrence_id 수. 재전송·반복 경고는 새 사건이 아니다. 해결 후 재발하여 새 occurrence ID를 받은 오류는 새 사건이다.
- resolved_count: 기존 서버의 RESOLVED 및 resolution_evidence가 저장된 사건만 인정한다. 기존 정책대로 Readback 오류 해결과 전체 Cockpit 완료를 구분한다.
- unresolved_count: 모든 미해결 사건(OPEN/미해결 종료/대체 포함). superseded_count는 그중 지시 대체로 닫힌 사건 수이며 수정 완료가 아니다.
- correction_rate: resolved_count / incident_count. 오류가 없으면 null(해당 없음).
- classification: READBACK, SETTING 별 사건 수와 전체 사건 대비 비율. 기존 검증 정책이 설정 오류 판정을 보류하면 리포트가 설정 오류를 새로 만들지 않는다.

## 이력

safety.timeline은 저장 sequence 순서의 입력·검증·Incident·음성 안내·종료 기록이다. UTC 시각, 연결된 instruction/occurrence ID, 원본 인식값과 validity, 비교 expected/actual/result/reason, 해당 시점 오류 상태·경고 재생 완료·해결 시각을 제공한다. 입력 품질이 낮은 숫자는 validity/UNVERIFIED와 함께 표시한다.
Correction Trace는 저장 이벤트로 DETECTED/WARNED/CORRECTING/RESOLVED/UNRESOLVED를 표현한다. WARNED는 음성 재생 COMPLETED 기록만 사용한다. 후보/PLAYING/실패/중단을 재생 성공으로 표현하지 않는다. UI 경고를 사람이 보았는지, 실제 스피커로 들었는지는 미수집이다.
새 관측·재검증 이벤트는 CORRECTING을 만들 수 있으며 UNVERIFIED는 성공이 아니다. 종료 때 미해결은 UNRESOLVED. 경고가 사라졌거나 지시가 대체된 사실만으로 RESOLVED를 만들지 않는다.

## 출처·요약

원본 evidence_unavailable_reason에 fixture가 있으면 FIXTURE_PRESENT 표시. 다른 입력은 STORED_INPUTS_UNVERIFIED_ORIGIN이며 실제 카메라 검증 완료라고 주장하지 않는다. 이 기능은 fixture를 새로 생성하거나 실제 세션에 데모 입력을 추가하지 않는다.
AI 기본은 미설정으로 규칙 기반 요약을 제공한다. 선택적으로 `RADAR_REPORT_AI_URL`, `RADAR_REPORT_AI_TOKEN`을 설정하면 사실 집계, 사전 검증 문장, 최대100개 이벤트 종류/시각과 facts_digest를 JSON POST한다. 제공자는 `{"fact_ids":["instructions","errors","corrections","scope"],"facts_digest":"요청의 digest"}`를 반환해야 한다. 순서는 변경 가능하지만 정확한 전체 ID집합/digest만 허용하며 문장·숫자·판정은 서버가 제공한 사실 문장만 출력한다. 자유 생성 문장은 표시하지 않는다. AI_ASSISTED_FACTS와 RULE_BASED를 구분한다.
Timeout/형식 오류/누락/지어낸 주장/HTTP 실패는 규칙 요약으로 대체한다. AI 오류 때문에 종료나 PDF가 실패하지 않게 한다. 외부 제공자는 선택사항이며 기본 실행에서 외부 호출하지 않는다.
