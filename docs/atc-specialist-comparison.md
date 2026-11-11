# 관제 특화 STT의 동일 음원 비교

기존 일반 Whisper 비교에서 호출부호 오류가 남아, 관제 데이터로 미세조정된 공개 모델3개를 같은 음원에 적용했다. 학습이나 운영 모델 교체 없이 Mac M4·16GiB에서 로컬 추론했다. 이번에도 이전에 분석한 실제 관제 발화3개의 원음과 기존 스피커→마이크 녹음본을 재사용했다. 새로운 교신6개 또는 독립 평가셋이 아니다.

## 모델을 고른 근거

| 실험 이름 | 공개 모델 | 학습 데이터: 제작자 모델 카드 기준 | 시험 음원과 중복 위험 |
| --- | --- | --- | --- |
| CTC-ATCOSIM | [Jzuluaga/wav2vec2-large-960h-lv60-self-en-atc-atcosim](https://huggingface.co/Jzuluaga/wav2vec2-large-960h-lv60-self-en-atc-atcosim) | ATCOSIM | UWB를 명시하지 않음. 개별 학습 파일 목록 미감사 |
| CTC-UWB+ATCOSIM | [Jzuluaga/wav2vec2-large-960h-lv60-self-en-atc-uwb-atcc-and-atcosim](https://huggingface.co/Jzuluaga/wav2vec2-large-960h-lv60-self-en-atc-uwb-atcc-and-atcosim) | UWB-ATCC + ATCOSIM | **높음. 이번3개가 UWB train split에 속함. 독립 성능 비교에서 제외해야 함** |
| ATC-Whisper-Turbo | [SingularityUS/ATC-whisper-turbo-v1](https://huggingface.co/SingularityUS/ATC-whisper-turbo-v1) | ATCO2 + ATCOSIM | UWB를 명시하지 않음. 개별 학습 파일 목록 미감사 |

첫 두 모델은 일반 Whisper와 다른 Wav2Vec2 CTC 계열로, 학술 연구·학습 코퍼스가 공개된 후보를 선택했다. 세 번째는 기존 large-v3-turbo와 같은 기반 모델의 관제용 미세조정 효과를 비교하기 위한 후보다. 제작자가 보고한 자체 평가 WER를 이 시험의 정확도로 옮기지 않았다. ATC-Whisper 카드는 평가자료가 주로 깨끗한 ATCOSIM 음성이며 실제 잡음 무전에서는 오류가 더 클 수 있다고 밝힌다.

CTC 모델 카드의 라이선스는 Apache-2.0이고, ATC-Whisper는 `other`로 표기하며 연구용 사용과 학습 데이터별 조건을 명시한다. 이번에는 로컬 연구 비교만 수행하고 가중치를 저장소에 재배포하지 않았다. 이 Whisper 후보는 이미 ATCO2로 학습되었으므로 향후 ATCO2를 독립 시험용으로 쓸 때 해당 모델의 학습 중복을 먼저 확인해야 한다. 이번 실행에서 ATCO2 음원을 내려받거나 추가 학습하지는 않았다.

## 동일하게 유지한 것과 달라진 것

- 동일 입력: 기존6개 WAV의 SHA-256을 확인했다. source revision `1e8270beb8c1643c8735dddb7229fffb0e399f74`의 [UWB-ATCC](https://huggingface.co/datasets/Jzuluaga/uwb_atcc), University of West Bohemia, CC BY-NC-SA4.0이다. 처음 음소거 상태에서 얻은 녹음은 제외했다.
- 동일 후단: 기존 BERT+규칙, 등록 호출부호와 허용 발음, 숫자 검사, 품질 임계값을 유지했다. 호출부호·기대 방위·정답 전사는 ASR 입력이나 프롬프트로 전달하지 않았다.
- CTC: 모델 카드의 LM 없는 greedy decoding, PyTorch float32 CPU4 threads. WAV를16kHz로 리샘플링했다. 별도 VAD나 철자 보정은 하지 않았다. ATCOSIM 모델 저장소에도 `language_model/uwb_atcc_4g.binary`라는 파일이 있으므로, LM을 통한 UWB 정보 유입을 피하고자 두 모델 모두 LM을 내려받거나 사용하지 않았다.
- Whisper: 원본 safetensors를 로컬 CTranslate2 FP16 형식으로 변환한 뒤 CPU int8·4 threads로 실행했다. 기존과 같은 beam5·영어·VAD·일반 관제 안내문 조건을 기본으로 하고, 안내문 제거 조건도 같은6개 파일에서 실행하기로 추론 전에 정했다. 재학습이나 시험 음원에 맞춘 가중치 변경은 없다.
- 속도는 같은 맥에서 측정했지만 엔진·정밀도·디코딩 방식이 다르다. 다운로드·모델 로딩을 제외한 파일별1회 실행의 STT 시간 중앙값이다. Apple GPU의 최고 속도나 반복 측정 성능을 뜻하지 않는다.

## 지표의 구분

WER은 이전 실험과 같은 채점기를 사용한다. 대소문자·문장부호를 정리하고 `080` 같은 숫자 표기를 `zero eight zero`로 맞춘 단어 오류율이다. 낮을수록 좋으며, 기준 전사는 조건별31단어뿐이다. 원래 정답의 `k`도 `kilo`로 고치지 않았다.

**텍스트 추출 일치**는 실제 STT 출력에 기존 BERT+규칙을 적용했을 때 호출부호와 HDG가 모두 맞고 여분의 ALT가 없는 경우다. 음성 품질 검사를 통과했다거나 서버가 지시를 채택했다는 뜻이 아니다.

**서버 채택**은 실제 `/atc` 경로의 최종 결과다. CTC에는 현재 Whisper의 모델 점수와 동등한 점수를 정의하지 않았다. 임의로0.9 같은 점수를 넣지 않고 `model_score=null`을 유지했으므로 기존 서버 정책은 CTC 입력을 판단 보류한다. 따라서 CTC의 채택0회를 받아쓰기 실패율로 해석하면 안 된다. CTC를 제품에 연결하려면 별도의 품질 정책과 검증이 필요하다.

## 실측 결과

아래 일반 Whisper는 직전 비교의 동일 음원·동일 일반 관제 안내문 결과다. 오류율은 낮을수록 좋다. CTC 두 모델에는 프롬프트가 없다.

| 모델·기본 조건 | 원음 WER | 기존 마이크 녹음 WER | STT 중앙값: 원음 / 마이크 |
| --- | ---: | ---: | ---: |
| 일반 Whisper base.en | 48.4% | 90.3% | 0.99 / 0.86초 |
| 일반 Whisper small.en | 38.7% | 51.6% | 2.90 / 2.83초 |
| 일반 Whisper medium.en | 61.3% | 67.7% | 8.51 / 8.52초 |
| 일반 Whisper large-v3-turbo | 38.7% | 45.2% | 11.75 / 15.55초 |
| CTC-ATCOSIM | 38.7% | 77.4% | 0.38 / 0.55초 |
| **ATC-Whisper-Turbo** | **22.6%** | **29.0%** | 11.01 / 10.95초 |
| CTC-UWB+ATCOSIM — 학습 중복 위험, 참고만 | 0.0% | 3.2% | 0.35 / 0.55초 |

안내문을 제거한 ATC-Whisper-Turbo는 원음29.0%, 마이크25.8%, 중앙값10.90/10.87초였다. 원음은 일반 안내문이 낫고 마이크는 없는 조건이 낫다. 시험 후 가장 좋은 조건만 골라 모델 전체 성능처럼 제시하지 않는다.

| 특화 모델·조건 | 텍스트 추출 일치: 원음 / 마이크 | 실제 서버 채택: 원음 / 마이크 |
| --- | ---: | ---: |
| CTC-ATCOSIM | 0/3 · 0/3 | 0/3 · 0/3 |
| CTC-UWB+ATCOSIM — 학습 중복 위험 | 3/3 · 2/3 | 0/3 · 0/3 |
| ATC-Whisper-Turbo · 일반 안내문 | 0/3 · 0/3 | 0/3 · 0/3 |
| ATC-Whisper-Turbo · 안내문 없음 | 0/3 · 0/3 | 0/3 · 0/3 |

ATC-Whisper의 단어 오류는 줄었지만 호출부호가 남은 문제다. 예를 들어 원음의 `speed bird eight two zero`를 `speedway eight six zero`로 전사했다. 방위가 맞아도 다른 항공기의 지시로 연결할 수 있으므로 기존 서버는 채택하지 않았다. ATCOSIM-only CTC도 마이크 조건에서 오류가 커졌다. 관제 특화라는 이름만으로 잡음 내성이 확보되지는 않았다.

CTC-UWB+ATCOSIM은 원음31단어 중0개, 마이크31단어 중1개만 틀렸다. 그러나 UWB 학습 코퍼스와 시험 자료가 겹칠 위험이 높아 이 수치로 최종 모델을 선정하지 않는다. 마이크로 다시 녹음해도 발화 내용과 원본 화자가 같아서 독립 시험이 되지 않는다. 또한 이 모델의 서버 채택0/3은 미확인 품질 점수를 보류하는 현재 정책의 결과다.

이번 결과에서 **ATC-Whisper-Turbo는 추가 검증할 후보**다. 일반 large-v3-turbo보다 같은3개 발화에서 WER이 원음16.1%p, 마이크16.2%p 낮았다. 다만 호출부호와 방위가 함께 맞는 경우는 없어서 지금 운영 모델을 교체할 근거는 부족하다. 다음 비교는 후보의 학습 자료와 겹치지 않는 새 교신에서 호출부호·숫자 오류를 따로 측정해야 한다. CTC를 후속 후보로 유지하려면 별도로 검증한 품질 정책도 필요하다.


## 재현·감사

`codex/atc-specialist-comparison`의 `scripts/evaluation/compare_atc_specialists.py`를 실행했다. `/atc` API는 PR #22의 `da0f219`, 공통 채점기는 PR #23의 `de7740e` 체크아웃을 지정했다. 모델별 별도 프로세스와 임시 DB를 사용하므로 실행 중 운영 비행·모델 설정은 변경하지 않는다. 외부에는 모델 파일만 다운로드하며 음성은 전송하지 않는다.

```sh
.venv/bin/python scripts/evaluation/compare_atc_specialists.py \
  --radar-root ../atc-microphone-modes \
  --scorer-root ../atc-stt-comparison \
  --plan .demo/specialist/plan.json \
  --audio-dir ../atc-microphone-modes/.demo/real-atc \
  --model-name ctc-uwb-atcosim --engine ctc \
  --model-dir .demo/specialist/models/ctc-uwb-atcosim \
  --bert-dir ../bert-hybrid-stt/.demo/bert-hybrid-model \
  --output .demo/specialist/ctc-uwb-atcosim-results.json
```

Whisper는 `--engine whisper`, 변환된 `whisper-atc-turbo-ct2` 경로를 사용한다. 추가 조건만 `--no-prompt`를 붙인다. 원본 모델 repo/revision은 결과 JSON의 model_sources, 변환 명령·해시는 conversion에 기록한다. 가중치/원시 실행 파일은 Git-ignored `.demo/specialist`에, 원음과 기존 마이크 녹음은 선행 worktree의 `.demo/real-atc`에 보존한다.

```sh
.venv/bin/python -m unittest discover -s scripts/evaluation -p 'test_atc_specialists.py'
.venv/bin/python scripts/evaluation/summarize_atc_specialists.py \
  --runs .demo/specialist --scorer-root ../atc-stt-comparison \
  --output docs/evaluation/atc-specialist-comparison-2026-11-10.json
```

[전체 출처·고정 계획·인식 원문·실측 결과](evaluation/atc-specialist-comparison-2026-11-10.json). 총24회 실제 모델 추론/API 실행을 완료했다. 입력6개의 해시, 결과 누락·중복, WER 재계산과 CTC12회의 `model_score=null`·보류를 확인했다. 전용 단위 테스트2개와 Python 컴파일 검사도 통과했다. 모델 학습 데이터의 개별 파일 목록 감사, 새 실시간 마이크, 대규모 미사용 교신, 운영 품질 정책 변경과 전체 UI 회귀는 이번 범위에서 수행하지 않는다.

새 체크아웃에서 계획은 결과 JSON의 `plan` 객체를 `json.dumps(..., indent=2) + "\n"`으로 저장하면 복구할 수 있다. 모델은 `model_sources`의 repo와 revision을 고정하여 Hugging Face `snapshot_download`로 내려받는다. safetensors가 있으면 그것을 우선하고 CTC-UWB 모델만 `pytorch_model.bin`을 사용한다. 설정·tokenizer 파일은 함께 받되 `language_model/`과 학습 checkpoint는 제외한다. Whisper 변환 명령은 `conversion.command`를 참고한다. Python/라이브러리 버전은 JSON의 `packages`에 기록했다. 요약 스크립트는 로컬 원시 결과4개와 plan/source/leakage-audit/conversion 파일이 필요하며, 공유 JSON은 이 정보와 결과를 보존한다. 원음6개와 BERT 가중치는 별도 로컬 입력이므로 저장소 clone만으로 음성 추론이 실행되는 것은 아니다.
