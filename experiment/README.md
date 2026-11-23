# 한국어 BERT 미세조정 실험

기준 웹 버전은 main의 ae97174다. 실험은 experiment/korean-bert 브랜치에서 실행했다. 웹에서 사용하는 분류기는 TF-IDF다.

| 구절 단위 14개 라벨 Macro F1 | TF-IDF | KLUE BERT |
|---|---:|---:|
| 검증 55개 | 0.376 | 0.305 |
| 기존 테스트 69개 | 0.305 | 0.360 |
| 추가 점검 60개 | 0.119 | 0.129 |

AI 라벨을 사용했다. 같은 리뷰가 기존 학습·검증·테스트에 중복되지 않도록 이전 실험의 분할을 재사용했다. 추가 점검 자료는 기존 라벨링에 쓰지 않은 리뷰 중 한글을 포함하는 길이 6~100자의 구절을 고를 수 있는 리뷰에서 추출했다. 무작위 시드 1123으로 리뷰를 섞고 리뷰당 한 구절을 골랐다. 이 표본은 기존 3개 게임에 한정되며 평가 사례가 없는 라벨도 있다. 평가 기준은 모든 자료에서 14개 라벨의 산술평균이고 분모가 0인 경우 해당 F1을 0으로 처리한다. 추가 점검 micro F1은 TF-IDF 0.475, BERT 0.444였다.

KLUE BERT의 앞 11개 층은 고정하고 마지막 트랜스포머 층과 다중 레이블 분류기를 220개 구절로 학습했다. 검증 자료에서 16개 학습 시점과 6개 판정 기준을 비교한 결과 4회차와 0.40을 선택했다. 점검 및 테스트 자료는 선택에 사용하지 않았다. 기존 테스트 문구는 과거 오류 분석에서 이미 살펴봤다. 모델별·라벨별 전체 수치는 results.json에 있다.

## 재현

저장소 루트에서 Python 3.12 가상환경으로 실행한다.

~~~powershell
python -m pip install -r experiment/requirements.txt
$revision = '77c8b3d707df785034b4e50f2da5d37be5f0f546'
New-Item -ItemType Directory -Force .bert_model | Out-Null
foreach ($name in 'config.json','tokenizer.json','special_tokens_map.json','tokenizer_config.json','vocab.txt','model.safetensors') {
    curl.exe -fLsS "https://huggingface.co/klue/bert-base/resolve/$revision/$name" -o ".bert_model/$name"
}
$revision | Set-Content .bert_model/revision.txt -Encoding ascii
python experiment/predict.py "캐릭터 이동이 너무 답답함"
~~~

bert-last-layer.pt에는 학습한 마지막 층과 분류기 파라미터가 들어 있다. 동일 조건으로 재학습하려면 저장소 루트에서 python experiment/train_bert.py를 실행한다. 실험 확인 후 git switch main으로 기준 버전으로 돌아갈 수 있다.
