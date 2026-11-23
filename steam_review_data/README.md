# Steam 한국어 리뷰 데이터

2026년 11월 11일 수집. 게임별 최신순 최대 2,000개의 한국어 설정 리뷰를 수집한 과제용 표본입니다. 실제 수집 시각은 collection_metadata.json과 각 행의 collected_at_utc에 기록됩니다.

## 파일

- `reviews_clean.csv`: 분석 시작용 통합 파일. 빈 내용, 문자·숫자가 전혀 없는 내용, 게임 내 공백 정규화 후 동일한 내용의 중복을 제외했습니다.
- `reviews_raw.csv`: 통합 원본 표. 리뷰 고유 번호로 중복을 방지했으며 작성자의 Steam ID는 저장하지 않았습니다.
- `elden_ring_raw.csv`, `stardew_valley_raw.csv`, `pubg_raw.csv`: 게임별 원본 표.
- `summary.csv`: 게임별 수집·정리 건수, 추천 여부, 플레이 시간 구간별 건수 및 리뷰 날짜 범위.
- `excluded_reviews.csv`: 제외한 리뷰 번호와 이유. 제외할 행이 있을 때 생성됩니다.
- `collection_metadata.json`: 수집 설정과 수집 당시 API 집계 정보.
- `../collect_steam_reviews.ps1`: 같은 조건으로 다시 수집하는 스크립트. 재실행하면 이번 결과 파일을 갱신합니다.

CSV는 Excel에서도 한국어를 읽을 수 있도록 UTF-8 BOM으로 저장했습니다. 본문에 줄바꿈이 있으므로 파일의 줄 수가 아니라 CSV 읽기 기능으로 행 수를 확인하세요.

## 수집 조건

- 게임: ELDEN RING(1245620), Stardew Valley(413150), PUBG: BATTLEGROUNDS(578080).
- Steam 언어 분류 `koreana`, 최신 작성순, 추천·비추천 모두, 구매 경로 모두.
- Steam의 off-topic activity 필터를 켰습니다.
- 한 요청에 최대 100개, 다음 페이지 cursor를 사용했습니다. 요청 사이에 대기하고 오류 시 재시도했습니다.
- 원본은 API 전체 응답이 아니라 분석에 필요한 필드만 추린 표입니다.

## 주요 열

| 열 | 의미 |
|---|---|
| app_id / game_name | 게임 번호 / 이름 |
| review_id | 리뷰 고유 번호. 숫자 연산에 사용하지 마세요. |
| review_text | 원문 리뷰 |
| recommended | Steam 추천 여부. 문장별 감정 정답은 아닙니다. |
| created_at_utc / updated_at_utc | 작성 / 수정 시각, UTC |
| playtime_at_review_minutes / hours | 리뷰 작성 당시 플레이 시간, 분 / 시간 |
| playtime_group | 10시간 미만 / 10시간 이상 50시간 미만 / 50시간 이상 / 미상 |
| helpful_votes / funny_votes | 도움 됨 / 재미있음 투표 수 |
| collected_at_utc | 해당 페이지를 수집한 시각, UTC |
| has_hangul | 한글 음절 또는 호환 자모 포함 여부 |
| short_review | 앞뒤 공백을 제외한 길이가 10자 미만인지 여부 |

## 분석 시 주의점

- 이 자료는 최신순 표본이며 전체 이용자의 무작위 표본이 아닙니다. 게임마다 포함된 날짜 범위가 다를 수 있습니다.
- Steam에서 한국어로 분류한 리뷰여도 실제 내용은 영어, 숫자 또는 짧은 은어일 수 있습니다. 한글이 없는 리뷰와 10자 미만 리뷰는 표시만 했으며 자동 삭제하지 않았습니다.
- 동일한 짧은 표현도 정리 파일에서는 게임당 최초 한 건만 남습니다. 원래 빈도를 분석하려면 원본 파일을 사용하세요.
- 추천 리뷰에도 불만이, 비추천 리뷰에도 칭찬이 있을 수 있습니다. 기본 결과는 '추천 리뷰의 키워드 / 비추천 리뷰의 키워드'로 해석하세요.
- 정리 파일에도 의미 없는 웃음, 장난, 복사 문구가 남을 수 있습니다. 의미 기반 검수까지 수행한 데이터는 아닙니다.
- 플레이 시간 구간별 추천·비추천 리뷰 수를 확인한 후 비교하세요. 자료가 적은 구간은 결과가 불안정합니다.
- 누락된 플레이 시간은 unknown으로 남겼습니다. 0시간으로 바꾸지 않았습니다.
- UTC를 한국 시각으로 표시하려면 9시간을 더하세요.
- API 접근 가능 여부가 재배포 라이선스를 뜻하지는 않습니다. 과제에 출처와 수집일을 표시하고 외부 재배포 시 Steam 조건과 리뷰 저작권을 별도로 확인하세요.

## 출처

- 공식 문서: https://partner.steamgames.com/doc/webapi/IUserReviewsService?l=english
- 요청 주소: https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/
- 게임 상점: https://store.steampowered.com/app/1245620/ , https://store.steampowered.com/app/413150/ , https://store.steampowered.com/app/578080/
