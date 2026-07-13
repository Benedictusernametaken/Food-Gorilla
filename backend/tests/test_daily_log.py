import datetime
import jwt
from unittest.mock import patch, MagicMock

from app.daily_log import JWT_SECRET, JWT_ALGORITHM


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


# log_date, total_calories_consumed, total_protein_consumed, total_carbs_consumed, total_fats_consumed
LOG_ROW = (datetime.date(2026, 7, 13), 1040, 90, 100, 20)


# ---------------------------------------------------------------------------
# GET /daily-log
# ---------------------------------------------------------------------------

def test_get_daily_log_requires_auth(client):
    resp = client.get('/daily-log')
    assert resp.status_code == 401


@patch('app.daily_log.get_db_connection')
def test_get_daily_log_no_entry_today_returns_zeros(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.get('/daily-log', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total_calories_consumed"] == 0
    assert body["log_date"] is None


@patch('app.daily_log.get_db_connection')
def test_get_daily_log_today(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[LOG_ROW])
    mock_get_conn.return_value = connection

    resp = client.get('/daily-log', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["log_date"] == "2026-07-13"
    assert body["total_calories_consumed"] == 1040
    assert body["total_protein_consumed"] == 90


@patch('app.daily_log.get_db_connection')
def test_get_daily_log_specific_date(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[LOG_ROW])
    mock_get_conn.return_value = connection

    resp = client.get('/daily-log?date=2026-07-13', headers=auth_header(user_token()))

    assert resp.status_code == 200
    cursor.execute.assert_any_call(
        "SELECT log_date, total_calories_consumed, total_protein_consumed, "
        "total_carbs_consumed, total_fats_consumed FROM daily_logs "
        "WHERE user_id = %s AND log_date = %s",
        (1, "2026-07-13"),
    )


def test_get_daily_log_invalid_date_format(client):
    resp = client.get('/daily-log?date=07-13-2026', headers=auth_header(user_token()))
    assert resp.status_code == 400


def test_reset_token_cannot_authenticate_daily_log(client):
    token = user_token(purpose="reset")
    resp = client.get('/daily-log', headers=auth_header(token))
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /daily-log/history
# ---------------------------------------------------------------------------

def test_get_daily_log_history_requires_auth(client):
    resp = client.get('/daily-log/history')
    assert resp.status_code == 401


@patch('app.daily_log.get_db_connection')
def test_get_daily_log_history_empty(mock_get_conn, client):
    connection, cursor = make_mock_connection()
    cursor.fetchall.return_value = []
    mock_get_conn.return_value = connection

    resp = client.get('/daily-log/history', headers=auth_header(user_token()))

    assert resp.status_code == 200
    assert resp.get_json()["logs"] == []


@patch('app.daily_log.get_db_connection')
def test_get_daily_log_history_returns_logs(mock_get_conn, client):
    connection, cursor = make_mock_connection()
    cursor.fetchall.return_value = [LOG_ROW]
    mock_get_conn.return_value = connection

    resp = client.get('/daily-log/history', headers=auth_header(user_token()))

    assert resp.status_code == 200
    logs = resp.get_json()["logs"]
    assert len(logs) == 1
    assert logs[0]["log_date"] == "2026-07-13"
    assert logs[0]["total_calories_consumed"] == 1040
