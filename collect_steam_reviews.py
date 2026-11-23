"""Steam 리뷰 수집기 (Python 3.10+, 외부 패키지 불필요).

실행: python collect_steam_reviews.py
예시: python collect_steam_reviews.py --app-ids 1245620 578080 --limit 100
문서: https://partner.steamgames.com/doc/webapi/IUserReviewsService?l=english
"""

import argparse
import csv
import json
import math
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ENDPOINT = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
GAME_NAMES = {
    1245620: "ELDEN RING",
    413150: "Stardew Valley",
    578080: "PUBG: BATTLEGROUNDS",
}
FIELDS = [
    "app_id", "game_name", "review_id", "language", "review_text",
    "recommended", "created_at_utc", "updated_at_utc",
    "playtime_at_review_minutes", "playtime_at_review_hours", "playtime_group",
    "helpful_votes", "funny_votes", "steam_purchase", "received_for_free",
    "written_during_early_access", "collected_at_utc", "has_hangul", "short_review",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def timestamp_to_iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else ""


def write_csv(path, rows, fields):
    """줄바꿈이 포함된 본문과 Excel 한글 표시를 지원. 임시 파일 후 교체."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def retry_delay(header, attempt):
    delay = min(30, 2 ** (attempt + 1))
    if header:
        try:
            seconds = float(header)
        except ValueError:
            try:
                seconds = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                seconds = 0
        delay = max(delay, seconds)
    return max(0, delay)


def fetch_page(parameters, attempts=5):
    query = urlencode({"input_json": json.dumps(parameters, ensure_ascii=False)})
    request = Request(ENDPOINT + "?" + query, headers={"User-Agent": "SteamReviewCourseProject/1.0"})
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.load(response)
            page = payload.get("response", payload)
            if not isinstance(page, dict) or not isinstance(page.get("reviews"), list):
                raise ValueError("Unexpected Steam response: reviews list is missing")
            return page
        except HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            delay = retry_delay(error.headers.get("Retry-After"), attempt)
        except (URLError, TimeoutError, ConnectionError):
            if attempt == attempts - 1:
                raise
            delay = retry_delay(None, attempt)
        print(f"Request failed; retrying in {delay:.0f}s...", flush=True)
        time.sleep(delay)


def make_row(review, app_id, collected_at):
    text = review.get("review", "") or ""
    minutes = review.get("author", {}).get("playtime_at_review")
    if minutes is None:
        group = "unknown"
    elif minutes < 600:
        group = "under_10h"
    elif minutes < 3000:
        group = "10_to_50h"
    else:
        group = "50h_plus"
    return {
        "app_id": app_id,
        "game_name": GAME_NAMES.get(app_id, f"App {app_id}"),
        "review_id": str(review["recommendationid"]),
        "language": review.get("language", ""),
        "review_text": text,
        "recommended": review["voted_up"],
        "created_at_utc": timestamp_to_iso(review.get("timestamp_created")),
        "updated_at_utc": timestamp_to_iso(review.get("timestamp_updated")),
        "playtime_at_review_minutes": minutes,
        "playtime_at_review_hours": round(minutes / 60, 2) if minutes is not None else None,
        "playtime_group": group,
        "helpful_votes": review.get("votes_up", 0),
        "funny_votes": review.get("votes_funny", 0),
        "steam_purchase": review.get("steam_purchase"),
        "received_for_free": review.get("received_for_free"),
        "written_during_early_access": review.get("written_during_early_access"),
        "collected_at_utc": collected_at,
        "has_hangul": bool(re.search(r"[\uac00-\ud7a3\u3131-\u318e]", text)),
        "short_review": len(text.strip()) < 10,
    }


def collect_game(app_id, limit, language, interval, rows, checkpoint):
    """각 페이지를 즉시 저장하여 오류가 나도 이미 받은 리뷰를 보존."""
    cursor = "*"
    seen_cursors = set()
    seen_ids = set()
    first_summary = None
    page_limit = max(100, math.ceil(limit / 100) * 5)
    for _ in range(page_limit):
        parameters = {
            "appid": app_id, "languages": [language], "filter": 1,
            "review_type": 0, "purchase_type": 1,
            "num_per_page": min(100, limit - len(rows)),
            "cursor": cursor, "filter_offtopic_activity": True,
        }
        page = fetch_page(parameters)
        if first_summary is None:
            first_summary = page.get("query_summary", {})
        if not page["reviews"]:
            return first_summary
        for review in page["reviews"]:
            review_id = str(review["recommendationid"])
            if review_id in seen_ids:
                continue
            rows.append(make_row(review, app_id, utc_now()))
            seen_ids.add(review_id)
            if len(rows) >= limit:
                break
        write_csv(checkpoint, rows, FIELDS)
        print(f"{GAME_NAMES.get(app_id, app_id)}: {len(rows)} / {limit}", flush=True)
        if len(rows) >= limit:
            return first_summary
        seen_cursors.add(cursor)
        cursor = page.get("cursor")
        if not cursor or cursor in seen_cursors:
            raise RuntimeError(f"Pagination stopped unexpectedly for app {app_id}; partial data saved")
        time.sleep(interval)
    raise RuntimeError(f"Pagination limit reached for app {app_id}; partial data saved")


def clean_reviews(rows):
    clean, excluded, seen = [], [], set()
    for row in rows:
        normalized = " ".join(row["review_text"].split())
        key = (row["app_id"], normalized)
        reason = None
        if not normalized:
            reason = "empty"
        elif not any(char.isalnum() for char in normalized):
            reason = "symbols_only"
        elif key in seen:
            reason = "duplicate_text_within_game"
        if reason:
            excluded.append({"app_id": row["app_id"], "review_id": row["review_id"], "reason": reason})
        else:
            seen.add(key)
            clean.append(row)
    return clean, excluded


def save_outputs(output_dir, rows, metadata, app_ids):
    clean, excluded = clean_reviews(rows)
    write_csv(output_dir / "reviews_raw.csv", rows, FIELDS)
    write_csv(output_dir / "reviews_clean.csv", clean, FIELDS)
    write_csv(output_dir / "excluded_reviews.csv", excluded, ["app_id", "review_id", "reason"])
    summaries = []
    for app_id in app_ids:
        subset = [row for row in clean if row["app_id"] == app_id]
        groups = Counter(row["playtime_group"] for row in subset)
        dates = [row["created_at_utc"] for row in subset if row["created_at_utc"]]
        summaries.append({
            "app_id": app_id, "game_name": GAME_NAMES.get(app_id, f"App {app_id}"),
            "raw_count": sum(row["app_id"] == app_id for row in rows),
            "clean_count": len(subset),
            "recommended_count": sum(row["recommended"] for row in subset),
            "not_recommended_count": sum(not row["recommended"] for row in subset),
            "under_10h": groups["under_10h"], "between_10_and_50h": groups["10_to_50h"],
            "at_least_50h": groups["50h_plus"], "missing_playtime": groups["unknown"],
            "without_hangul": sum(not row["has_hangul"] for row in subset),
            "short_review_count": sum(row["short_review"] for row in subset),
            "oldest_review_utc": min(dates, default=""), "newest_review_utc": max(dates, default=""),
        })
    write_csv(output_dir / "summary.csv", summaries, list(summaries[0]))
    metadata.update(finished_at_utc=utc_now(), raw_count=len(rows), clean_count=len(clean), excluded_count=len(excluded))
    (output_dir / "collection_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {output_dir}\nRaw: {len(rows)}, clean: {len(clean)}, excluded: {len(excluded)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Collect Steam reviews to UTF-8 CSV (no packages required).")
    parser.add_argument("--app-ids", nargs="+", type=int, default=list(GAME_NAMES), help="Steam app IDs")
    parser.add_argument("--limit", type=int, default=2000, help="Maximum RAW reviews per game (default: 2000)")
    parser.add_argument("--language", default="koreana", help="Steam language code (default: koreana)")
    parser.add_argument("--interval", type=float, default=1.5, help="Seconds between pages (minimum: 1)")
    parser.add_argument("--output-dir", type=Path, help="New or empty directory; default: timestamped directory")
    args = parser.parse_args()
    if args.limit < 1 or any(app_id < 1 for app_id in args.app_ids):
        parser.error("--limit and app IDs must be positive integers")
    if not math.isfinite(args.interval) or args.interval < 1:
        parser.error("--interval must be a finite number of at least 1 second")
    app_ids = list(dict.fromkeys(args.app_ids))
    output_dir = args.output_dir or Path(__file__).resolve().parent / ("steam_review_data_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        parser.error("Output directory must be new or empty; existing files will not be overwritten")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    metadata = {
        "endpoint": ENDPOINT, "started_at_utc": utc_now(), "status": "running",
        "app_ids": app_ids, "language": args.language, "ordering": "recent",
        "review_type": "all", "purchase_type": "all", "filter_offtopic_activity": True,
        "target_per_game": args.limit, "games": [],
    }
    exit_code = 0
    try:
        for app_id in app_ids:
            game_rows = []
            try:
                summary = collect_game(app_id, args.limit, args.language, args.interval, game_rows, output_dir / f"{app_id}_raw.csv")
                metadata["games"].append({"app_id": app_id, "collected_count": len(game_rows), "query_summary": summary})
            finally:
                rows.extend(game_rows)
        metadata["status"] = "complete"
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as error:
        metadata.update(status="partial", error=str(error) or "Interrupted by user")
        print(f"Collection stopped: {metadata['error']}", file=sys.stderr)
        exit_code = 1
    finally:
        save_outputs(output_dir, rows, metadata, app_ids)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
