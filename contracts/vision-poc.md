# Vision 결과 JSON — 1주차 PoC

이미지 한 장에서 선택 ALT·HDG를 읽은 값, 판독 실패 사유, 근거 이미지와 시각을 기록한다. 출력 파일은 `observation.json`이다.

SPEC-002-WI-01 중 Vision 로컬 결과 제안이다. 전체 공통 계약 확정이나 현재 서버 지원을 의미하지 않는다. 현재 인식기는 숫자 OCR이며 바늘·눈금·선택 마커 인식은 미구현이다. 실제 Cockpit 화면에서 선택값을 확인하는 검증도 아직 하지 않았다.

## 전체 구조

```text
observation.json
├── 실행/입력 정보: schema_version, source, input_mode, frame_id
├── 시각 정보: captured_at, processed_at, capture_time_known
├── 점수 정보: score_calibrated
├── fields
│   ├── altitude: 고도 인식 결과
│   └── heading: 방위 인식 결과
└── evidence: 전체 입력 이미지 위치
```

정상 예제는 [vision-readable.json](examples/vision-readable.json), 판독 실패 예제는 [vision-unreadable.json](examples/vision-unreadable.json)을 참고한다. v1 예제의 근거 경로는 설명용이다. v2 MCP 예제의 근거는 저장소의 실제 문서 자산을 가리키며 경로 기준은 저장소 루트다.

## 실행·입력 정보

| 필드 | 타입 | 의미·현재 값 |
| --- | --- | --- |
| `schema_version` | string | 로컬 결과 형식 버전. 현재 `vision-poc/1` |
| `source` | string | 입력 출처. 현재 `cockpit_image`; 이 문자열이 실제 Cockpit 촬영을 증명하지는 않음 |
| `input_mode` | string | 현재 `still_image` — 이미지 한 장. 실카메라/영상 모드 아님 |
| `frame_id` | string | 실행마다 새 UUID. 같은 이미지를 다시 실행해도 다른 ID이며 입력 중복 검출 ID는 아님 |
| `captured_at` | string 또는 null | 실제 촬영 시각, 시간대가 포함된 입력을 UTC ISO 8601로 변환. 시각 미상은 null |
| `processed_at` | string | 두 필드의 처리를 마친 시각. UTC ISO 8601 |
| `capture_time_known` | boolean | 촬영 시각을 입력받았는지. 시각의 진위를 검증했다는 의미는 아님 |
| `score_calibrated` | boolean | 현재 false. 모델 점수를 실제 정확도/확률에 맞게 보정하지 않았음 |
| `fields` | object | `altitude`와 `heading`의 개별 결과 |
| `evidence` | string | 전체 이미지 복사본 `frame.png`의 로컬 파일 경로. 서버 URL 아님 |

촬영 시각은 CLI의 `--captured-at`으로 제공한다. 생략하면 `captured_at=null`, `capture_time_known=false`이다. 파일 수정 시각·처리 시각을 촬영 시각으로 대체하지 않는다. 오래된 이미지인지 판단하는 freshness 정책은 아직 없다.

## ALT·HDG 개별 결과

`fields.altitude`와 `fields.heading`은 아래 구조를 각각 사용한다.

| 필드 | 타입 | 의미·예시 |
| --- | --- | --- |
| `value` | integer 또는 null | 해석한 숫자. 고도 3000, 방위 270. 판독 실패 시 null |
| `unit` | string | 고도 `feet`, 방위 `degrees`. 입력이 FL이면 숫자 × 100으로 feet 변환 |
| `raw_text` | string | OCR이 반환한 글자. 예: `"000"`. 결과가 없거나 OCR 실행 실패면 빈 문자열 |
| `model_score` | number 또는 null | OCR 점수 0~1. 결과가 없거나 유효하지 않으면 null. 여러 OCR 결과가 있으면 최소 점수이며 현재 여러 결과는 형식 오류로 거부 |
| `reason` | string 또는 null | 실패 사유. 검사 통과 시 null |
| `roi` | integer[4] | 숫자를 읽은 영역 `[left, top, right, bottom]` |
| `contrast_stddev` | number | ROI를 그레이스케일로 변환한 밝기의 표준편차. 빈 영역 확인용; 정확도/일반적인 흐림 점수 아님 |
| `evidence` | string | 잘라낸 ROI 이미지의 로컬 경로. `altitude.png` 또는 `heading.png` |

ROI는 EXIF 방향을 적용한 원본 이미지의 픽셀 좌표이며 원점은 좌상단이다. 오른쪽·아래 경계는 제외한다. `[30, 100, 380, 210]`은 너비 350, 높이 110 픽셀 영역이다. 이미지 크기가 설정과 다르면 자동 축소/확대하지 않고 입력 오류로 종료한다.

HDG는 0–359이다. `"000"`은 `value=0`이며 누락값이 아니다. 360을 임의로 0으로 바꾸지 않는다. OCR의 O를 0으로 바꾸거나 누락된 숫자를 추측해 채우지 않는다.

`model_score=1.0`은 정확도 100%를 의미하지 않는다. `reason=null`도 실제 정답이나 비행 상태의 정상 판정을 보장하지 않는다. 현재 검사에서 거부할 사유를 찾지 못했다는 의미다.

## 실패 사유

| `reason` | 현재 구현에서의 발생 조건 |
| --- | --- |
| `blank_roi` | 영역의 밝기 표준편차가 1 미만. 전체 가림/빈 영역 등을 의심하여 OCR을 실행하지 않음 |
| `no_text` | OCR 실행은 성공했지만 글자 결과가 없음 |
| `invalid_score` | 모델 점수가 유한한 0~1 숫자가 아님. model_score도 null로 처리 |
| `invalid_format` | OCR 결과가 여러 개이거나 글자가 숫자 1~5자리 형식에 맞지 않음 |
| `low_model_score` | 점수가 설정의 minimum_model_score 미만. 현재 합성 설정 0.5는 실험값 |
| `out_of_range` | 방위 숫자가 359를 초과함 |
| `ocr_unavailable` | OCR 바이너리/실행/20초 timeout/응답 해석 등에 실패함 |

예를 들어 고도 영역이 전부 가려지면 다음처럼 기록한다. 나머지 필드는 계속 포함된다.

```json
{
  "value": null,
  "raw_text": "",
  "model_score": null,
  "reason": "blank_roi",
  "unit": "feet"
}
```

한 필드의 실패가 다른 필드를 무조건 실패로 만들지는 않는다. ALT가 null이어도 HDG는 읽은 값을 유지할 수 있다. 부분 가림·흐림·반사가 반드시 특정 사유로 탐지되는 것은 아니며, 숫자로 읽힌 오답은 현재 검사에서 통과할 수 있다.

파일 없음·잘못된 이미지 크기·ROI/시각 설정 오류는 위 reason 목록으로 표현하지 않는다. CLI가 오류를 출력하고 종료 코드 2로 종료한다. 필드별 실패는 JSON으로 반환하며 CLI 종료 코드가 0이어도 모든 필드가 판독됐다는 뜻은 아니다.

## 저장 파일과 확인 방법

`--output-dir` 아래 실행 UUID별 폴더에 저장한다.

```text
<output-dir>/<frame_id>/
├── frame.png          전체 입력 이미지
├── altitude.png       고도 ROI
├── heading.png        방위 ROI
└── observation.json   이번 인식 결과
```

경로는 실행에 사용한 output-dir에 따라 상대 또는 절대 경로가 된다. 상대 경로는 실행 당시 작업 디렉터리 기준이며 JSON 파일 디렉터리 기준이 아니다. 현재 예제 명령은 저장소 루트에서 실행한다. 실제 이미지에서 읽은 위치를 확인하려면 ROI 파일을, 값과 실패 이유를 확인하려면 JSON을 연다. 실행 방법은 [Vision README](../vision/README.md)를 참고한다.

## 현재 서버와의 차이

현재 backend Observation은 altitude/heading/confidence를 필수로 받으며 null·필드별 점수·근거를 지원하지 않는다. 이 JSON을 현재 endpoint에 직접 전송하지 않는다.

백엔드 담당과 flight_id/clearance_id 연결, 부분값, freshness, health, 근거 저장·참조, 필드별 점수 계약을 맞춘 뒤 서버 연동한다. 누락값을 0으로 채우거나 임의의 단일 confidence로 합치지 않는다.

이 결과에는 관제 지시/Readback과의 비교나 NORMAL/MISMATCH/UNVERIFIED 판정이 없다. 최종 판단은 서버 담당이다. 현재 상태를 표시하는 바늘과 선택 목표값을 구분하는 것은 실제 화면을 정한 뒤 확인해야 한다.

## 사용자 지정 MCP 속도 관측 확장

속도 ROI가 없는 기존 설정은 `vision-poc/1`과 ALT/HDG 두 필드를 유지한다. `speed`가 있는 설정은 `vision-poc/2`로 출력하고 `fields.speed` 및 `speed.png`를 추가한다. v1 소비자는 새 필드를 지원한다고 가정하지 않는다. 현재 v2 예제는 [mcp-observation.json](examples/mcp-observation.json)이며 방위 창 전처리 후 세 필드가 판독된 결과다.

speed는 같은 필드 구조를 사용한다. unit=knots이면 value는 정수이고 숫자 1~3자리만 받는다. unit=mach이면 value는 소수이며 `.780`, `0.78` 같은 소수점 뒤 2~3자리 형식을 받는다. IAS와 Mach를 서로 변환하지 않는다. 속도 모드는 설정 파일로 지정하며 자동 식별이나 실제 화면 모드 변경 검증은 아직 없다. 이 검사는 표시 형식 검사이며 해당 기체의 운용 가능 속도를 판정하지 않는다.

v2에서 `fields`는 altitude/heading/speed이며 speed evidence는 `speed.png`이다. speed 선택 기능을 넣은 기존 설명의 value 타입은 integer 또는 float 또는 null로 확장된다. 방위 0–359·고도 FL 변환 규칙은 유지한다. 속도까지 지원하는 서버 검증·관제 비교는 미구현이다.

## 선택 OCR 전처리 정보

작은 숫자 창에만 전처리를 적용할 수 있다. 설정 파일의 전체 `ocr_preprocessing`을 기본값으로 사용하고 개별 `heading.ocr_preprocessing` 등이 있으면 해당 필드 설정을 우선한다. 빈 object는 해당 필드 전처리를 끈다. `scale`은 정수 1~8, `grayscale`은 boolean이다. 현재 MCP 설정은 방위 창에만 grayscale=true, scale=4를 적용한다.

전처리를 사용한 필드에는 다음 항목이 추가된다. 기존 `evidence`와 `roi`는 원본 이미지의 영역을 유지한다.

| 필드 | 의미 |
| --- | --- |
| `ocr_evidence` | OCR에 실제 전달한 `<field>-ocr.png` 경로 |
| `ocr_preprocessing` | grayscale/scale의 적용값. 크기 변경에는 Lanczos 보간 사용 |

`contrast_stddev`는 전처리 이전 원본 ROI에서 계산한다. 전처리 설정이 없으면 기존처럼 원본 ROI를 OCR에 전달하고 위 두 추가 항목은 없다. 이미지 확대는 새로운 정답 정보를 만드는 것이 아니며 원본 판독 실패/범위 검사는 유지한다.
