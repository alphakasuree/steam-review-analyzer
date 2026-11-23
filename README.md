# 스팀 리뷰 분석

Windows에서는 저장소를 받은 뒤 **스팀 리뷰 분석.exe**를 더블클릭하세요. 실행 파일에 세 게임의 분석 결과가 포함되어 있습니다.

## 다른 PC에서 이어서 개발하기

GitHub에 업로드한 경우 저장소를 복제하세요. Git 번들 파일을 옮긴 경우에는 번들이 있는 폴더에서 아래 명령으로 커밋 기록과 프로젝트를 복원할 수 있습니다.

~~~powershell
git clone steam-review-analyzer.bundle steam-review-analyzer
cd steam-review-analyzer
~~~

화면 코드는 ReviewWindow.cs에 있습니다. Windows PowerShell에서 아래 명령을 실행하면 현재 분석 결과를 포함한 실행 파일을 다시 만듭니다.

~~~powershell
.\build_review_app.ps1
~~~

## 모델 재학습

저장소 폴더에서 Python 3.12 가상환경을 만들고, 공개 다국어 임베딩 모델을 내려받은 뒤 실행하세요. 학습에 사용하는 리뷰와 AI 작성 라벨은 저장소에 포함되어 있습니다.

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
New-Item -ItemType Directory -Force review_model | Out-Null
$modelUrl = 'https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/resolve/main'
Invoke-WebRequest "$modelUrl/tokenizer.json" -OutFile review_model/tokenizer.json
Invoke-WebRequest "$modelUrl/onnx/model_quantized.onnx" -OutFile review_model/model_quantized.onnx
.\.venv\Scripts\python analyze_reviews.py
.\build_review_app.ps1
~~~

수집 방법은 [수집기 안내](STEAM_COLLECTOR_GUIDE.md), 데이터 출처와 필드는 [데이터 설명](steam_review_data/README.md)을 참고하세요.
