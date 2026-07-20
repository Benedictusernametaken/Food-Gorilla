import os
from flask import jsonify, request
import psycopg2
import os
import re
import datetime
import bcrypt
import jwt
# Import the shared master app instance from your package folder
from app import app

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24
RESET_TOKEN_EXPIRY_MINUTES = 15

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_db_connection():
    # No hardcoded fallback — DATABASE_URL is always set by docker-compose.
    return psycopg2.connect(os.environ["DATABASE_URL"])


def make_token(user_id, username, purpose="auth", expiry=None):
    payload = {
        "user_id": user_id,
        "username": username,
        "purpose": purpose,
        "exp": datetime.datetime.now(datetime.timezone.utc) + (expiry or datetime.timedelta(hours=TOKEN_EXPIRY_HOURS)),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not username or not email or not password:
        return jsonify({"error": "username, email, and password are required"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "invalid email format"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT user_id FROM users WHERE email = %s OR username = %s",
            (email, username),
        )
        if cursor.fetchone():
            return jsonify({"error": "username or email already in use"}), 409

        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING user_id",
            (username, email, password_hash),
        )
        user_id = cursor.fetchone()[0]
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"registration failed: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    token = make_token(user_id, username)
    return jsonify({"user_id": user_id, "username": username, "token": token}), 201


@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get('identifier') or '').strip()
    password = data.get('password') or ''

    if not identifier or not password:
        return jsonify({"error": "identifier and password are required"}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT user_id, username, password_hash FROM users WHERE email = %s OR username = %s",
            (identifier.lower(), identifier),
        )
        row = cursor.fetchone()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"login failed: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    if not row or not bcrypt.checkpw(password.encode('utf-8'), row[2].encode('utf-8')):
        return jsonify({"error": "invalid credentials"}), 401

    user_id, username, _ = row
    token = make_token(user_id, username)
    return jsonify({"user_id": user_id, "username": username, "token": token}), 200


@app.route('/auth/reset-request', methods=['POST'])
def reset_request():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({"error": "email is required"}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT user_id, username FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"reset request failed: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    generic_response = {"message": "if that email is registered, a reset link has been sent"}

    # Always return the same generic message regardless of whether the
    # email exists, so this endpoint can't be used to enumerate accounts.
    if not row:
        return jsonify(generic_response), 200

    user_id, username = row
    reset_token = make_token(
        user_id, username, purpose="reset",
        expiry=datetime.timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES),
    )

    # No email provider is wired up yet, so the reset token is returned
    # directly in the response instead of being emailed out. Swap this for
    # a real send once an email service is configured.
    generic_response["reset_token"] = reset_token
    return jsonify(generic_response), 200


@app.route('/auth/reset-confirm', methods=['POST'])
def reset_confirm():
    data = request.get_json(silent=True) or {}
    reset_token = data.get('token') or ''
    new_password = data.get('new_password') or ''

    if not reset_token or not new_password:
        return jsonify({"error": "token and new_password are required"}), 400
    if len(new_password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    try:
        payload = jwt.decode(reset_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "reset token has expired"}), 400
    except jwt.InvalidTokenError:
        return jsonify({"error": "invalid reset token"}), 400

    if payload.get('purpose') != 'reset':
        return jsonify({"error": "invalid reset token"}), 400

    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE user_id = %s",
            (password_hash, payload['user_id']),
        )
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"reset confirm failed: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify({"message": "password updated successfully"}), 200
