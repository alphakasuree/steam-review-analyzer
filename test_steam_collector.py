"""네트워크 없이 페이지 이동, 원문 저장, 정리 규칙을 확인합니다."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_steam_reviews as collector


def review(review_id, text="전투는 좋지만 버그가 많다", minutes=600):
    return {
        "recommendationid": review_id, "review": text, "voted_up": True,
        "author": {"playtime_at_review": minutes}, "language": "koreana",
        "timestamp_created": 1700000000, "timestamp_updated": 1700000000,
    }


class CollectorTests(unittest.TestCase):
    def test_pagination_deduplication_and_csv_roundtrip(self):
        pages = [
            {"reviews": [review("1", '음악, "최고"\n재미있다')], "cursor": "next+/=", "query_summary": {}},
            {"reviews": [review("1"), review("2")], "cursor": "last"},
        ]
        rows = []
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            output = Path(temporary) / "reviews.csv"
            with patch.object(collector, "fetch_page", side_effect=pages) as fetch, patch.object(collector.time, "sleep"):
                collector.collect_game(1245620, 2, "koreana", 1.5, rows, output)
            self.assertEqual(fetch.call_args_list[1].args[0]["cursor"], "next+/=")
            with output.open(encoding="utf-8-sig", newline="") as file:
                saved = list(csv.DictReader(file))
            self.assertEqual([row["review_id"] for row in saved], ["1", "2"])
            self.assertEqual(saved[0]["review_text"], '음악, "최고"\n재미있다')

    def test_cleaning_is_within_game_and_preserves_raw(self):
        rows = [collector.make_row(review(str(index), text), app, "now") for index, (app, text) in enumerate([
            (1, "재미 있다"), (1, "재미\n있다"), (2, "재미 있다"), (1, " "), (1, "!!!"),
        ])]
        clean, excluded = collector.clean_reviews(rows)
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(clean), 2)
        self.assertEqual([item["reason"] for item in excluded], ["duplicate_text_within_game", "empty", "symbols_only"])

    def test_playtime_boundaries_and_missing(self):
        for minutes, group in [(None, "unknown"), (0, "under_10h"), (599, "under_10h"), (600, "10_to_50h"), (3000, "50h_plus")]:
            row = collector.make_row(review("1", minutes=minutes), 1, "now")
            self.assertEqual(row["playtime_group"], group)
            self.assertEqual(row["playtime_at_review_hours"], None if minutes is None else round(minutes / 60, 2))

    def test_repeated_cursor_stops_and_preserves_checkpoint(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            output = Path(temporary) / "reviews.csv"
            with patch.object(collector, "fetch_page", return_value={"reviews": [review("1")], "cursor": "*"}):
                with self.assertRaises(RuntimeError):
                    collector.collect_game(1, 2, "koreana", 1.5, [], output)
            self.assertTrue(output.exists())

    def test_rate_limit_retry_after(self):
        self.assertEqual(collector.retry_delay("15", 0), 15)
        self.assertEqual(collector.retry_delay("invalid", 0), 2)


if __name__ == "__main__":
    unittest.main()
