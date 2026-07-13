import datetime
import jwt
from unittest.mock import patch, MagicMock

from app.dashboard import JWT_SECRET, JWT_ALGORITHM


def make_mock_connection(fetchone_side_effect=None):
    cursor = MagicMock()
    if fetchone_side_effect is not None:
        cursor.fetchone.side_effect = fetchone_side_effect
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
