import bcrypt
import jwt
from unittest.mock import patch, MagicMock

from app.vendor_auth import JWT_SECRET, JWT_ALGORITHM


def make_mock_connection(fetchone_return=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_return
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection, cursor


@patch('app.vendor_auth.get_db_connection')
def test_vendor_register_success(mock_get_conn, client):
    connection, cursor = make_mock_connection()
    cursor.fetchone.side_effect = [None, (5,)]
    mock_get_conn.return_value = connection

    resp = client.post('/vendor/auth/register', json={
        "restaurant_name": "Lean & Mean Kitchen",
        "email": "vendor@example.com",
        "password": "supersecret1",
    })

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["vendor_id"] == 5
    assert body["restaurant_name"] == "Lean & Mean Kitchen"
    assert "token" in body
    connection.commit.assert_called_once()


def test_vendor_register_missing_fields(client):
    resp = client.post('/vendor/auth/register', json={"restaurant_name": "Only Name"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_vendor_register_invalid_email(client):
    resp = client.post('/vendor/auth/register', json={
        "restaurant_name": "Test Vendor",
        "email": "not-an-email",
        "password": "supersecret1",
    })
    assert resp.status_code == 400


def test_vendor_register_short_password(client):
    resp = client.post('/vendor/auth/register', json={
        "restaurant_name": "Test Vendor",
        "email": "vendor@example.com",
        "password": "short",
    })
    assert resp.status_code == 400


@patch('app.vendor_auth.get_db_connection')
def test_vendor_register_duplicate_email(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=(1,))
    mock_get_conn.return_value = connection

    resp = client.post('/vendor/auth/register', json={
        "restaurant_name": "Dupe Vendor",
        "email": "dupe@example.com",
        "password": "supersecret1",
    })

    assert resp.status_code == 409
    assert "error" in resp.get_json()


@patch('app.vendor_auth.get_db_connection')
def test_vendor_login_success(mock_get_conn, client):
    password_hash = bcrypt.hashpw(b"supersecret1", bcrypt.gensalt()).decode('utf-8')
    connection, cursor = make_mock_connection(fetchone_return=(9, "Some Restaurant", password_hash))
    mock_get_conn.return_value = connection

    resp = client.post('/vendor/auth/login', json={
        "email": "vendor@example.com",
        "password": "supersecret1",
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["vendor_id"] == 9
    assert body["restaurant_name"] == "Some Restaurant"
    decoded = jwt.decode(body["token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert decoded["vendor_id"] == 9
    assert decoded["role"] == "vendor"


@patch('app.vendor_auth.get_db_connection')
def test_vendor_login_wrong_password(mock_get_conn, client):
    password_hash = bcrypt.hashpw(b"correctpassword", bcrypt.gensalt()).decode('utf-8')
    connection, cursor = make_mock_connection(fetchone_return=(9, "Some Restaurant", password_hash))
    mock_get_conn.return_value = connection

    resp = client.post('/vendor/auth/login', json={
        "email": "vendor@example.com",
        "password": "wrongpassword",
    })

    assert resp.status_code == 401


@patch('app.vendor_auth.get_db_connection')
def test_vendor_login_unknown_vendor(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=None)
    mock_get_conn.return_value = connection

    resp = client.post('/vendor/auth/login', json={
        "email": "ghost@example.com",
        "password": "whatever1",
    })

    assert resp.status_code == 401


def test_vendor_login_missing_fields(client):
    resp = client.post('/vendor/auth/login', json={"email": "vendor@example.com"})
    assert resp.status_code == 400
