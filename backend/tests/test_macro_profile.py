import datetime
import jwt
from unittest.mock import patch, MagicMock

from app.macro_profile import JWT_SECRET, JWT_ALGORITHM


def make_mock_connection(fetchone_return=None, fetchall_return=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_return
    cursor.fetchall.return_value = fetchall_return or []
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


VALID_PAYLOAD = {
    "age": 28,
    "gender": "male",
    "weight_kg": 80,
    "height_cm": 180,
    "activity_level": "moderate",
    "goal": "gain_muscle",
}

PROFILE_ROW = (5, 2800, 210, 315, 78, datetime.datetime(2026, 7, 13, 12, 0, 0))


def test_create_profile_requires_auth(client):
    resp = client.post('/profile/macros', json=VALID_PAYLOAD)
    assert resp.status_code == 401


@patch('app.macro_profile.get_db_connection')
def test_create_profile_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=PROFILE_ROW)
    mock_get_conn.return_value = connection

    resp = client.post('/profile/macros', headers=auth_header(user_token()), json=VALID_PAYLOAD)

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["profile_id"] == 5
    assert body["calories"] == 2800
    connection.commit.assert_called_once()


def test_create_profile_missing_fields(client):
    resp = client.post('/profile/macros', headers=auth_header(user_token()), json={"age": 28})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_profile_invalid_gender(client):
    payload = {**VALID_PAYLOAD, "gender": "robot"}
    resp = client.post('/profile/macros', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


def test_create_profile_invalid_activity_level(client):
    payload = {**VALID_PAYLOAD, "activity_level": "flying"}
    resp = client.post('/profile/macros', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


def test_create_profile_invalid_goal(client):
    payload = {**VALID_PAYLOAD, "goal": "become_immortal"}
    resp = client.post('/profile/macros', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


def test_create_profile_age_out_of_range(client):
    payload = {**VALID_PAYLOAD, "age": 5}
    resp = client.post('/profile/macros', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


def test_create_profile_weight_non_numeric(client):
    payload = {**VALID_PAYLOAD, "weight_kg": "heavy"}
    resp = client.post('/profile/macros', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


@patch('app.macro_profile.get_db_connection')
def test_create_profile_female_lose_weight(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=PROFILE_ROW)
    mock_get_conn.return_value = connection

    payload = {
        "age": 30, "gender": "female", "weight_kg": 65, "height_cm": 165,
        "activity_level": "sedentary", "goal": "lose_weight",
    }
    resp = client.post('/profile/macros', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 201


def test_list_profiles_requires_auth(client):
    resp = client.get('/profile/macros')
    assert resp.status_code == 401


@patch('app.macro_profile.get_db_connection')
def test_list_profiles_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchall_return=[PROFILE_ROW])
    mock_get_conn.return_value = connection

    resp = client.get('/profile/macros', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["profiles"]) == 1
    assert body["profiles"][0]["profile_id"] == 5


def test_delete_profile_requires_auth(client):
    resp = client.delete('/profile/macros/5')
    assert resp.status_code == 401


@patch('app.macro_profile.get_db_connection')
def test_delete_profile_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=(5,))
    mock_get_conn.return_value = connection

    resp = client.delete('/profile/macros/5', headers=auth_header(user_token(user_id=1)))

    assert resp.status_code == 200
    connection.commit.assert_called_once()


@patch('app.macro_profile.get_db_connection')
def test_delete_profile_not_owned_or_missing(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=None)
    mock_get_conn.return_value = connection

    resp = client.delete('/profile/macros/999', headers=auth_header(user_token(user_id=1)))

    assert resp.status_code == 404


def test_reset_token_cannot_authenticate(client):
    token = user_token(purpose="reset")
    resp = client.post('/profile/macros', headers=auth_header(token), json=VALID_PAYLOAD)
    assert resp.status_code == 401
