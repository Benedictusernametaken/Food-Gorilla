import datetime
import jwt
from unittest.mock import patch, MagicMock

from app.cart import JWT_SECRET, JWT_ALGORITHM


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


# meal_id, vendor_id, name, base_price, base_calories, base_protein, base_carbs, base_fats
MEAL_ROW = (1, 7, "Chicken Bowl", 12.5, 520, 45, 50, 10)

# ingredient_id, calories_per_unit, protein_per_unit, carbs_per_unit, fats_per_unit, price_per_unit, default_quantity
INGREDIENT_ROWS = [
    (10, 82, 15, 0, 1, 2.50, 1),
    (11, 48, 1, 3, 4, 1.80, 1),
]

EMPTY_CART_ORDER_ROW = None


# ---------------------------------------------------------------------------
# GET /cart
# ---------------------------------------------------------------------------

def test_get_cart_requires_auth(client):
    resp = client.get('/cart')
    assert resp.status_code == 401


@patch('app.cart.get_db_connection')
def test_get_cart_empty(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.get('/cart', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["order_id"] is None
    assert body["items"] == []
    assert body["total_price"] == 0


@patch('app.cart.get_db_connection')
def test_get_cart_with_items(mock_get_conn, client):
    order_row = (100, 7, 25.0, 1040, 90, 100, 20)
    item_row = (1000, 1, "Chicken Bowl", 2, 25.0, 1040, 90, 100, 20)
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[order_row],
        fetchall_side_effect=[[item_row], [(10, "Extra Chicken Breast", 2)]],
    )
    mock_get_conn.return_value = connection

    resp = client.get('/cart', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["order_id"] == 100
    assert len(body["items"]) == 1
    assert body["items"][0]["order_item_id"] == 1000
    assert body["items"][0]["ingredients"][0]["ingredient_id"] == 10


# ---------------------------------------------------------------------------
# POST /cart/items
# ---------------------------------------------------------------------------

def test_add_to_cart_requires_auth(client):
    resp = client.post('/cart/items', json={"meal_id": 1})
    assert resp.status_code == 401


def test_add_to_cart_missing_meal_id(client):
    resp = client.post('/cart/items', headers=auth_header(user_token()), json={})
    assert resp.status_code == 400


def test_add_to_cart_invalid_quantity(client):
    resp = client.post(
        '/cart/items', headers=auth_header(user_token()),
        json={"meal_id": 1, "quantity": 0},
    )
    assert resp.status_code == 400


def test_add_to_cart_invalid_ingredients_type(client):
    resp = client.post(
        '/cart/items', headers=auth_header(user_token()),
        json={"meal_id": 1, "ingredients": [1, 2]},
    )
    assert resp.status_code == 400


@patch('app.cart.get_db_connection')
def test_add_to_cart_meal_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.post(
        '/cart/items', headers=auth_header(user_token()), json={"meal_id": 999},
    )

    assert resp.status_code == 404


@patch('app.cart.get_db_connection')
def test_add_to_cart_unknown_ingredient(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[MEAL_ROW])
    cursor.fetchall.side_effect = [INGREDIENT_ROWS]
    mock_get_conn.return_value = connection

    resp = client.post(
        '/cart/items', headers=auth_header(user_token()),
        json={"meal_id": 1, "ingredients": {"999": 1}},
    )

    assert resp.status_code == 400


@patch('app.cart.get_db_connection')
def test_add_to_cart_creates_new_order(mock_get_conn, client):
    # meal lookup -> no existing pending order -> insert order -> insert item -> fetch_cart
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[
            MEAL_ROW,          # fetch_meal_with_ingredients: meal row
            None,               # no existing pending order
            (55,),              # new order_id
            (500,),             # new order_item_id
            (12.5, 520, 45, 50, 10),  # recompute_order_totals: SUM(...)
            (55, 7, 12.5, 520, 45, 50, 10),  # fetch_cart: order row
        ],
        fetchall_side_effect=[
            INGREDIENT_ROWS,    # fetch_meal_with_ingredients: ingredient rows
            [(500, 1, "Chicken Bowl", 1, 12.5, 520, 45, 50, 10)],  # fetch_cart: items
            [],                 # fetch_cart: ingredients for that item
        ],
    )
    mock_get_conn.return_value = connection

    resp = client.post(
        '/cart/items', headers=auth_header(user_token()), json={"meal_id": 1},
    )

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["order_id"] == 55
    connection.commit.assert_called_once()


@patch('app.cart.get_db_connection')
def test_add_to_cart_different_vendor_rejected(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[
            MEAL_ROW,        # vendor_id 7
            (55, 999),       # existing pending order for a different vendor
        ],
        fetchall_side_effect=[INGREDIENT_ROWS],
    )
    mock_get_conn.return_value = connection

    resp = client.post(
        '/cart/items', headers=auth_header(user_token()), json={"meal_id": 1},
    )

    assert resp.status_code == 400
    assert "vendor" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# PUT /cart/items/<id>
# ---------------------------------------------------------------------------

def test_update_cart_item_requires_auth(client):
    resp = client.put('/cart/items/1', json={"quantity": 2})
    assert resp.status_code == 401


def test_update_cart_item_nothing_to_update(client):
    resp = client.put('/cart/items/1', headers=auth_header(user_token()), json={})
    assert resp.status_code == 400


@patch('app.cart.get_db_connection')
def test_update_cart_item_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.put(
        '/cart/items/1', headers=auth_header(user_token()), json={"quantity": 2},
    )

    assert resp.status_code == 404


@patch('app.cart.get_db_connection')
def test_update_cart_item_quantity_only(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[
            (55, 1, 1),          # order_id, meal_id, current_quantity
            MEAL_ROW,            # fetch_meal_with_ingredients: meal row
            (25.0, 1040, 90, 100, 20),  # recompute_order_totals: SUM(...)
            (55, 7, 25.0, 1040, 90, 100, 20),  # fetch_cart: order row
        ],
        fetchall_side_effect=[
            [(10, 1), (11, 1)],  # existing order_item_ingredients (quantity-only update)
            INGREDIENT_ROWS,     # fetch_meal_with_ingredients: ingredient rows
            [(1000, 1, "Chicken Bowl", 2, 25.0, 1040, 90, 100, 20)],  # fetch_cart items
            [],
        ],
    )
    mock_get_conn.return_value = connection

    resp = client.put(
        '/cart/items/1000', headers=auth_header(user_token()), json={"quantity": 2},
    )

    assert resp.status_code == 200
    connection.commit.assert_called_once()


# ---------------------------------------------------------------------------
# DELETE /cart/items/<id>
# ---------------------------------------------------------------------------

def test_remove_cart_item_requires_auth(client):
    resp = client.delete('/cart/items/1')
    assert resp.status_code == 401


@patch('app.cart.get_db_connection')
def test_remove_cart_item_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.delete('/cart/items/1', headers=auth_header(user_token()))

    assert resp.status_code == 404


@patch('app.cart.get_db_connection')
def test_remove_cart_item_success_leaves_other_items(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[
            (55,),   # order_id owning this item
            (1,),    # COUNT(*) remaining items -> 1
            (12.5, 520, 45, 50, 10),  # recompute_order_totals: SUM(...)
            (55, 7, 12.5, 520, 45, 50, 10),  # fetch_cart: order row
        ],
        fetchall_side_effect=[
            [(2000, 1, "Chicken Bowl", 1, 12.5, 520, 45, 50, 10)],  # fetch_cart items
            [],
        ],
    )
    mock_get_conn.return_value = connection

    resp = client.delete('/cart/items/1000', headers=auth_header(user_token()))

    assert resp.status_code == 200
    connection.commit.assert_called_once()


@patch('app.cart.get_db_connection')
def test_remove_last_cart_item_empties_cart(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[
            (55,),   # order_id owning this item
            (0,),    # COUNT(*) remaining items -> 0, order gets deleted
            None,    # fetch_cart: no pending order left
        ],
    )
    mock_get_conn.return_value = connection

    resp = client.delete('/cart/items/1000', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["order_id"] is None
    assert body["items"] == []


# ---------------------------------------------------------------------------
# DELETE /cart
# ---------------------------------------------------------------------------

def test_clear_cart_requires_auth(client):
    resp = client.delete('/cart')
    assert resp.status_code == 401


@patch('app.cart.get_db_connection')
def test_clear_cart_success(mock_get_conn, client):
    connection, cursor = make_mock_connection()
    mock_get_conn.return_value = connection

    resp = client.delete('/cart', headers=auth_header(user_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["items"] == []
    connection.commit.assert_called_once()


def test_reset_token_cannot_authenticate_cart(client):
    token = user_token(purpose="reset")
    resp = client.get('/cart', headers=auth_header(token))
    assert resp.status_code == 401
