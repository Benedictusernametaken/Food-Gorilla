import datetime
import jwt
from unittest.mock import patch, MagicMock

from app.checkout import JWT_SECRET, JWT_ALGORITHM


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


# order_id, vendor_id, order_status, order_date, total_price, total_calories, total_protein, total_carbs, total_fats
CONFIRMED_ORDER_ROW = (55, 7, "confirmed", datetime.datetime(2026, 7, 13, 12, 0, 0), 25.0, 1040, 90, 100, 20)


# ---------------------------------------------------------------------------
# POST /checkout
# ---------------------------------------------------------------------------

def test_checkout_requires_auth(client):
    resp = client.post('/checkout')
    assert resp.status_code == 401


@patch('app.checkout.get_db_connection')
def test_checkout_empty_cart_rejected(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.post('/checkout', headers=auth_header(user_token()))

    assert resp.status_code == 400
    assert "empty" in resp.get_json()["error"]


@patch('app.checkout.get_db_connection')
def test_checkout_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[
            (55,),               # pending order lookup
            CONFIRMED_ORDER_ROW,  # fetch_order_detail: order row
        ],
        fetchall_side_effect=[
            [(1000, 1, "Chicken Bowl", 2, 25.0, 1040, 90, 100, 20)],  # items
            [],  # ingredients for that item
        ],
    )
    mock_get_conn.return_value = connection

    resp = client.post('/checkout', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["order_id"] == 55
    assert body["order_status"] == "confirmed"
    connection.commit.assert_called_once()
    cursor.execute.assert_any_call(
        "UPDATE orders SET order_status = 'confirmed' WHERE order_id = %s",
        (55,),
    )


def test_reset_token_cannot_authenticate_checkout(client):
    token = user_token(purpose="reset")
    resp = client.post('/checkout', headers=auth_header(token))
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /orders
# ---------------------------------------------------------------------------

def test_list_orders_requires_auth(client):
    resp = client.get('/orders')
    assert resp.status_code == 401


@patch('app.checkout.get_db_connection')
def test_list_orders_empty(mock_get_conn, client):
    connection, cursor = make_mock_connection()
    cursor.fetchall.return_value = []
    mock_get_conn.return_value = connection

    resp = client.get('/orders', headers=auth_header(user_token()))

    assert resp.status_code == 200
    assert resp.get_json()["orders"] == []


@patch('app.checkout.get_db_connection')
def test_list_orders_returns_past_orders(mock_get_conn, client):
    connection, cursor = make_mock_connection()
    cursor.fetchall.return_value = [CONFIRMED_ORDER_ROW]
    mock_get_conn.return_value = connection

    resp = client.get('/orders', headers=auth_header(user_token()))

    assert resp.status_code == 200
    orders = resp.get_json()["orders"]
    assert len(orders) == 1
    assert orders[0]["order_id"] == 55
    assert orders[0]["order_status"] == "confirmed"


# ---------------------------------------------------------------------------
# GET /orders/<id>
# ---------------------------------------------------------------------------

def test_get_order_requires_auth(client):
    resp = client.get('/orders/55')
    assert resp.status_code == 401


@patch('app.checkout.get_db_connection')
def test_get_order_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.get('/orders/55', headers=auth_header(user_token()))

    assert resp.status_code == 404


@patch('app.checkout.get_db_connection')
def test_get_order_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[
            (55,),                # ownership/status check
            CONFIRMED_ORDER_ROW,  # fetch_order_detail: order row
        ],
        fetchall_side_effect=[
            [(1000, 1, "Chicken Bowl", 2, 25.0, 1040, 90, 100, 20)],  # items
            [(10, "Extra Chicken Breast", 2)],  # ingredients for that item
        ],
    )
    mock_get_conn.return_value = connection

    resp = client.get('/orders/55', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["order_id"] == 55
    assert len(body["items"]) == 1
    assert body["items"][0]["ingredients"][0]["ingredient_id"] == 10
