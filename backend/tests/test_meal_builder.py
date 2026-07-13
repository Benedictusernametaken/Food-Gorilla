from unittest.mock import patch, MagicMock


def make_mock_connection(fetchone_side_effect=None, fetchall_return=None):
    cursor = MagicMock()
    if fetchone_side_effect is not None:
        cursor.fetchone.side_effect = fetchone_side_effect
    cursor.fetchall.return_value = fetchall_return or []
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection, cursor


MEAL_ROW = (1, "Chicken Bowl", "desc", 12.5, 520, 45, 50, 10)

INGREDIENT_ROWS = [
    (10, "Extra Chicken Breast", "50g", 82, 15, 0, 1, 2.50, 1),
    (11, "Avocado Scoop", "30g", 48, 1, 3, 4, 1.80, 1),
]


@patch('app.meal_builder.get_db_connection')
def test_get_customize_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[MEAL_ROW], fetchall_return=INGREDIENT_ROWS,
    )
    mock_get_conn.return_value = connection

    resp = client.get('/meals/1/customize')

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["meal_id"] == 1
    assert len(body["ingredients"]) == 2


@patch('app.meal_builder.get_db_connection')
def test_get_customize_meal_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.get('/meals/999/customize')

    assert resp.status_code == 404


@patch('app.meal_builder.get_db_connection')
def test_post_customize_defaults_match_base(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[MEAL_ROW], fetchall_return=INGREDIENT_ROWS,
    )
    mock_get_conn.return_value = connection

    resp = client.post('/meals/1/customize', json={})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total_price"] == 12.5
    assert body["total_calories"] == 520
    assert body["total_protein"] == 45


@patch('app.meal_builder.get_db_connection')
def test_post_customize_increase_ingredient(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[MEAL_ROW], fetchall_return=INGREDIENT_ROWS,
    )
    mock_get_conn.return_value = connection

    # +1 extra unit of chicken breast (id 10) over its default of 1
    resp = client.post('/meals/1/customize', json={"ingredients": {"10": 2}})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total_price"] == 15.0
    assert body["total_calories"] == 602
    assert body["total_protein"] == 60


@patch('app.meal_builder.get_db_connection')
def test_post_customize_remove_ingredient(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[MEAL_ROW], fetchall_return=INGREDIENT_ROWS,
    )
    mock_get_conn.return_value = connection

    resp = client.post('/meals/1/customize', json={"ingredients": {"11": 0}})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total_price"] == 10.7
    assert body["total_calories"] == 472


@patch('app.meal_builder.get_db_connection')
def test_post_customize_unknown_ingredient(mock_get_conn, client):
    connection, cursor = make_mock_connection(
        fetchone_side_effect=[MEAL_ROW], fetchall_return=INGREDIENT_ROWS,
    )
    mock_get_conn.return_value = connection

    resp = client.post('/meals/1/customize', json={"ingredients": {"999": 1}})

    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_post_customize_negative_quantity(client):
    resp = client.post('/meals/1/customize', json={"ingredients": {"10": -1}})
    assert resp.status_code == 400


def test_post_customize_non_integer_quantity(client):
    resp = client.post('/meals/1/customize', json={"ingredients": {"10": "lots"}})
    assert resp.status_code == 400


def test_post_customize_ingredients_not_object(client):
    resp = client.post('/meals/1/customize', json={"ingredients": [1, 2, 3]})
    assert resp.status_code == 400


@patch('app.meal_builder.get_db_connection')
def test_post_customize_meal_not_found(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_side_effect=[None])
    mock_get_conn.return_value = connection

    resp = client.post('/meals/999/customize', json={})

    assert resp.status_code == 404
