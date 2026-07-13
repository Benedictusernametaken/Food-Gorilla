import bcrypt
import jwt
from unittest.mock import patch, MagicMock

from app.auth import JWT_SECRET, JWT_ALGORITHM


def make_mock_connection(fetchone_return=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_return
    connection = MagicMock()
    connection.cursor.return_value = cursor
    return connection, cursor


@patch('app.auth.get_db_connection')
def test_register_success(mock_get_conn, client):
    connection, cursor = make_mock_connection()
    cursor.fetchone.side_effect = [None, (42,)]
    mock_get_conn.return_value = connection

    resp = client.post('/auth/register', json={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "supersecret1",
    })

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["user_id"] == 42
    assert body["username"] == "newuser"
    assert "token" in body
    connection.commit.assert_called_once()


def test_register_missing_fields(client):
    resp = client.post('/auth/register', json={"username": "onlyname"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_register_invalid_email(client):
    resp = client.post('/auth/register', json={
        "username": "user1",
        "email": "not-an-email",
        "password": "supersecret1",
    })
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post('/auth/register', json={
        "username": "user1",
        "email": "user1@example.com",
        "password": "short",
    })
    assert resp.status_code == 400


@patch('app.auth.get_db_connection')
def test_register_duplicate_email(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=(1,))
    mock_get_conn.return_value = connection

    resp = client.post('/auth/register', json={
        "username": "dupe",
        "email": "dupe@example.com",
        "password": "supersecret1",
    })

    assert resp.status_code == 409
    assert "error" in resp.get_json()


@patch('app.auth.get_db_connection')
def test_login_success(mock_get_conn, client):
    password_hash = bcrypt.hashpw(b"supersecret1", bcrypt.gensalt()).decode('utf-8')
    connection, cursor = make_mock_connection(fetchone_return=(7, "someuser", password_hash))
    mock_get_conn.return_value = connection

    resp = client.post('/auth/login', json={
        "identifier": "someuser",
        "password": "supersecret1",
    })

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["user_id"] == 7
    assert body["username"] == "someuser"
    decoded = jwt.decode(body["token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert decoded["user_id"] == 7


@patch('app.auth.get_db_connection')
def test_login_wrong_password(mock_get_conn, client):
    password_hash = bcrypt.hashpw(b"correctpassword", bcrypt.gensalt()).decode('utf-8')
    connection, cursor = make_mock_connection(fetchone_return=(7, "someuser", password_hash))
    mock_get_conn.return_value = connection

    resp = client.post('/auth/login', json={
        "identifier": "someuser",
        "password": "wrongpassword",
    })

    assert resp.status_code == 401


@patch('app.auth.get_db_connection')
def test_login_unknown_user(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=None)
    mock_get_conn.return_value = connection

    resp = client.post('/auth/login', json={
        "identifier": "ghost",
        "password": "whatever1",
    })

    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post('/auth/login', json={"identifier": "someuser"})
    assert resp.status_code == 400


@patch('app.auth.get_db_connection')
def test_reset_request_known_email(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=(7, "someuser"))
    mock_get_conn.return_value = connection

    resp = client.post('/auth/reset-request', json={"email": "someuser@example.com"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert "reset_token" in body


@patch('app.auth.get_db_connection')
def test_reset_request_unknown_email(mock_get_conn, client):
    connection, cursor = make_mock_connection(fetchone_return=None)
    mock_get_conn.return_value = connection

    resp = client.post('/auth/reset-request', json={"email": "ghost@example.com"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert "reset_token" not in body


def test_reset_request_missing_email(client):
    resp = client.post('/auth/reset-request', json={})
    assert resp.status_code == 400


@patch('app.auth.get_db_connection')
def test_reset_confirm_success(mock_get_conn, client):
    connection, cursor = make_mock_connection()
    mock_get_conn.return_value = connection

    import datetime
    token = jwt.encode(
        {
            "user_id": 7,
            "username": "someuser",
            "purpose": "reset",
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    resp = client.post('/auth/reset-confirm', json={
        "token": token,
        "new_password": "newsupersecret1",
    })

    assert resp.status_code == 200
    connection.commit.assert_called_once()


def test_reset_confirm_invalid_token(client):
    resp = client.post('/auth/reset-confirm', json={
        "token": "not-a-real-token",
        "new_password": "newsupersecret1",
    })
    assert resp.status_code == 400


def test_reset_confirm_wrong_purpose_token(client):
    import datetime
    token = jwt.encode(
        {
            "user_id": 7,
            "username": "someuser",
            "purpose": "auth",
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    resp = client.post('/auth/reset-confirm', json={
        "token": token,
        "new_password": "newsupersecret1",
    })
    assert resp.status_code == 400


def test_reset_confirm_missing_fields(client):
    resp = client.post('/auth/reset-confirm', json={"token": "abc"})
    assert resp.status_code == 400
