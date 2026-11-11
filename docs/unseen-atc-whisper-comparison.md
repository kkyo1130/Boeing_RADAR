# 새 관제탑 녹음 60개의 일반·관제용 Whisper 비교

사용자는 앞선3개 발화에서 나타난 관제용 Whisper의 개선이 새 녹음에서도 이어지는지 확인하도록 요청했다. 이번에는 기존 모델2개를 재학습하지 않고, 새로 선정한 실제 관제사 발화60개에 같은 추론 조건을 적용했다. 비교 대상은 일반 `large-v3-turbo`와 `SingularityUS/ATC-whisper-turbo-v1`이다. 운영 RADAR의 모델·설정·호출부호 사전은 변경하지 않았다. [고정 표본·출처·전체 전사·실측 JSON](evaluation/unseen-atc-whisper-2026-11-10.json)에 상세 근거를 보존한다.

## “학습에 안 쓴 자료”를 확인한 범위

관제용 모델의 제작자는 추가 학습 자료를 **ATCO2+ATCOSIM**으로 명시한다. 이번에는 그 두 자료를 피하고 [UWB-ATCC 공식 test split](https://huggingface.co/datasets/Jzuluaga/uwb_atcc)을 사용했다. UWB는 실제 교신의 수동 전사와 화자 역할을 제공한다. `_AT`로 끝나는 관제사 단독 구간만 선택했다. 학습 중복 위험이 컸던 UWB 학습 Wav2Vec2는 이번 대상에 포함하지 않았다. [관제용 모델 카드](https://huggingface.co/SingularityUS/ATC-whisper-turbo-v1)

**일반 Whisper의 사전학습에 이 녹음이 한 번도 포함되지 않았다는 보장은 할 수 없다.** 확인한 공개 자료에는 개별 사전학습 음원 목록이 없고, 관제용 모델의 추가 학습 파일별 목록도 확보하지 못했다. 따라서 이번 결과는 “공개된 추가 학습 코퍼스와 다르고, 우리 프로젝트의 확인된 학습·평가 선택 목록에서 제외한 새 음원”에 대한 결과다. 두 모델 모두에 대해 사전학습 중복0을 검증한 독립 시험이라고 표현하지 않는다. [기반 모델 카드](https://huggingface.co/openai/whisper-large-v3-turbo)

로컬 학습·평가 JSON80개에 기록된1,226개 ID와1,051개 원본 녹음 그룹을 대조했다. 동일 ID뿐 아니라 같은 원본 녹음의 다른 구간도 제외했다. 기존 정답·전사와 정확히 같은 정규화 문장, 새 표본 안의 중복 문장·음원도 제외했다. 이전에 다운로드한 전체 시험셋의 문장 목록 `uwb_official_test_text.json`은 사용한 표본 목록이 아니므로 제외 집합에 넣지 않았다. 파일별 SHA-256과 제외 근거는 결과 JSON에 남겼다. 이 감사는 기록으로 확인 가능한 사용 이력에 한정한다.

## 음원 선정과 실행 조건

- 데이터 revision: `1e8270beb8c1643c8735dddb7229fffb0e399f74`, 공식 test2,822개. 확인한 해당 split의 원본 ID는 모두 TWR이다. 선택 근거는 실제 음성·수동 전사·역할 표시·명시된 라이선스·공식 분할이다. 조사 당시 Hub API의 월 다운로드737회·좋아요17개도 기록했지만 이를 정확도의 근거로 쓰지 않는다.
- 파일: `data/test-00000-of-00001-3a021115ca23c2a5.parquet`, 약131MB. University of West Bohemia 제공, Hugging Face Jzuluaga 배포, CC BY-NC-SA4.0. 추출 전사와 평가 파생자료에도 출처·동일 라이선스 조건을 유지한다. 원음은 Git에 올리지 않는다.
- 제외: 관제사 단독이 아닌1,658개, 이전 사용 원본 녹음 그룹581개, 기존 문장과 같은7개. 남은576구간·389그룹을 seed20261110으로 섞고 서로 다른60그룹에서1개씩 선정했다. 명령 유형·음질·길이·모델 정답 여부로 고르지 않았다.
- 고정 표본:60구간, 약225.30초, 정답734단어(공백 기준), 구간0.96–7.105초. 원문을 유지했으며 `roger` 같은 짧은 발화도 제외하지 않았다. 최종 지표의 분모는 아래 정규화 채점기로 다시 계산한다.
- 같은 조건: Mac M4·16GiB, CTranslate2 CPU int8·4 threads, 영어, beam5, VAD, `condition_on_previous_text=false`, temperature0, 같은 일반 관제 안내문. 호출부호·정답 문장·기대 숫자는 프롬프트에 넣지 않았다.
- 측정 순서: 두 모델을 미리 로드하고 발화마다 먼저 실행할 모델을 번갈아 바꿨다. 다운로드·가중치 로딩 시간은 제외한다. 반복 속도 실험이나 Apple GPU 최적화는 아니다.

일반 모델은 [Dropbox가 공개한 OpenAI 모델의 CTranslate2 변환본](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo), revision `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`이다. 관제용 모델 revision은 `dd7538f043a454ac5873774bb0afe7e527808eef`이고 이전 실험에서 변환한 동일 가중치를 재사용했다. 모델 파일 해시는 실행 결과에 기록한다.

이번에는 **받아쓰기 자체**를 비교한다. RADAR의 후단 모델 점수에 따른 세그먼트 제거를 적용하지 않고 생성된 전사를 그대로 채점했다. 또한 temperature를0으로 고정했다. 앞선3개 시험의 후단 필터·온도 fallback 조건과 다르므로 이전 표의 절대 수치와 합쳐 평균내지 않는다. 두 모델 사이에는 동일 조건을 적용했다. ATCO2 평가, 새로운 스피커/마이크 재녹음, BERT 추출·서버 채택 시험은 하지 않았다.

## 채점 방법

주 지표는 단어 오류율 WER이다. 대소문자·문장부호를 정리하고 숫자 표기를 자리별 영어 단어로 확장한다. 예를 들어 `080`과 `zero eight zero`는 같게 보지만 `to`를 `two`로 고치거나 항공사 이름을 보정하지 않는다. 60개의 단어 오류 수를 합쳐 전체 정답 단어 수로 나눈다. 숫자 확장 전 WER도 함께 보존한다. 원래 전사에는 `deaprture`, `skytavel` 같은 철자도 있어 그대로 채점했다. 정답 전사 자체의 표기 오류 때문에 올바른 철자가 단어 오류로 계산될 수 있으며, 결과를 본 뒤 정답을 고치지는 않았다. 문장별 WER 중앙값과 오류율100% 초과 문장 수도 보조로 기록해 극단적인 반복 출력의 영향을 드러낸다.

숫자 보조 지표는 전체 문장에서 숫자 단어의 **순서 있는 목록**을 비교한다. `zero`부터`nine`, `oh`, `niner`, `hundred`, `thousand`를 추출한다. 이는 호출부호·주파수·활주로·고도 등이 섞인 표면 표현 지표이며, ALT/HDG 값 정확도나 명령 이해 정확도가 아니다. 숫자가 없는 발화의 일치를 성공으로 부풀리지 않도록 숫자 있는 발화의 전체 일치 수도 따로 표시한다.

각 원본 녹음에서1구간만 뽑았으므로 같은60쌍을 함께 재추출하는 paired bootstrap10,000회(seed20261110)로 WER 차이의95% 구간을 구한다. 이 구간은 이 표본의 재표집 변동만 나타낸다. 같은 관제사·공항의 반복이나 사전학습 중복을 제거한 일반화 보장은 아니다.

## 전체60개 결과: 고정 temperature0

| 지표 | 일반 Whisper Turbo | 관제용 Whisper Turbo |
| --- | ---: | ---: |
| 전체 WER, 낮을수록 좋음 | 149.5% (1,097/734) | 30.2% (222/734) |
| 문장별 WER 중앙값 | 33.3% | 25.7% |
| 정규화 문장 전체 일치 | 3/60 | 4/60 |
| 숫자가 있는55개 중 숫자 단어 목록 전체 일치 | 20/55 | 30/55 |
| 숫자 토큰 오류율 | 286.4% (862/301) | 10.6% (32/301) |
| 오류율100% 초과 문장 | 14/60 | 3/60 |
| 처리 시간 중앙값 | 10.91초 | 10.62초 |

문장별 비교는 **관제용 우세35개, 동률14개, 일반 모델 우세11개**다. 전체 단어 오류 중 일반 모델은 대치189·삭제30·삽입878개, 관제용은 대치131·삭제17·삽입74개였다. WER은 삽입까지 세므로100%를 넘을 수 있다. 일반 모델이 짧은 정답 대신 `seven` 등을100단어 넘게 반복한 사례가 큰 영향을 줬다. 이를 제거하거나100%로 잘라내지 않았다.

전체 WER 차이(관제용−일반)는−119.2%p, paired bootstrap95% 구간은 약−202.5~−51.8%p다. 이는 고정 temperature0에서 나온 반복 출력까지 포함한 차이다. 이 숫자를 운영 RADAR의 개선 폭으로 옮기면 안 된다. 문장별 중앙값과35/14/11 비교를 함께 봐도 이번 표본에서 관제용이 우세하지만, 대부분 문장은 아직 완전히 일치하지 않는다.

개선 사례와 남은 오류도 함께 보존한다. `uwb-atcc_TWR-ahaj40_000215_000755_AT`에서 일반 모델의 `Paparanway` 등의 오류가 관제용에서 줄었지만, 관제용도 정답 `cleared to land wind`를 `cleared to line seven`으로 전사했다. 반대로 `uwb-atcc_TWR-FJ5hyZ_001080_001791_AT`의 대기 지시에서는 일반 모델1단어, 관제용3단어 오류로 일반 모델이 더 정확했다. 예시2개는 전체 집계를 대신하지 않는다.

## 추가 진단: 기본 재시도 설정

기본 결과를 확인하던 중 긴 반복이 나타나, **어느 모델이든 WER100%를 넘긴14구간**을 사후 진단 대상으로 정했다. 같은14개를 두 모델 모두 다시 실행했고, temperature만 현재 RADAR와 같은 `[0, 0.2, 0.4, 0.6, 0.8, 1.0]` 재시도 목록으로 바꿨다. 호출마다 CTranslate2 seed20261110을 고정했다. 후단 점수 필터를 적용한 서버 E2E가 아니라 디코딩 설정 진단이다.

| 같은14개 문제 구간 | 일반 Whisper | 관제용 Whisper |
| --- | ---: | ---: |
| 고정 temperature0 WER | 770.3% | 68.6% |
| 기본 재시도 WER | 97.5% (115/118) | 68.6% (81/118) |
| 재시도 후 숫자 있는11개 중 숫자 목록 전체 일치 | 1/11 | 7/11 |

일반 모델의 반복 출력은 기본 재시도에서 크게 줄었다. 따라서 전체60개 고정 조건의149.5%와30.2%만 보고 추가 학습 효과가 그만큼이라고 단정하면 과장이다. 진단 대상에서도 관제용이 더 낮은 오류율을 보였지만, 이14개는 실패 사례를 보고 고른 집합이므로 새로운 독립 시험이 아니다. 나머지46개를 기본 재시도로 실행하지 않았으므로 전체60개의 기본 재시도 성능을 계산하거나 두 조건의 결과를 섞지 않았다. 기존120회 결과는 그대로 유지했다.


## 판단

공개된 추가 학습 코퍼스와 다른 새 관제탑60구간에서도 관제용 모델의 개선 신호를 확인했다. 그러나 완전 일치는4/60에 그쳤고 호출부호·명령·숫자 오류가 남았다. 같은 공항/코퍼스 내 새 구간이며 화자 독립성이 검증된 것은 아니다. 운영 모델은 교체하지 않았다. 기본 재시도 설정의 효과와 순수한 추가 학습 효과를 혼동하지 않고, 후속 선택에서는 실제 운영 디코딩 조건과 호출부호·ALT/HDG 의미 정확도를 별도로 확인해야 한다.


## 재현과 검증

기본 비교120회와 추가 진단28회, 합계148회 실제 가중치 추론 및 입력/결과 감사가 완료됐다. 단위 테스트6개·Python 컴파일 검사를 통과했다. 감사는 고정60개×2모델 커버리지, 원음 해시, 이전 파일80개 해시, 이전 원본 그룹 중복0, WER/숫자 지표 재계산을 포함한다. 전체 UI/서버 회귀와 새 마이크 녹음은 미실행이다.

`scripts/evaluation/prepare_unseen_atc.py`가 이전 자료 감사·선정·WAV 추출·계획 고정을 담당한다. `compare_unseen_whisper.py`는 파일/가중치/계획/실행 코드 해시를 확인해 로컬 추론하고 각 결과를 원자 저장한다. 중단 후 재개할 때 조건이 바뀌면 거부한다. `summarize_unseen_whisper.py`는 모든60×2결과, 이전 사용 파일 해시와 원본 그룹 중복0, 음원 해시, 지표 재계산을 검사한다.

작업 루트에서 실행한다. 준비 단계는 새 출력 폴더에서 한 번만 실행하며 이미 고정된 계획은 덮어쓰지 않는다:

```sh
.venv/bin/python scripts/evaluation/prepare_unseen_atc.py \
  --communication ../.. \
  --parquet .demo/unseen/dataset/data/test-00000-of-00001-3a021115ca23c2a5.parquet \
  --output .demo/unseen/audio
.venv/bin/python scripts/evaluation/compare_unseen_whisper.py \
  --plan .demo/unseen/audio/plan.json \
  --generic ../atc-stt-comparison/.demo/stt-comparison/models/large-v3-turbo \
  --specialist ../atc-specialist-comparison/.demo/specialist/models/whisper-atc-turbo-ct2 \
  --output .demo/unseen/results.json
.venv/bin/python scripts/evaluation/check_whisper_fallback.py \
  --plan .demo/unseen/audio/plan.json --results .demo/unseen/results.json \
  --generic ../atc-stt-comparison/.demo/stt-comparison/models/large-v3-turbo \
  --specialist ../atc-specialist-comparison/.demo/specialist/models/whisper-atc-turbo-ct2 \
  --output .demo/unseen/fallback.json
.venv/bin/python scripts/evaluation/summarize_unseen_whisper.py \
  --plan .demo/unseen/audio/plan.json --results .demo/unseen/results.json \
  --source .demo/unseen/source.json --communication ../.. \
  --fallback .demo/unseen/fallback.json \
  --output docs/evaluation/unseen-atc-whisper-2026-11-10.json
.venv/bin/python -m unittest discover -s scripts/evaluation -p 'test_unseen_whisper.py'
```

원음·모델은 Git-ignored `.demo`에 별도 보존한다. 새 체크아웃에서 원음은 고정 revision의 parquet와 공유 JSON의 `plan.clips` ID로 복구할 수 있다. 기존 사용 자료 목록은 `plan.prior_files`에 경로/해시로 보존한다. 전체 기존 자료가 없는 환경에서는 해당 제외 감사까지 재현했다고 주장하면 안 된다. 모델 출처와 revision을 고정해 내려받고 관제용은 이전 [PR #24](https://github.com/kkyo1130/Boeing_RADAR/pull/24)의 변환 절차를 따른다. 실행기 자체는 이전 PR의 API나 채점 코드에 의존하지 않는다.
