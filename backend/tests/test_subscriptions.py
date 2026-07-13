import datetime
import jwt
from unittest.mock import patch, MagicMock

from app.subscriptions import JWT_SECRET, JWT_ALGORITHM


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


# meal_id, name, base_price, base_calories, base_protein, base_carbs, base_fats
MEAL_ROW_1 = (1, "Chicken Bowl", 12.5, 520, 45, 50, 10)
MEAL_ROW_2 = (2, "Salmon Plate", 15.0, 600, 50, 40, 20)

# subscription_id, start_date, end_date, status
SUB_ROW = (10, datetime.date(2026, 7, 20), datetime.date(2026, 8, 20), "active")

VALID_PAYLOAD = {
    "start_date": "2026-07-20",
    "end_date": "2026-08-20",
    "schedule": [
        {"day_of_week": 1, "meal_id": 1, "time_slot": "lunch"},
        {"day_of_week": 3, "meal_id": 2, "time_slot": "dinner"},
    ],
}


# ---------------------------------------------------------------------------
# POST /subscriptions
# ---------------------------------------------------------------------------

def test_create_subscription_requires_auth(client):
    resp = client.post('/subscriptions', json=VALID_PAYLOAD)
    assert resp.status_code == 401


def test_reset_token_cannot_authenticate(client):
    token = user_token(purpose="reset")
    resp = client.post('/subscriptions', headers=auth_header(token), json=VALID_PAYLOAD)
    assert resp.status_code == 401


@patch('app.subscriptions.get_db_connection')
def test_create_subscription_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[SUB_ROW, (100,), (101,)],
        fetchall_side_effect=[[MEAL_ROW_1, MEAL_ROW_2]],
    )
    mock_get_conn.return_value = connection

    resp = client.post('/subscriptions', headers=auth_header(user_token()), json=VALID_PAYLOAD)

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["subscription_id"] == 10
    assert body["start_date"] == "2026-07-20"
    assert body["status"] == "active"
    assert len(body["schedule"]) == 2
    assert body["schedule"][0]["day_name"] == "Monday"
    assert body["schedule"][0]["schedule_id"] == 100
    assert body["total_cost"] == 27.5
    assert body["total_calories"] == 1120
    connection.commit.assert_called_once()


def test_create_subscription_missing_schedule(client):
    payload = {"start_date": "2026-07-20", "end_date": "2026-08-20"}
    resp = client.post('/subscriptions', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


def test_create_subscription_bad_date_format(client):
    payload = {**VALID_PAYLOAD, "start_date": "07-20-2026"}
    resp = client.post('/subscriptions', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


def test_create_subscription_end_before_start(client):
    payload = {**VALID_PAYLOAD, "start_date": "2026-08-20", "end_date": "2026-07-20"}
    resp = client.post('/subscriptions', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


def test_create_subscription_invalid_day_of_week(client):
    payload = {**VALID_PAYLOAD, "schedule": [{"day_of_week": 6, "meal_id": 1, "time_slot": "lunch"}]}
    resp = client.post('/subscriptions', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


def test_create_subscription_invalid_time_slot(client):
    payload = {**VALID_PAYLOAD, "schedule": [{"day_of_week": 1, "meal_id": 1, "time_slot": "brunch"}]}
    resp = client.post('/subscriptions', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


def test_create_subscription_duplicate_day_and_slot(client):
    payload = {**VALID_PAYLOAD, "schedule": [
        {"day_of_week": 1, "meal_id": 1, "time_slot": "lunch"},
        {"day_of_week": 1, "meal_id": 2, "time_slot": "lunch"},
    ]}
    resp = client.post('/subscriptions', headers=auth_header(user_token()), json=payload)
    assert resp.status_code == 400


@patch('app.subscriptions.get_db_connection')
def test_create_subscription_meal_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchall_side_effect=[[MEAL_ROW_1]])
    mock_get_conn.return_value = connection

    resp = client.post('/subscriptions', headers=auth_header(user_token()), json=VALID_PAYLOAD)

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /subscriptions
# ---------------------------------------------------------------------------

def test_list_subscriptions_requires_auth(client):
    resp = client.get('/subscriptions')
    assert resp.status_code == 401


@patch('app.subscriptions.get_db_connection')
def test_list_subscriptions_empty(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchall_side_effect=[[]])
    mock_get_conn.return_value = connection

    resp = client.get('/subscriptions', headers=auth_header(user_token()))

    assert resp.status_code == 200
    assert resp.get_json()["subscriptions"] == []


@patch('app.subscriptions.get_db_connection')
def test_list_subscriptions_success(mock_get_conn, client):
    schedule_rows = [
        (10, 100, 1, "lunch", *MEAL_ROW_1),
        (10, 101, 3, "dinner", *MEAL_ROW_2),
    ]
    connection, cursor = make_mock_connection(fetchall_side_effect=[[SUB_ROW], schedule_rows])
    mock_get_conn.return_value = connection

    resp = client.get('/subscriptions', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["subscriptions"]) == 1
    assert body["subscriptions"][0]["total_cost"] == 27.5
    assert len(body["subscriptions"][0]["schedule"]) == 2


# ---------------------------------------------------------------------------
# GET /subscriptions/<id>
# ---------------------------------------------------------------------------

def test_get_subscription_requires_auth(client):
    resp = client.get('/subscriptions/10')
    assert resp.status_code == 401


@patch('app.subscriptions.get_db_connection')
def test_get_subscription_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchall_side_effect=[[]])
    mock_get_conn.return_value = connection

    resp = client.get('/subscriptions/999', headers=auth_header(user_token()))

    assert resp.status_code == 404


@patch('app.subscriptions.get_db_connection')
def test_get_subscription_success(mock_get_conn, client):
    schedule_rows = [(10, 100, 1, "lunch", *MEAL_ROW_1)]
    connection, cursor = make_mock_connection(fetchall_side_effect=[[SUB_ROW], schedule_rows])
    mock_get_conn.return_value = connection

    resp = client.get('/subscriptions/10', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["subscription_id"] == 10
    assert body["schedule"][0]["meal_name"] == "Chicken Bowl"


# ---------------------------------------------------------------------------
# PUT /subscriptions/<id>/schedule/<schedule_id>
# ---------------------------------------------------------------------------

# schedule_id, delivery_day_of_week, delivery_time_slot, meal_id
OWNED_ROW = (100, 1, "lunch", 1)

# Monday 2026-07-20 08:00 — well before the 10:00 cutoff for a 12:00 lunch slot.
BEFORE_CUTOFF = datetime.datetime(2026, 7, 20, 8, 0)
# Monday 2026-07-20 11:00 — inside the 2-hour cutoff window before lunch.
AFTER_CUTOFF = datetime.datetime(2026, 7, 20, 11, 0)


def test_modify_scheduled_meal_requires_auth(client):
    resp = client.put('/subscriptions/10/schedule/100', json={"meal_id": 2})
    assert resp.status_code == 401


def test_modify_scheduled_meal_no_fields(client):
    resp = client.put('/subscriptions/10/schedule/100', headers=auth_header(user_token()), json={})
    assert resp.status_code == 400


def test_modify_scheduled_meal_invalid_time_slot(client):
    resp = client.put('/subscriptions/10/schedule/100', headers=auth_header(user_token()), json={"time_slot": "brunch"})
    assert resp.status_code == 400


@patch('app.subscriptions.get_db_connection')
def test_modify_scheduled_meal_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.put('/subscriptions/10/schedule/999', headers=auth_header(user_token()), json={"meal_id": 2})

    assert resp.status_code == 404


@patch('app.subscriptions.current_time')
@patch('app.subscriptions.get_db_connection')
def test_modify_scheduled_meal_success(mock_get_conn, mock_now, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[OWNED_ROW, MEAL_ROW_2])
    mock_get_conn.return_value = connection
    mock_now.return_value = BEFORE_CUTOFF

    resp = client.put('/subscriptions/10/schedule/100', headers=auth_header(user_token()), json={"meal_id": 2})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meal_id"] == 2
    assert body["meal_name"] == "Salmon Plate"
    connection.commit.assert_called_once()


@patch('app.subscriptions.current_time')
@patch('app.subscriptions.get_db_connection')
def test_modify_scheduled_meal_after_cutoff(mock_get_conn, mock_now, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[OWNED_ROW])
    mock_get_conn.return_value = connection
    mock_now.return_value = AFTER_CUTOFF

    resp = client.put('/subscriptions/10/schedule/100', headers=auth_header(user_token()), json={"meal_id": 2})

    assert resp.status_code == 409


@patch('app.subscriptions.current_time')
@patch('app.subscriptions.get_db_connection')
def test_modify_scheduled_meal_new_meal_not_found(mock_get_conn, mock_now, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[OWNED_ROW, None])
    mock_get_conn.return_value = connection
    mock_now.return_value = BEFORE_CUTOFF

    resp = client.put('/subscriptions/10/schedule/100', headers=auth_header(user_token()), json={"meal_id": 999})

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /subscriptions/<id>/schedule/<schedule_id>
# ---------------------------------------------------------------------------

def test_cancel_scheduled_meal_requires_auth(client):
    resp = client.delete('/subscriptions/10/schedule/100')
    assert resp.status_code == 401


@patch('app.subscriptions.get_db_connection')
def test_cancel_scheduled_meal_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.delete('/subscriptions/10/schedule/999', headers=auth_header(user_token()))

    assert resp.status_code == 404


@patch('app.subscriptions.current_time')
@patch('app.subscriptions.get_db_connection')
def test_cancel_scheduled_meal_success(mock_get_conn, mock_now, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[OWNED_ROW])
    mock_get_conn.return_value = connection
    mock_now.return_value = BEFORE_CUTOFF

    resp = client.delete('/subscriptions/10/schedule/100', headers=auth_header(user_token()))

    assert resp.status_code == 200
    connection.commit.assert_called_once()


@patch('app.subscriptions.current_time')
@patch('app.subscriptions.get_db_connection')
def test_cancel_scheduled_meal_after_cutoff(mock_get_conn, mock_now, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[OWNED_ROW])
    mock_get_conn.return_value = connection
    mock_now.return_value = AFTER_CUTOFF

    resp = client.delete('/subscriptions/10/schedule/100', headers=auth_header(user_token()))

    assert resp.status_code == 409
