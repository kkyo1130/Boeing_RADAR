# 같은 실제 관제 음원으로 STT 모델 비교

이 실험은 기존 Whisper base.en 대신 다른 사전학습 모델을 사용하면 현재 RADAR의 실제 관제 인식이 나아지는지 확인한다. 재학습이나 운영 모델 교체는 하지 않았다. 모델만 바꾸는 기본 비교와, 일반 관제 안내문을 제거하는 후속 진단을 구분한다.

## 비교 조건

- Mac: Apple M4, 메모리16GiB, 논리 코어10개. CTranslate2 CPU int8·4 threads로 모델별 별도 프로세스에서 순차 실행했다. Apple GPU/MLX의 최고 속도를 측정한 실험이 아니다.
- 모델: 기존 base.en, [small.en](https://huggingface.co/Systran/faster-whisper-small.en), [medium.en](https://huggingface.co/Systran/faster-whisper-medium.en), [large-v3-turbo](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo). 모두 Whisper 계열이며 네 가지 서로 다른 ASR 아키텍처 비교는 아니다. 공개 CTranslate2 변환본은 모델 카드에서 확인했고 source revision·가중치 해시를 기록했다.
- 입력: 앞선 ATC 수음 시험에서 선택한 UWB-ATCC 관제사 발화3개의 원음과, 당시 Mac 스피커→마이크로 실제 녹음했던 WAV3개. 이번에는 같은 WAV를 디스크에서 재처리했다. 새 마이크 녹음이나 새 실제 교신6개가 아니다. 초기 음소거 때의 녹음은 제외했다.
- 공통 설정: 영어, beam5, VAD, 이전 문맥 conditioning off, 기존 일반 관제 용어 안내문. 등록 호출부호·BERT·규칙·품질 임계값을 고정했다. 정답 전사문·특정 호출부호·기대 방위는 ASR에 전달하지 않았다. 실험용 임시 DB와 TestClient를 사용했고 실제 운영 상태·모델 설정을 변경하지 않았다.
- 출처: [UWB-ATCC / Jzuluaga](https://huggingface.co/datasets/Jzuluaga/uwb_atcc), University of West Bohemia, CC BY-NC-SA4.0. source revision은 `1e8270beb8c1643c8735dddb7229fffb0e399f74`. ATCO2는 사용하지 않았다.

세 발화는 이미 오류 분석에 사용했고 원 데이터의 train split이다. 독립 평가자료가 아니며, 이번 수치로 전체 관제 교신의 정확도나 일반화 성능을 추정하지 않는다. 데이터셋 정답 전사도 수동으로 수정하지 않았다. 특히 Lufthansa 발화 정답의 마지막 `k`와 모델이 출력하는 `kilo` 차이는 아래 단어 오류율에 포함된다.

## 채점 방법

단어 오류율(WER)은 정답 단어 수 대비 삽입·삭제·대체 수로 계산하며 낮을수록 좋다. 아래 표는 대소문자·문장부호를 정리하고 숫자 표기만 맞췄다. 예를 들어 `080`은 `zero eight zero`로 비교하지만, `Spirit`을 `Speedbird`로 바꾸거나 `oh`를 `zero`로 고치지는 않는다. 오류율을 빼서 모델의 검증된 정확도로 표현하지 않는다. 숫자 표기를 그대로 둔 lexical WER도 JSON에 별도로 보존한다.

각 조건은 정답31단어, 발화3개뿐이다. 속도는 파일별1회 실행에서 측정한 STT 시간의 중앙값이며 다운로드·모델 로딩·BERT 처리 시간을 제외한다. 첫 추론의 초기화 비용과 현재 맥 부하는 포함될 수 있다. 반복 측정한 성능 보장은 아니다.

지시 채택은 같은 등록 호출부호에 대해 서버가 기대 HDG(040/300/080)를 채택하고 불필요한 ALT를 만들지 않은 경우다. 글자를 일부 맞히거나 방위 숫자만 알아들은 것은 지시 채택 성공으로 계산하지 않는다.

## 기본 비교 결과

| 모델 | 원음 WER ↓ | 마이크 녹음본 WER ↓ | 원음 STT 중앙값 | 마이크 STT 중앙값 | 지시 채택 원음 / 마이크 |
| --- | ---: | ---: | ---: | ---: | --- |
| base.en | 48.4% | 90.3% | 0.99초 | 0.86초 | 0/3 · 0/3 |
| small.en | 38.7% | 51.6% | 2.90초 | 2.83초 | 0/3 · 0/3 |
| medium.en | 61.3% | 67.7% | 8.51초 | 8.52초 | 0/3 · 0/3 |
| large-v3-turbo | 38.7% | 45.2% | 11.75초 | 15.55초 | 0/3 · 0/3 |

small.en과 turbo는 이 음원에서 base.en보다 단어 오류가 줄었다. small.en은 turbo와 원음 오류율이 같고 CPU 처리 시간은 더 짧았다. turbo는 마이크 녹음본 오류율이 가장 낮았지만 모든 파일에서 호출부호나 명령이 틀려 지시 채택으로 이어지지 않았다. medium.en은 더 큰 모델이어도 기본 안내문 조건에서 small.en보다 나빴다.

예를 들어 세 번째 음원에서 small.en은 방위080을 맞혔지만 호출부호의 항공사 이름을 `Spirit`로 출력했다. turbo의 마이크 결과도 `Speed rate`로 출력했다. 이를 정답인 항공사 이름으로 강제 교체하지 않았고, 다른 항공기에 대한 지시가 될 수 있어 현재 등록 호출부호 검사를 유지했다.

## 안내문 제거 후속 진단

medium.en에서 일반 관제 안내문에 포함된 숫자 목록과 유사한 출력이 관찰되어, 같은4개 모델·같은6개 파일에 대해 `initial_prompt`만 제거했다. 기본 비교 결과를 보고 정한 후속 실험이므로 별도 조건으로 보고한다.

| 모델 | 원음 WER ↓ | 마이크 녹음본 WER ↓ | 지시 채택 원음 / 마이크 |
| --- | ---: | ---: | --- |
| base.en | 74.2% | 96.8% | 0/3 · 0/3 |
| small.en | 32.3% | 61.3% | 0/3 · 0/3 |
| medium.en | 35.5% | 67.7% | 0/3 · 0/3 |
| large-v3-turbo | 45.2% | 90.3% | 0/3 · 0/3 |

medium.en은 원음에서 개선됐고 숫자 목록 출력은 줄었지만 호출부호 문제가 남았다. small.en은 원음에서 개선된 반면 마이크 녹음본에서는 나빠졌다. 따라서 안내문을 무조건 제거하거나 더 큰 모델로 바꾸는 결론은 지지하지 않는다.

## 원인 분리와 판단

모든 시간 측정을 끝낸 뒤 **정답 전사문만 추출기에 전달하는 별도 진단**을 했다. ASR에는 전달하지 않았고 서버 지시를 실제 채택한 시험도 아니다. 동일한 BERT+규칙·등록 호출부호에서 GWI7P/HDG040, DLH1KK/HDG300, BAW820/HDG080에서 추출기의 `instruction_check`가3/3 PASS였다. 실제 서버의 지시 채택 시험과는 구분한다. 이 문장들에서는 STT가 올바른 텍스트를 만들면 추출기가 처리할 수 있다는 근거다. 모든 실제 교신에서 추출기가 정확하다는 뜻은 아니다.

현재 운영 모델은 그대로 유지했다. 추가 시험용 후보로는 CPU 비용이 비교적 작은 small.en을 먼저 고려할 수 있으나, 이번에 동작이 완성된 대체 모델을 찾은 것은 아니다. 다음 검증은 더 많은 미사용 실제 음원에서 호출부호·명령별 성능을 측정하고 ATC 용도로 학습된 STT 및 전처리 후보를 비교하는 것이다. 이번3개에 맞춘 호출부호 강제 교체나 품질 기준 완화로 데모를 통과시키지 않는다.

기본24회와 안내문 제거24회, 총48회의 실제 로컬 추론/서버 처리에서 올바른 지시 채택0회·잘못된 지시 채택0회였다. 전사 품질 개선과 안전한 최종 지시 채택은 별개로 보고한다.

## 검증·검토 범위

6개 입력 해시를 이전 시험 기록과 대조했고, 집계할 때 모델별 파일 누락/중복과 계획 해시를 검사했다. 점수 계산 테스트5개는 누락 전사, 삽입으로100%를 넘는 오류율, 숫자 표기, 동음어를 임의 보정하지 않음, 악센트 문자를 포함한 단어 경계를 확인한다. 자체 검토 중 악센트 문자가 단어 둘로 분리되던 채점기를 수정했고, 저장된48개 전사문을 동일한 수정 기준으로 다시 채점했다. ASR 결과·시간·채택 여부는 바꾸지 않았다.

제품 코드 변경은 없으므로 전체 backend/UI 회귀는 이번에 다시 실행하지 않았다. 실제 새 마이크 입력, Apple GPU 가속, 다른 ASR 아키텍처, ATC 특화 재학습, 독립 대규모 성능평가는 미실행이다. 모델 점수는 보정되지 않은 값이며 모델끼리 같은 정확도를 뜻한다고 가정하지 않는다.


## 재현 방법

평가 스크립트는 이 브랜치에 있고, 실제 `/atc` API 실행에는 [PR #22](https://github.com/kkyo1130/Boeing_RADAR/pull/22)의 코드 `da0f219b4b328e252d6bded629c6f155bbd370b0` 체크아웃을 사용했다. 해당 API가 없는 구버전 dev를 `--radar-root`로 지정하면 중단된다. 원음·마이크 녹음·BERT·Whisper 가중치는 로컬 전용이며 Git에 넣지 않았다.

현재 실험 폴더에서 다음 명령을 실행할 수 있다. Python 환경은 기존 communication 학습 환경을 연결한 `.venv`다.

```sh
.venv/bin/python scripts/evaluation/compare_atc_stt.py \
  --radar-root ../atc-microphone-modes \
  --plan .demo/stt-comparison/plan.json \
  --audio-dir ../atc-microphone-modes/.demo/real-atc \
  --model-name small.en \
  --model-dir .demo/stt-comparison/models/small.en \
  --bert-dir ../bert-hybrid-stt/.demo/bert-hybrid-model \
  --output .demo/stt-comparison/small.en-results.json
```

안내문 제거 조건은 `--no-prompt`와 `no-prompt-plan.json`을 함께 사용한다. 계획과 플래그가 다르면 중단한다. 모든 입력 해시를 추론 전에 확인하며, 집계기는 각 모델·조건에 동일한6개 파일이 빠짐없이 있는지 다시 검사한다.

```sh
.venv/bin/python -m unittest discover -s scripts/evaluation -p 'test_compare*.py'
 .venv/bin/python scripts/evaluation/check_atc_reference.py \
  --radar-root ../atc-microphone-modes \
  --plan .demo/stt-comparison/plan.json \
  --bert-dir ../bert-hybrid-stt/.demo/bert-hybrid-model \
  --output .demo/stt-comparison/reference-control.json
.venv/bin/python scripts/evaluation/summarize_atc_stt.py \
  .demo/stt-comparison docs/evaluation/atc-stt-comparison-2026-11-10.json
```

[전체 조건·해시·인식 원문·지표](evaluation/atc-stt-comparison-2026-11-10.json)를 보존한다. 모델 다운로드는 각 source JSON의 repo/revision으로 Hugging Face `snapshot_download`를 사용했다. 음성은 외부 추론 서비스에 전송하지 않았다.
