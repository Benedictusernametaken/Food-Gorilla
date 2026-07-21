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

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_db_connection():
    # No hardcoded fallback — DATABASE_URL is always set by docker-compose.
    return psycopg2.connect(os.environ["DATABASE_URL"])


def make_vendor_token(vendor_id, restaurant_name):
    payload = {
        "vendor_id": vendor_id,
        "restaurant_name": restaurant_name,
        "role": "vendor",
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=TOKEN_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@app.route('/vendor/auth/register', methods=['POST'])
def vendor_register():
    data = request.get_json(silent=True) or {}
    restaurant_name = (data.get('restaurant_name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    cuisine_type = (data.get('cuisine_type') or '').strip() or None

    if not restaurant_name or not email or not password:
        return jsonify({"error": "restaurant_name, email, and password are required"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "invalid email format"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT vendor_id FROM vendors WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"error": "email already in use"}), 409

        cursor.execute(
            "INSERT INTO vendors (restaurant_name, cuisine_type, email, password_hash) "
            "VALUES (%s, %s, %s, %s) RETURNING vendor_id",
            (restaurant_name, cuisine_type, email, password_hash),
        )
        vendor_id = cursor.fetchone()[0]
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"registration failed: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    token = make_vendor_token(vendor_id, restaurant_name)
    return jsonify({"vendor_id": vendor_id, "restaurant_name": restaurant_name, "token": token}), 201


@app.route('/vendor/auth/login', methods=['POST'])
def vendor_login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT vendor_id, restaurant_name, password_hash FROM vendors WHERE email = %s",
            (email,),
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

    vendor_id, restaurant_name, _ = row
    token = make_vendor_token(vendor_id, restaurant_name)
    return jsonify({"vendor_id": vendor_id, "restaurant_name": restaurant_name, "token": token}), 200
