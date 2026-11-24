# 파이썬 Steam 리뷰 수집기

`collect_steam_reviews.py`는 Python 3.10 이상에서 실행합니다. 추가 패키지 설치나 API 키 입력은 필요하지 않습니다. 인터넷 연결은 필요합니다.

## 실행

코드가 있는 폴더에서 아래 명령을 실행합니다. Windows에서 `python` 대신 `py -3`를 사용할 수도 있습니다.

```powershell
python collect_steam_reviews.py
```

기본값은 엘든 링, 스타듀 밸리, 배틀그라운드의 한국어 리뷰를 게임당 최대 2,000개씩 최신순으로 가져옵니다. 정리 후 개수는 줄어들 수 있습니다. 실제 리뷰가 부족하면 있는 만큼 저장합니다.

처음에는 소량으로 실행해보세요.

```powershell
python collect_steam_reviews.py --limit 10
```

특정 게임만 가져오려면 상점 주소의 `/app/` 뒤에 있는 게임 번호를 지정합니다.

```powershell
python collect_steam_reviews.py --app-ids 1245620 578080 --limit 2000
```

영어 리뷰를 수집하거나 저장 폴더를 지정할 수도 있습니다. 저장 폴더는 새 폴더 또는 빈 폴더여야 합니다.

```powershell
python collect_steam_reviews.py --app-ids 1245620 --language english --limit 100 --output-dir english_reviews
```

## 저장 결과

기본적으로 코드 옆에 `steam_review_data_실행날짜_시간` 폴더가 생깁니다. 이전에 수집한 `steam_review_data` 폴더는 변경하지 않습니다.

- `reviews_raw.csv`: 모든 게임의 수집 결과. 리뷰 번호 중복을 제거합니다.
- `reviews_clean.csv`: 게임별 동일 내용 중복, 빈 내용, 문자·숫자가 전혀 없는 내용을 제외한 분석용 자료.
- `게임번호_raw.csv`: 게임별 수집 결과. 각 페이지를 받은 뒤 저장합니다.
- `excluded_reviews.csv`: 정리 과정에서 제외한 리뷰 번호와 이유.
- `summary.csv`: 게임별 추천·비추천 및 플레이 시간 구간별 개수.
- `collection_metadata.json`: 수집 조건과 성공·부분 완료 상태. `complete`여도 실제 리뷰가 적으면 목표보다 적을 수 있습니다.

## 코드가 하는 일

1. 공식 `GetAppReviews` API에 한국어·최신순·추천/비추천 모두·구매 경로 모두를 요청합니다.
2. 최대 100개씩 받고, 응답의 `cursor`로 다음 페이지를 가져옵니다.
3. 요청 사이에 기본 1.5초 기다립니다. 일시적인 연결 오류나 요청 제한에는 최대 5회 시도하며, 서버의 Retry-After가 있으면 따릅니다.
4. 리뷰 본문과 추천 여부, 작성일, 작성 당시 플레이 시간 등을 저장합니다. 작성자 Steam ID는 저장하지 않습니다.
5. 정리 결과와 집계를 함께 저장합니다. 수집 중 오류가 나거나 Ctrl+C로 중단해도 받은 페이지는 보존하며, 자동 이어받기는 지원하지 않습니다.

## 해석

- Steam이 한국어로 분류한 글에도 영어·짧은 은어가 있습니다. `has_hangul`, `short_review`로 표시하고 삭제하지 않습니다.
- 추천 여부는 리뷰 전체 평가입니다. 개별 문장의 긍정·부정 정답이 아닙니다.
- 작성 당시 플레이 시간은 분과 시간으로 모두 저장하며 누락 시 빈칸입니다. 구간은 10시간 미만, 10시간 이상 50시간 미만, 50시간 이상입니다.
- 날짜는 UTC입니다. 한국 시각은 9시간을 더합니다. 게임마다 최신순 표본의 날짜 범위가 다릅니다.
- 정리 파일은 같은 내용의 반복을 제거하므로, 원래 언급 빈도를 분석하려면 원본도 함께 확인하세요. 의미 없는 장난 글까지 자동으로 판별하지는 않습니다.
- 공식 문서: https://partner.steamgames.com/doc/webapi/IUserReviewsService?l=english
