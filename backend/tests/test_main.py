import datetime
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import main


class FakeCursor:
    def __init__(self, rows, today_row):
        self.rows = rows
        self.today_row = today_row
        self.last_query = None

    def execute(self, query, params=None):
        self.last_query = query

    def fetchall(self):
        return self.rows

    def fetchone(self):
        if self.last_query and "log_date = CURRENT_DATE" in self.last_query:
            return self.today_row
        return None

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, cursor_factory=None):
        return self._cursor

    def close(self):
        pass


class DashboardTests(unittest.TestCase):
    def test_macro_progress_tier_boundaries(self):
        self.assertEqual(main.macro_progress_tier(74, 100), "green")
        self.assertEqual(main.macro_progress_tier(75, 100), "orange")
        self.assertEqual(main.macro_progress_tier(99, 100), "orange")
        self.assertEqual(main.macro_progress_tier(100, 100), "red")

    def test_accumulate_daily_log_no_double_count(self):
        existing_log = {
            "total_calories_consumed": 100,
            "total_protein_consumed": 10,
            "total_carbs_consumed": 20,
            "total_fats_consumed": 5,
        }
        order_totals = {"calories": 300, "protein": 15, "carbs": 25, "fats": 10}
        result = main.accumulate_daily_log(existing_log, order_totals)
        self.assertEqual(result["total_calories_consumed"], 400)
        self.assertEqual(result["total_protein_consumed"], 25)
        self.assertEqual(result["total_carbs_consumed"], 45)
        self.assertEqual(result["total_fats_consumed"], 15)

    def test_build_weekly_history_returns_7_entries(self):
        end_date = datetime.date.today()
        rows = [
            {"log_date": end_date, "total_calories_consumed": 2200},
            {"log_date": end_date - datetime.timedelta(days=2), "total_calories_consumed": 1800},
        ]
        history = main.build_weekly_history(rows, end_date, 2000)

        self.assertEqual(len(history), 7)
        self.assertEqual(history[0]["calories"], 0)
        self.assertEqual(history[-1]["calories"], 2200)
        self.assertTrue(any(entry["calories"] == 1800 for entry in history))
        self.assertEqual(sum(1 for entry in history if entry["calories"] == 0), 5)

    def test_dashboard_endpoint_returns_7_day_history(self):
        now = datetime.date.today()
        rows = [
            {"log_date": now - datetime.timedelta(days=3), "total_calories_consumed": 1800},
            {"log_date": now, "total_calories_consumed": 2200},
        ]
        today_row = {
            "total_calories_consumed": 2200,
            "total_protein_consumed": 110,
            "total_carbs_consumed": 260,
            "total_fats_consumed": 75,
        }
        cursor = FakeCursor(rows, today_row)
        connection = FakeConnection(cursor)

        with patch("app.main.get_authenticated_user_id", return_value=1), patch(
            "app.main.get_db_connection", return_value=connection
        ):
            client = main.app.test_client()
            response = client.get("/dashboard", headers={"Authorization": "Bearer ignored"})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("weekly", data)
        self.assertEqual(len(data["weekly"]), 7)
        self.assertEqual(data["weekly"][0]["calories"], 0)
        self.assertEqual(data["today"]["total_calories_consumed"], 2200)


if __name__ == "__main__":
    unittest.main()
