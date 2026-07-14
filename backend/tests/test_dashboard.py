import datetime
import jwt
from unittest.mock import patch, MagicMock

from app.dashboard import JWT_SECRET, JWT_ALGORITHM


def make_mock_connection(fetchone_side_effect=None, fetchall_side_effect=None):
    cursor = MagicMock()
    if fetchone_side_effect is not None:
        cursor.fetchone.side_effect = fetchone_side_effect
    if fetchall_side_effect is not None:
        cursor.fetchall.side_effect = fetchall_side_effect
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection, cursor


def user_token(user_id=1, username="someuser", purpose="auth"):
    payload = {
        "user_id": user_id,
        "username": username,
        "purpose": purpose,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# daily_calorie_target, target_protein_g, target_carbs_g, target_fats_g
PROFILE_ROW = (2800, 210, 315, 78)

# log_date, total_calories_consumed, total_protein_consumed, total_carbs_consumed, total_fats_consumed
LOG_ROW = (datetime.date(2026, 7, 13), 3200, 100, 100, 20)
LOG_ROW_UNDER_TARGET = (datetime.date(2026, 7, 13), 1000, 90, 100, 20)


def test_get_dashboard_requires_auth(client):
    resp = client.get('/dashboard')
    assert resp.status_code == 401


def test_reset_token_cannot_authenticate_dashboard(client):
    token = user_token(purpose="reset")
    resp = client.get('/dashboard', headers=auth_header(token))
    assert resp.status_code == 401


@patch('app.dashboard.get_db_connection')
def test_dashboard_no_profile_no_log(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None, None])
    mock_get_conn.return_value = connection

    resp = client.get('/dashboard', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["targets"] is None
    assert body["log_date"] is None
    assert body["consumed"]["calories"] == 0
    assert body["remaining"] is None
    assert body["exceeded"] == {"calories": False, "protein": False, "carbs": False, "fats": False}


@patch('app.dashboard.get_db_connection')
def test_dashboard_under_target(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[PROFILE_ROW, LOG_ROW_UNDER_TARGET])
    mock_get_conn.return_value = connection

    resp = client.get('/dashboard', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["targets"]["calories"] == 2800
    assert body["consumed"]["calories"] == 1000
    assert body["remaining"]["calories"] == 1800
    assert body["exceeded"] == {"calories": False, "protein": False, "carbs": False, "fats": False}


@patch('app.dashboard.get_db_connection')
def test_dashboard_exceeded_calories(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[PROFILE_ROW, LOG_ROW])
    mock_get_conn.return_value = connection

    resp = client.get('/dashboard', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["exceeded"]["calories"] is True
    assert body["exceeded"]["protein"] is False
    assert body["remaining"]["calories"] == -400


@patch('app.dashboard.get_db_connection')
def test_dashboard_profile_but_no_log_today(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[PROFILE_ROW, None])
    mock_get_conn.return_value = connection

    resp = client.get('/dashboard', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["targets"]["calories"] == 2800
    assert body["consumed"] == {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}
    assert body["exceeded"] == {"calories": False, "protein": False, "carbs": False, "fats": False}


# ---------------------------------------------------------------------------
# GET /dashboard/weekly
# ---------------------------------------------------------------------------

# log_date, total_calories_consumed, total_protein_consumed, total_carbs_consumed, total_fats_consumed
WEEKLY_ROWS_DESC = [
    (datetime.date(2026, 7, 13), 3200, 100, 100, 20),
    (datetime.date(2026, 7, 12), 2000, 90, 100, 20),
    (datetime.date(2026, 7, 11), 2900, 95, 100, 20),
]


def test_get_weekly_dashboard_requires_auth(client):
    resp = client.get('/dashboard/weekly')
    assert resp.status_code == 401


@patch('app.dashboard.get_db_connection')
def test_weekly_dashboard_no_logs(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[PROFILE_ROW], fetchall_side_effect=[[]])
    mock_get_conn.return_value = connection

    resp = client.get('/dashboard/weekly', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["days"] == []
    assert body["summary"] == {"average_calories": 0, "days_on_track": 0, "times_exceeded": 0, "days_logged": 0}


@patch('app.dashboard.get_db_connection')
def test_weekly_dashboard_with_logs(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[PROFILE_ROW], fetchall_side_effect=[WEEKLY_ROWS_DESC])
    mock_get_conn.return_value = connection

    resp = client.get('/dashboard/weekly', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["calorie_target"] == 2800
    # chronological order, oldest first
    assert [d["date"] for d in body["days"]] == ["2026-07-11", "2026-07-12", "2026-07-13"]
    assert body["days"][2]["exceeded"] is True
    assert body["days"][1]["exceeded"] is False
    assert body["summary"]["days_on_track"] == 1
    assert body["summary"]["times_exceeded"] == 2
    assert body["summary"]["average_calories"] == round((3200 + 2000 + 2900) / 3)


@patch('app.dashboard.get_db_connection')
def test_weekly_dashboard_no_profile(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None], fetchall_side_effect=[WEEKLY_ROWS_DESC])
    mock_get_conn.return_value = connection

    resp = client.get('/dashboard/weekly', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["calorie_target"] is None
    assert all(d["exceeded"] is False for d in body["days"])
    assert all(d["percent_of_target"] is None for d in body["days"])


# ---------------------------------------------------------------------------
# POST /dashboard/reset
# ---------------------------------------------------------------------------

def test_reset_daily_log_requires_auth(client):
    resp = client.post('/dashboard/reset')
    assert resp.status_code == 401


@patch('app.dashboard.get_db_connection')
def test_reset_daily_log_success(mock_get_conn, client):
    connection, cursor = make_mock_connection()
    mock_get_conn.return_value = connection

    resp = client.post('/dashboard/reset', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["consumed"] == {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}
    connection.commit.assert_called_once()
