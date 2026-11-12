# 고도·방위 규칙 보완과 같은 녹음의 재시험

관제용 Whisper의 기존 전사를 바꾸지 않고 숫자 표현을 처리하는 범위를 확장했다. 기존 음원과 전사를 고정했으므로 아래 차이는 후단 BERT+규칙의 변경 결과다. STT 재학습·재전사·호출부호 변경은 수행하지 않았다.

## 변경한 처리

| 입력 예 | 새 숫자 후보 | 적용 범위 |
| --- | --- | --- |
| `FL80`, `FL 80`, `flight level eight zero` | 8,000ft | 명시 FL 단위와2/3자리 숫자 |
| `flight level three hundred` | 30,000ft | one~nine hundred의 완전한 백 단위 표현 |
| `heading three six zero`, `heading 360` | 0° | 음성의 명시 방위360만 북쪽0으로 변환 |
| `heading ah two seven zero` | 270°·확인 필요 | heading 바로 뒤 단일 ah/uh/um과 완전한3자리 숫자 |

북쪽의0/360 표기는 [FAA 설명](https://www.faa.gov/air_traffic/publications/atpubs/fs_html/chap3_section_3.html)을 확인했다. 이 원문 변환을 수용하도록 [음성 숫자 계약](../contracts/structure-rules.md)과 [공통 Observation 설명](../contracts/observation-v2.md)을 함께 수정했다. DTO·Schema·저장 값의 HDG 범위는0~359를 유지한다. wire값360은 여전히 거부하며, OCR/Cockpit의360값을 고치거나361/720/음수를 modulo 연산으로 보정하지 않는다.

`parse_command`는 숫자 후보를 반환하는 순수 파서다. 머뭇거림이 포함된 방위를 숫자로 읽더라도 `check_structure`는 `HEADING_HESITATION_REQUIRES_REVIEW`, BERT+규칙은 `HYBRID_HEADING_HESITATION_REQUIRES_REVIEW`를 남긴다. NER를 끈 서버 요청에서도 이 후보는 목표 지시로 채택되지 않음을 검증했다. 원본 전사·단어/문자 위치·엔티티 원문을 보존한다. `q`/`kel` 같은 단어, 숫자 중간 삽입, 여러 번의 머뭇거림, 잘린 숫자는 제거하지 않는다.

BERT 가중치와 기존 frozen baseline은 그대로이며 규칙 보완 단계만 `bert-hybrid-rules-v3` / `explicit-numeric-slots-v2`로 표시한다. compact `FL80`의 후보는 바로 앞 고도 명령 문맥에서만 추가해 호출부호 안의 비슷한 토큰을 대체하지 않는다. 원문의 조건/부정/추가 꼬리문구·숫자 상한·호출부호 검사는 유지한다. 앞 단계 호출부호 문맥 모드의 자동 채택 보류도 유지한다.

## 같은 자료로 비교한 결과

앞선 [PR #26](https://github.com/kkyo1130/Boeing_RADAR/pull/26)의 실제 녹음88개 정답/ASR176조건과 [PR #27](https://github.com/kkyo1130/Boeing_RADAR/pull/27)의 문맥 유무48조건을 재사용했다. 후자는 실제23개+합성무음1개이고20개가 앞의88개와 겹친다. 총224조건, 중복 제외 실제91개와 합성무음1개이며 신규 독립 시험112개가 아니다. 빈 무음2조건은 빈 후보로 처리하고 나머지222조건에서 실제 로컬 BERT 가중치로 재추론했다. 원음·전사·정답·소스·모델 해시를 고정해 입력 변경이 없음을 확인했다.

| 실제 녹음의 평가 항목 | 수정 전 | 수정 후 |
| --- | ---: | ---: |
| Whisper 전사: 고도 값 | 11/15 (73.3%) | **13/15 (86.7%)** |
| Whisper 전사: 방위 값 | 7/13 (53.8%) | **10/13 (76.9%)** |
| 정답 전사: 고도 값 | 12/15 | 14/15 |
| 정답 전사: 방위 값 | 12/13 | 13/13 |

이는 해당 필드가 있는 문장에서 숫자 후보 목록 전체가 맞은 수이며 자동 지시 승인율이 아니다. 방위 개선3개 중1개는360→0,2개는 ah 뒤 숫자 후보 복원이다. 후자2개는 검토 필요로 유지돼 자동 승인 성공으로 세지 않는다.

기존 TWR60개에는 목표 고도/방위가 없었고 수정 후에도 해당 숫자 오검출은0/60이었다. 호출부호는 모든224조건에서 예측 목록이 그대로였다. 전체 비교에서 기존에 맞힌 필드가 틀린 필드로 바뀐 회귀0건이다. 호출부호가 포함된 문장의 전체 필드 동시 정답은 ASR 고도4/15, 방위0/7로 그대로여서 숫자 개선만으로 항공기와 지시 연결이 해결된 것은 아니다.

문맥 유무 추가 시험의 목록 밖 항공기 중 방위3개는 두 조건 모두1/3→3/3으로 늘었다. 두 새 후보는 머뭇거림 보류 대상이다. 등록 데모3개 방위3/3, 고도3개3/3은 유지됐으며 호출부호·없는 호출부호 오검출·무음 결과도 변화가 없다. 이는 중복된 회귀 자료의 별도 확인이지 추가 독립 성능 증거가 아니다.

## 남은 실패

- `flight level three one zero one thousand or greater`: 뒤에 이어지는 숫자의 역할을 확정할 수 없어 전체 숫자 구문을 임의로 자르지 않았다. 정답 전사에서도 남는 고도1개다.
- `flight level obama zero zero`: STT가 one을 손상시켜 고도 후보가 없다. 이 단어를 one으로 추정하지 않았다.
- `heading q zero five zero`, `heading kel two nine zero`: 불명확한 단어를 삭제하지 않았다.
- `left heading two seven zero`가 `leveling two seven zero`로 바뀐 사례: 숫자가 보여도 사라진 heading 명령을 만들어 넣지 않았다.

고도2개·방위3개가 ASR 조건에서 여전히 실패한다. 이 자료는 이미 오류를 확인하고 수정에 사용한 개발/회귀 자료다. 특히 방위13개는 이전 평가 원본 그룹과 겹치는 진단 자료라는 앞선 제약을 유지한다. 전문가의 원음/정답 독립 검수는 없으며 이 점수를 실제 운항 정확도로 일반화하지 않는다.

## 검증·재현

- 실제 BERT/v7 포함 backend **623 passed**, skip0, 기존 Starlette TestClient deprecation 경고1. 신규 숫자 표현·원문 보존·0과 결측·범위 초과·미지원 꼬리·NER 비활성 서버의 보류 경계를 포함한다. 최초 집중 테스트에서 과거 FL30 거부 기대값1개가 새 계약과 충돌해 FL30 허용/FL3 거부로 갱신한 뒤 전체 통과했다.
- 공통 JSON Schema6종/fixture21개 검사 통과. 문형 fixture는24개이며 wire360 거부와 음성360→0을 분리한다. 스키마/DB migration 변경은 없다.
- 224조건 커버리지, 실제 원음·고정 전사·정답·가중치·소스 해시, 모든 채점·집계 재계산, 호출부호 예측 불변과 이전 정답 회귀0을 감사했다. [원문·전후 후보·숫자 변환·보류 사유·점수 JSON](evaluation/numeric-rules-replay-2026-11-10.json)에 보존한다.
- Python 컴파일·diff 검사 통과. 새 마이크 녹음, STT 재실행, 브라우저 전체 회귀, 외부 리뷰·항공 전문가 검수는 미실행이다. 서버 경계 시험은 주입 STT fixture이며 실측 BERT 재추론과 구분한다.

실행 위치는 작업 worktree 루트다. 선행 로컬 실험 자료가 필요하며 기존 replay 결과를 덮어쓰지 않는다.

```sh
OMP_NUM_THREADS=4 .venv/bin/python scripts/evaluation/replay_numeric_rules.py
.venv/bin/python scripts/evaluation/publish_numeric_rules.py
.venv/bin/python contracts/check_v2.py
# backend/에서 실제 모델 경로를 지정해 실행:
OMP_NUM_THREADS=4 RADAR_TEST_BERT_MODEL=/absolute/path/to/bert-hybrid-model \
RADAR_TEST_NER_MODEL=/absolute/path/to/v7-model ../.venv/bin/python -m pytest -q
```

자료 출처는 University of West Bohemia의 [UWB-ATCC](https://huggingface.co/datasets/Jzuluaga/uwb_atcc), Jzuluaga 배포 revision `1e8270beb8c1643c8735dddb7229fffb0e399f74`, CC BY-NC-SA4.0이다. 전사·파생 라벨/결과에 동일 출처·라이선스 조건을 유지한다. 실제 원음·모델·중간 결과는 ignored `.demo/numeric/`와 선행 worktree에 보존하고 Git에는 올리지 않는다.
