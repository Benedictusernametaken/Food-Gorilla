import datetime
import jwt
from unittest.mock import patch, MagicMock

from app.vendor_meals import JWT_SECRET, JWT_ALGORITHM


def make_mock_connection(fetchone_return=None, fetchall_return=None,
                          fetchone_side_effect=None, fetchall_side_effect=None):
    cursor = MagicMock()
    if fetchone_side_effect is not None:
        cursor.fetchone.side_effect = fetchone_side_effect
    else:
        cursor.fetchone.return_value = fetchone_return
    if fetchall_side_effect is not None:
        cursor.fetchall.side_effect = fetchall_side_effect
    else:
        cursor.fetchall.return_value = fetchall_return or []
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection, cursor


def vendor_token(vendor_id=1, restaurant_name="Test Kitchen", role="vendor"):
    payload = {
        "vendor_id": vendor_id,
        "restaurant_name": restaurant_name,
        "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


MEAL_ROW = (10, 1, "Chicken Bowl", "desc", 12.5, 500, 40, 50, 10, True)

# ingredient_id, name, unit, calories_per_unit, protein_per_unit, carbs_per_unit, fats_per_unit, price_per_unit
INGREDIENT_CATALOG_ROW = (1, "Extra Chicken Breast", "50g", 82, 15, 0, 1, 2.5)

# ...same columns + default_quantity
MEAL_INGREDIENT_ROW = (1, "Extra Chicken Breast", "50g", 82, 15, 0, 1, 2.5, 2)


def test_list_meals_requires_auth(client):
    resp = client.get('/vendor/meals')
    assert resp.status_code == 401


def test_list_meals_rejects_customer_token(client):
    token = vendor_token(role="not-vendor")
    resp = client.get('/vendor/meals', headers=auth_header(token))
    assert resp.status_code == 401


@patch('app.vendor_meals.get_db_connection')
def test_list_meals_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchall_return=[MEAL_ROW])
    mock_get_conn.return_value = connection

    resp = client.get('/vendor/meals', headers=auth_header(vendor_token(vendor_id=1)))

    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["meals"]) == 1
    assert body["meals"][0]["name"] == "Chicken Bowl"


@patch('app.vendor_meals.get_db_connection')
def test_create_meal_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=MEAL_ROW)
    mock_get_conn.return_value = connection

    resp = client.post('/vendor/meals', headers=auth_header(vendor_token(vendor_id=1)), json={
        "name": "Chicken Bowl",
        "description": "desc",
        "price": 12.5,
        "calories": 500,
        "protein": 40,
        "carbs": 50,
        "fats": 10,
    })

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["meal_id"] == 10
    assert body["is_available"] is True
    connection.commit.assert_called_once()


def test_create_meal_missing_fields(client):
    resp = client.post('/vendor/meals', headers=auth_header(vendor_token()), json={"name": "Only Name"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_meal_non_numeric(client):
    resp = client.post('/vendor/meals', headers=auth_header(vendor_token()), json={
        "name": "Bad Meal", "price": "free", "calories": 500, "protein": 40, "carbs": 50, "fats": 10,
    })
    assert resp.status_code == 400


def test_create_meal_negative_values(client):
    resp = client.post('/vendor/meals', headers=auth_header(vendor_token()), json={
        "name": "Bad Meal", "price": -5, "calories": 500, "protein": 40, "carbs": 50, "fats": 10,
    })
    assert resp.status_code == 400


def test_create_meal_requires_auth(client):
    resp = client.post('/vendor/meals', json={
        "name": "Chicken Bowl", "price": 12.5, "calories": 500, "protein": 40, "carbs": 50, "fats": 10,
    })
    assert resp.status_code == 401


@patch('app.vendor_meals.get_db_connection')
def test_get_meal_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=MEAL_ROW)
    mock_get_conn.return_value = connection

    resp = client.get('/vendor/meals/10', headers=auth_header(vendor_token(vendor_id=1)))

    assert resp.status_code == 200
    assert resp.get_json()["meal_id"] == 10


@patch('app.vendor_meals.get_db_connection')
def test_get_meal_not_found_or_not_owned(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=None)
    mock_get_conn.return_value = connection

    resp = client.get('/vendor/meals/999', headers=auth_header(vendor_token(vendor_id=1)))

    assert resp.status_code == 404


@patch('app.vendor_meals.get_db_connection')
def test_update_meal_success(mock_get_conn, client):
    connection, cursor = make_mock_connection()
    cursor.fetchone.side_effect = [MEAL_ROW, MEAL_ROW]
    mock_get_conn.return_value = connection

    resp = client.put('/vendor/meals/10', headers=auth_header(vendor_token(vendor_id=1)), json={
        "name": "Chicken Bowl", "price": 13.0, "calories": 500, "protein": 40, "carbs": 50, "fats": 10,
    })

    assert resp.status_code == 200
    connection.commit.assert_called_once()


@patch('app.vendor_meals.get_db_connection')
def test_update_meal_not_owned(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=None)
    mock_get_conn.return_value = connection

    resp = client.put('/vendor/meals/999', headers=auth_header(vendor_token(vendor_id=1)), json={
        "name": "X", "price": 1, "calories": 1, "protein": 1, "carbs": 1, "fats": 1,
    })

    assert resp.status_code == 404


@patch('app.vendor_meals.get_db_connection')
def test_delete_meal_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=(10,))
    mock_get_conn.return_value = connection

    resp = client.delete('/vendor/meals/10', headers=auth_header(vendor_token(vendor_id=1)))

    assert resp.status_code == 200
    connection.commit.assert_called_once()


@patch('app.vendor_meals.get_db_connection')
def test_delete_meal_not_owned(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=None)
    mock_get_conn.return_value = connection

    resp = client.delete('/vendor/meals/999', headers=auth_header(vendor_token(vendor_id=1)))

    assert resp.status_code == 404


@patch('app.vendor_meals.get_db_connection')
def test_toggle_availability_success(mock_get_conn, client):
    off_row = MEAL_ROW[:-1] + (False,)
    connection, cursor = make_mock_connection(fetchone_return=off_row)
    mock_get_conn.return_value = connection

    resp = client.patch('/vendor/meals/10/availability', headers=auth_header(vendor_token(vendor_id=1)), json={
        "is_available": False,
    })

    assert resp.status_code == 200
    assert resp.get_json()["is_available"] is False
    connection.commit.assert_called_once()


def test_toggle_availability_missing_field(client):
    resp = client.patch('/vendor/meals/10/availability', headers=auth_header(vendor_token()), json={})
    assert resp.status_code == 400


@patch('app.vendor_meals.get_db_connection')
def test_toggle_availability_not_owned(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=None)
    mock_get_conn.return_value = connection

    resp = client.patch('/vendor/meals/999/availability', headers=auth_header(vendor_token(vendor_id=1)), json={
        "is_available": True,
    })

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET/POST /vendor/ingredients
# ---------------------------------------------------------------------------

def test_list_ingredients_requires_auth(client):
    resp = client.get('/vendor/ingredients')
    assert resp.status_code == 401


@patch('app.vendor_meals.get_db_connection')
def test_list_ingredients_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchall_return=[INGREDIENT_CATALOG_ROW])
    mock_get_conn.return_value = connection

    resp = client.get('/vendor/ingredients', headers=auth_header(vendor_token()))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ingredients"][0]["name"] == "Extra Chicken Breast"


def test_create_ingredient_requires_auth(client):
    resp = client.post('/vendor/ingredients', json={
        "name": "Rice", "calories_per_unit": 100, "protein_per_unit": 2,
        "carbs_per_unit": 22, "fats_per_unit": 0, "price_per_unit": 0.5,
    })
    assert resp.status_code == 401


def test_create_ingredient_missing_fields(client):
    resp = client.post('/vendor/ingredients', headers=auth_header(vendor_token()), json={"name": "Rice"})
    assert resp.status_code == 400


def test_create_ingredient_non_numeric(client):
    resp = client.post('/vendor/ingredients', headers=auth_header(vendor_token()), json={
        "name": "Rice", "calories_per_unit": "lots", "protein_per_unit": 2,
        "carbs_per_unit": 22, "fats_per_unit": 0, "price_per_unit": 0.5,
    })
    assert resp.status_code == 400


def test_create_ingredient_negative_values(client):
    resp = client.post('/vendor/ingredients', headers=auth_header(vendor_token()), json={
        "name": "Rice", "calories_per_unit": -1, "protein_per_unit": 2,
        "carbs_per_unit": 22, "fats_per_unit": 0, "price_per_unit": 0.5,
    })
    assert resp.status_code == 400


@patch('app.vendor_meals.get_db_connection')
def test_create_ingredient_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=INGREDIENT_CATALOG_ROW)
    mock_get_conn.return_value = connection

    resp = client.post('/vendor/ingredients', headers=auth_header(vendor_token()), json={
        "name": "Extra Chicken Breast", "unit": "50g", "calories_per_unit": 82,
        "protein_per_unit": 15, "carbs_per_unit": 0, "fats_per_unit": 1, "price_per_unit": 2.5,
    })

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["ingredient_id"] == 1
    connection.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Meal ingredients (default recipe) on create/get/update
# ---------------------------------------------------------------------------

@patch('app.vendor_meals.get_db_connection')
def test_create_meal_with_ingredients_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_return=MEAL_ROW,
        fetchall_side_effect=[[(1,)], [MEAL_INGREDIENT_ROW]],
    )
    mock_get_conn.return_value = connection

    resp = client.post('/vendor/meals', headers=auth_header(vendor_token(vendor_id=1)), json={
        "name": "Chicken Bowl", "description": "desc", "price": 12.5,
        "calories": 500, "protein": 40, "carbs": 50, "fats": 10,
        "ingredients": {"1": 2},
    })

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["ingredients"][0]["ingredient_id"] == 1
    connection.commit.assert_called_once()


@patch('app.vendor_meals.get_db_connection')
def test_create_meal_ingredient_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchall_return=[])
    mock_get_conn.return_value = connection

    resp = client.post('/vendor/meals', headers=auth_header(vendor_token(vendor_id=1)), json={
        "name": "Chicken Bowl", "price": 12.5, "calories": 500, "protein": 40, "carbs": 50, "fats": 10,
        "ingredients": {"999": 1},
    })

    assert resp.status_code == 404


def test_create_meal_ingredients_not_object(client):
    resp = client.post('/vendor/meals', headers=auth_header(vendor_token()), json={
        "name": "X", "price": 1, "calories": 1, "protein": 1, "carbs": 1, "fats": 1,
        "ingredients": "not-an-object",
    })
    assert resp.status_code == 400


def test_create_meal_ingredients_bad_quantity(client):
    resp = client.post('/vendor/meals', headers=auth_header(vendor_token()), json={
        "name": "X", "price": 1, "calories": 1, "protein": 1, "carbs": 1, "fats": 1,
        "ingredients": {"1": 0},
    })
    assert resp.status_code == 400


@patch('app.vendor_meals.get_db_connection')
def test_get_meal_includes_ingredients(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=MEAL_ROW, fetchall_return=[MEAL_INGREDIENT_ROW])
    mock_get_conn.return_value = connection

    resp = client.get('/vendor/meals/10', headers=auth_header(vendor_token(vendor_id=1)))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ingredients"][0]["ingredient_id"] == 1


@patch('app.vendor_meals.get_db_connection')
def test_update_meal_replaces_ingredients(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[MEAL_ROW, MEAL_ROW],
        fetchall_side_effect=[[(1,)], [MEAL_INGREDIENT_ROW]],
    )
    mock_get_conn.return_value = connection

    resp = client.put('/vendor/meals/10', headers=auth_header(vendor_token(vendor_id=1)), json={
        "name": "Chicken Bowl", "price": 13.0, "calories": 500, "protein": 40, "carbs": 50, "fats": 10,
        "ingredients": {"1": 3},
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ingredients"][0]["ingredient_id"] == 1
    connection.commit.assert_called_once()


@patch('app.vendor_meals.get_db_connection')
def test_update_meal_ingredient_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=MEAL_ROW, fetchall_return=[])
    mock_get_conn.return_value = connection

    resp = client.put('/vendor/meals/10', headers=auth_header(vendor_token(vendor_id=1)), json={
        "name": "Chicken Bowl", "price": 13.0, "calories": 500, "protein": 40, "carbs": 50, "fats": 10,
        "ingredients": {"999": 1},
    })

    assert resp.status_code == 404


@patch('app.vendor_meals.replace_meal_ingredients')
@patch('app.vendor_meals.get_db_connection')
def test_update_meal_without_ingredients_key_leaves_recipe_untouched(mock_get_conn, mock_replace, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[MEAL_ROW, MEAL_ROW])
    mock_get_conn.return_value = connection

    resp = client.put('/vendor/meals/10', headers=auth_header(vendor_token(vendor_id=1)), json={
        "name": "Chicken Bowl", "price": 13.0, "calories": 500, "protein": 40, "carbs": 50, "fats": 10,
    })

    assert resp.status_code == 200
    mock_replace.assert_not_called()
