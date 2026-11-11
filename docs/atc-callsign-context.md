# 등록 호출부호를 참고하는 관제 STT

## 확보한 정보와 연결 범위

실시간 주변 항공기 API나 실제 비행계획 연동은 현재 RADAR에 없다. 기존 ATC 데모 설정과 SQLite 세션 스냅샷에서 아래 목록을 확인했다. 이번 기능은 운영 환경에서 이미 등록해 둔 호출부호 발음을 사용한다. 현재 확보된 것은 데모 등록 정보이며 실시간 관제 공역의 교통 목록이라고 표현하지 않는다.

| 등록 식별자 | 기존 등록 발음 |
| --- | --- |
| RADAR123 | Radar one two three |
| GWI7P | german wings seven papa |
| DLH1KK | lufthansa one kilo k |
| BAW820 | speed bird eight two zero / speedbird eight two zero |

원본은 선행 ATC 수음 작업의 `.demo/config.json`과 `.demo/radar.db`의 `v2_flight_contexts.callsign_registry`다. 설정 파일과 마지막 세 세션의 목록이 일치했다. RADAR123은 모의 항공기이며 나머지 세 개는 이전 실제 녹음 데모에 맞춰 등록한 정보다. 이번 시험의 정답으로 새 호출부호를 생성하거나 실시간 항공기 정보를 수집한 것은 아니다.

## 처리 방식

세션의 호출부호 등록 스냅샷 → 발음 목록 검증 → Whisper `hotwords` → 원문 전사 → 기존 BERT 호출부호·규칙 고도/방위 후보 추출 순서다. 사용 중인 faster-whisper의 로컬 `transcribe.py` API에서 hotwords가 참고 표현이며 prefix와 다름을 확인했다. 강제 출력 접두어, 인식 후 호출부호 치환, 정답 지시/숫자 삽입은 사용하지 않는다.

- 모든 등록 항공기의 발음을 같은 조건으로 전달하며 현재 비행기만 우선하도록 고르지 않는다.
- 발음 최대16개·전체400자, 영문/숫자/공백/하이픈만 허용한다. 초과/지원하지 않는 표현이면 전체 힌트를 끄고 사유를 반환한다. 애플리케이션에서 앞부분만 잘라 일부 항공기를 선택하지 않는다. 이번5개 발음은 모델에 그대로 전달했다.
- 모델 싱글턴에 호출부호를 저장하지 않고 매 요청의 세션 스냅샷을 사용한다. 새 설정 파일이 기존 세션을 소급 변경하지 않는다.
- 응답의 `stt_context`에 사용한 발음·등록 목록 해시·관측한 세션 revision·비활성 사유를 남긴다. 이 메타데이터는 현재 API 응답에 있으며 Observation DB의 별도 영속 필드로 추가하지 않았다.
- 호출부호 힌트 자체는 해당 항공기를 실제로 불렀다는 증거가 아니다. 문맥 모드는 `callsign_context_requires_review`로 자동 지시 채택을 보류한다. 정확도 검증 전에는 기존 자동 처리 경로의 기본 설정을 바꾸지 않는다.

서버의 ATC 파일/마이크 수음과 Pilot 복창 어댑터에 연결했다. 이전 CLI `produce_observation.py`에는 이번 기능을 추가하지 않았다. 관제용 Whisper 외에도 같은 로컬 어댑터를 쓰는 모델에서 기능은 사용 가능하지만 이번 실측은 관제용 모델에 한정한다.

## 비교 설계

같은 원음·관제용 Whisper 가중치·기본 안내문·영어·beam5·VAD·CPU int8 조건에서 hotwords 유무만 바꿨다. 서비스 LocalWhisper의 기존 temperature fallback 설정을 유지했으며 이전 PR #26의 temperature0 점수와 직접 전후 비교하지 않는다. 기존 BERT+규칙과 숫자 파서는 그대로 유지한다.

- 등록된 실제 녹음3개: 이전 데모 재시험이다. 발음 목록이 해당 녹음에서 미리 만들어졌으므로 독립 일반화 평가나 현장 선행정보 검증이 아니다.
- 목록 밖 호출부호12개: 이전 PR #26의 TWR6/고도3/방위3개를 seed20261112로 추출했다.
- 호출부호 없는 실제 녹음8개: 이전 TWR 정답에서 CALLSIGN 빈 목록인 모든 문장이다.
- 별도 합성 무음1개: 단어를 만들어내는지 검사한다. 실제 관제 녹음 수에 합산하지 않는다.

음원은 University of West Bohemia의 [UWB-ATCC](https://huggingface.co/datasets/Jzuluaga/uwb_atcc), Jzuluaga 배포 revision `1e8270beb8c1643c8735dddb7229fffb0e399f74`, CC BY-NC-SA4.0이다. 전사·파생 라벨/결과도 동일 출처·라이선스 조건을 유지한다. 관제용 모델은 `SingularityUS/ATC-whisper-turbo-v1`의 기존 로컬 변환 가중치다. 원음·모델은 Git 제외다.

비교 목록·정답·등록 설정·음원/가중치 해시를 추론 전에 `.demo/context/plan.json`으로 고정했다. 호출부호는 앞선 평가와 같은 숫자/NATO/공백 표기 정규화로 목록 전체 일치를 센다. 독립 전문가 검수와 새 현장 녹음은 수행하지 않는다. 모델 점수는 검증된 정답 확률이 아니다.

## 실측 결과

48회 비교 추론과 실제 모델을 사용하는 별도 ASGI 요청2회를 완료했다. 호출부호 추출은 숫자/NATO 표기 차이를 정규화한 뒤 목록 전체 일치로 계산했다.

| 자료 | 힌트 없음 | 등록 발음 힌트 사용 |
| --- | ---: | ---: |
| 등록된 데모3개: 호출부호 정확 추출 | 0/3 | 1/3 |
| 목록 밖 항공기12개: 호출부호 정확 추출 | 3/12 | 3/12 |
| 호출부호 없는8개: 올바르게 빈 목록 반환 | 6/8 | 6/8 |
| 합성 무음1개: 빈 전사/빈 후보 반환 | 1/1 | 1/1 |

등록 데모에서 `lufansa one kilo kilo`가 `lufthansa one kilo kilo`로 바뀌어1개를 맞혔다. `speedway eight six zero`는 `speedbird eight six zero`로 이름은 개선됐지만 정답820을860으로 듣는 오류가 남았다. `german wing seven papa`의 단수 wing도 두 조건 모두 그대로였다. 이름 일부 개선을 호출부호 전체 성공으로 세지 않는다.

목록 밖12개+호출부호 없는8개에서 등록 목록의 완전한 호출부호 표현을 삽입한 경우는 두 조건 모두0/20이었다. 작은 회귀 표본에서 관찰되지 않았다는 뜻이며 잘못된 항공기 연결이 불가능하다는 증거는 아니다. 특히 `ten five one`, 출발 절차 문장의 `antalia`를 BERT가 CALLSIGN으로 잡는2개 오검출은 여전히 남았다. 이들은 등록 목록의 호출부호와 일치하지 않는다.

숫자 후보는 두 조건에서 동일했다. 등록 데모의 방위3/3, 목록 밖 고도3/3·방위1/3이다. 이번 작업에서 숫자 규칙이나 BERT를 바꾸지 않았다. 전체 필드 일치는 등록 데모0/3→1/3, 목록 밖3/12→3/12이며 후보 추출 성공률이다. 서버의 엄격한 등록 발음 일치·조건 검사는 별도이므로 정규화 채점 성공을 항공기 식별/지시 채택 성공으로 표현하지 않는다.

실제 모델 ASGI 요청에서는 Lufthansa 원음이 `lufthansa one kilo kilo turn left heading three zero zero`로 전사되고 문맥 해시/발음 목록과 실제 BERT 후보가 반환됐다. 문맥 사용 결과는 확인 필요로 남아 목표값을 생성하지 않았다. 무음 요청도 빈 전사·약신호 사유·UNVERIFIED를 유지했다. 테스트용 ASR 응답을 주입하지 않았고, 새 마이크 수음이나 네트워크 HTTP 경로 시험은 아니다.

결론은 **등록 발음이 일부 항공사 이름 복원에는 도움이 됐으나 번호 오류와 호출부호 전체 정확도를 충분히 해결하지 못했다**는 것이다. 세 데모의 발음이 과거 해당 녹음에서 미리 등록된 점, 기존 회귀 자료와 작은 표본, 서비스의 temperature fallback을 포함한 단일 실행이라는 제약이 있다. 외부 현장 평가나 재학습 없이 일반적인 성능 향상을 주장하지 않는다. [고정 계획·전사·후단 후보·점수·API 결과](evaluation/callsign-context-2026-11-10.json)에 근거를 보존한다.

새 문맥 전용11개를 포함해 실제 BERT/v7 모델을 지정한 backend **571 passed**(skip0, 기존 Starlette deprecation 경고1). 발행 감사에서 계획/원음/설정/가중치/소스 해시,48개 조건별 결과, 채점 재계산을 확인했다. Python 컴파일·shell 구문·diff 검사도 통과했다. 외부 PR 리뷰·브라우저·새 마이크·실시간 교통 목록 연동은 미실행이다.

## 실행

기존 로컬 모델과 데모 등록 설정을 준비한 다음:

```sh
RADAR_WHISPER_MODEL=/absolute/path/to/whisper-atc-turbo-ct2 \
RADAR_NER_MODEL=/absolute/path/to/bert-hybrid-model \
RADAR_V2_CONFIG=/absolute/path/to/config.json \
scripts/run-context-backend.sh
```

이 launcher는 `RADAR_STT_CALLSIGN_CONTEXT=1`을 설정하고 기존 BERT+규칙 서버를 실행한다. `/api/demo/status`의 `callsign_context_enabled`와 음성 응답의 `stt_context`로 적용 여부를 확인한다. 기존 서버는 별도로 재시작해야 하며, 이번 실험은 다른 작업의 서버/DB를 교체하지 않는다.

```sh
.venv/bin/python scripts/evaluation/evaluate_callsign_context.py
.venv/bin/python scripts/evaluation/check_context_api.py
.venv/bin/python scripts/evaluation/publish_callsign_context.py
```

재현에는 선행 `atc-microphone-modes`, `atc-slot-evaluation`, `atc-unseen-whisper`, `atc-specialist-comparison`, `bert-hybrid-stt` 로컬 산출물이 필요하다. 실험 스크립트는 기존 결과를 덮어쓰지 않도록 검사한다. API 검증은 별도 로컬 DB와 ASGI 요청으로 실제 모델을 실행하며 새 마이크 수음이나 네트워크 HTTP 시험과 구분한다.
