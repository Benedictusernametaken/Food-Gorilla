from unittest.mock import patch, MagicMock


def make_mock_connection(fetchall_return=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = fetchall_return or []
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection, cursor


MEAL_ROW = (1, 1, "Lean & Mean Kitchen", "Chicken Bowl", "desc", 12.5, 500, 40, 50, 10)


@patch('app.menu.get_db_connection')
def test_browse_menu_success(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchall_return=[MEAL_ROW])
    mock_get_conn.return_value = connection

    resp = client.get('/menu')

    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["meals"]) == 1
    assert body["meals"][0]["name"] == "Chicken Bowl"
    assert body["meals"][0]["restaurant_name"] == "Lean & Mean Kitchen"


@patch('app.menu.get_db_connection')
def test_browse_menu_empty(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchall_return=[])
    mock_get_conn.return_value = connection

    resp = client.get('/menu')

    assert resp.status_code == 200
    assert resp.get_json()["meals"] == []


@patch('app.menu.get_db_connection')
def test_browse_menu_no_auth_required(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchall_return=[MEAL_ROW])
    mock_get_conn.return_value = connection

    resp = client.get('/menu')

    assert resp.status_code != 401


@patch('app.menu.get_db_connection')
def test_browse_menu_db_error(mock_get_conn, client):
    mock_get_conn.side_effect = Exception("connection refused")

    resp = client.get('/menu')

    assert resp.status_code == 500
    assert "error" in resp.get_json()
