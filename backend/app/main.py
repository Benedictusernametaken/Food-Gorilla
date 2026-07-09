import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import jsonify, request, g
import psycopg2
import psycopg2.extras
from werkzeug.security import check_password_hash
# Import the shared master app instance from your package folder
from app import app

SESSION_TTL = timedelta(hours=24)

REQUIRED_MEAL_FIELDS = [
    "name", "base_price", "base_calories", "base_protein", "base_carbs", "base_fats",
]

MEAL_COLUMNS = (
    "meal_id, name, description, base_price, base_calories, "
    "base_protein, base_carbs, base_fats, is_available"
)

# Marketplace search range filters: query-param prefix -> underlying column.
# Keys are hardcoded here (never taken from user input) before being
# interpolated into SQL, so this stays injection-safe.
SEARCH_RANGE_FIELDS = {
    "price": "base_price",
    "calories": "base_calories",
    "protein": "base_protein",
    "carbs": "base_carbs",
    "fats": "base_fats",
}


def get_db():
    # No hardcoded fallback — DATABASE_URL is always set by docker-compose.
    # Fail loudly if it's missing rather than silently connecting elsewhere.
    db_url = os.environ["DATABASE_URL"]
    return psycopg2.connect(db_url)


def require_vendor_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header[len("Bearer "):].strip()

        conn = get_db()
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(
                "SELECT vendor_id, expires_at FROM vendor_sessions WHERE token = %s",
                (token,),
            )
            session = cursor.fetchone()
            cursor.close()
        finally:
            conn.close()

        if not session or session["expires_at"] < datetime.utcnow():
            return jsonify({"error": "Session expired or invalid, please log in again"}), 401

        g.vendor_id = session["vendor_id"]
        return f(*args, **kwargs)

    return wrapper


def serialize_meal(row):
    meal = dict(row)
    if meal.get("base_price") is not None:
        meal["base_price"] = float(meal["base_price"])
    return meal


def serialize_meals(rows):
    return [serialize_meal(row) for row in rows]


def validate_meal_payload(data):
    errors = []
    for field in REQUIRED_MEAL_FIELDS:
        if data.get(field) in (None, ""):
            errors.append(f"{field} is required")
    if errors:
        return errors

    if not str(data["name"]).strip():
        errors.append("name cannot be blank")

    try:
        if float(data["base_price"]) < 0:
            errors.append("base_price cannot be negative")
    except (TypeError, ValueError):
        errors.append("base_price must be a number")

    for field in ("base_calories", "base_protein", "base_carbs", "base_fats"):
        try:
            if int(data[field]) < 0:
                errors.append(f"{field} cannot be negative")
        except (TypeError, ValueError):
            errors.append(f"{field} must be a whole number")

    return errors


@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "message": "Welcome to the Food Gorilla Backend API!"
    })


@app.route('/health-check')
def health_check():
    connection = None
    try:
        connection = get_db()
        cursor = connection.cursor()
        # Pure connectivity check — no dependency on any specific table,
        # so this keeps working no matter how the schema evolves.
        cursor.execute("SELECT 1;")
        cursor.fetchone()
        cursor.close()

        return jsonify({
            "status": "healthy",
            "database_connectivity": "CONNECTED"
        })

    except Exception as e:
        return jsonify({
            "status": "degraded",
            "database_connectivity": f"FAILED: {str(e)}"
        }), 500

    finally:
        if connection:
            connection.close()


# ====================================================
# VENDOR AUTH
# ====================================================

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT vendor_id, restaurant_name, password_hash FROM vendors WHERE email = %s",
            (email,),
        )
        vendor = cursor.fetchone()
        cursor.close()

        if not vendor or not check_password_hash(vendor["password_hash"], password):
            return jsonify({"error": "Invalid email or password"}), 401

        token = secrets.token_hex(32)
        expires_at = datetime.utcnow() + SESSION_TTL

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO vendor_sessions (token, vendor_id, expires_at) VALUES (%s, %s, %s)",
            (token, vendor["vendor_id"], expires_at),
        )
        conn.commit()
        cursor.close()

        return jsonify({
            "token": token,
            "vendor_id": vendor["vendor_id"],
            "restaurant_name": vendor["restaurant_name"],
            "expires_at": expires_at.isoformat(),
        })
    finally:
        conn.close()


@app.route('/api/auth/logout', methods=['POST'])
@require_vendor_auth
def logout():
    token = request.headers.get("Authorization", "").split(" ", 1)[1].strip()
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vendor_sessions WHERE token = %s", (token,))
        conn.commit()
        cursor.close()
    finally:
        conn.close()
    return jsonify({"status": "logged_out"})


@app.route('/api/vendor/me', methods=['GET'])
@require_vendor_auth
def get_current_vendor():
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT vendor_id, restaurant_name, cuisine_type, email FROM vendors WHERE vendor_id = %s",
            (g.vendor_id,),
        )
        vendor = cursor.fetchone()
        cursor.close()
        return jsonify(vendor)
    finally:
        conn.close()


# ====================================================
# MERCHANT DASHBOARD — MENU ITEM CRUD (auth required, vendor-scoped)
# ====================================================

@app.route('/api/vendor/meals', methods=['GET'])
@require_vendor_auth
def list_vendor_meals():
    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            f"SELECT {MEAL_COLUMNS} FROM meals WHERE vendor_id = %s ORDER BY meal_id DESC",
            (g.vendor_id,),
        )
        meals = cursor.fetchall()
        cursor.close()
        return jsonify(serialize_meals(meals))
    finally:
        conn.close()


@app.route('/api/vendor/meals', methods=['POST'])
@require_vendor_auth
def create_vendor_meal():
    data = request.get_json(silent=True) or {}
    errors = validate_meal_payload(data)
    if errors:
        return jsonify({"errors": errors}), 400

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            f"""
            INSERT INTO meals (vendor_id, name, description, base_price, base_calories,
                                base_protein, base_carbs, base_fats, is_available)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {MEAL_COLUMNS}
            """,
            (
                g.vendor_id,
                str(data["name"]).strip(),
                (data.get("description") or "").strip() or None,
                float(data["base_price"]),
                int(data["base_calories"]),
                int(data["base_protein"]),
                int(data["base_carbs"]),
                int(data["base_fats"]),
                bool(data.get("is_available", True)),
            ),
        )
        meal = cursor.fetchone()
        conn.commit()
        cursor.close()
        return jsonify(serialize_meal(meal)), 201
    finally:
        conn.close()


@app.route('/api/vendor/meals/<int:meal_id>', methods=['PUT'])
@require_vendor_auth
def update_vendor_meal(meal_id):
    data = request.get_json(silent=True) or {}
    errors = validate_meal_payload(data)
    if errors:
        return jsonify({"errors": errors}), 400

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            f"""
            UPDATE meals
            SET name = %s, description = %s, base_price = %s, base_calories = %s,
                base_protein = %s, base_carbs = %s, base_fats = %s, is_available = %s
            WHERE meal_id = %s AND vendor_id = %s
            RETURNING {MEAL_COLUMNS}
            """,
            (
                str(data["name"]).strip(),
                (data.get("description") or "").strip() or None,
                float(data["base_price"]),
                int(data["base_calories"]),
                int(data["base_protein"]),
                int(data["base_carbs"]),
                int(data["base_fats"]),
                bool(data.get("is_available", True)),
                meal_id,
                g.vendor_id,
            ),
        )
        meal = cursor.fetchone()
        conn.commit()
        cursor.close()
        if not meal:
            return jsonify({"error": "Meal not found"}), 404
        return jsonify(serialize_meal(meal))
    finally:
        conn.close()


@app.route('/api/vendor/meals/<int:meal_id>/availability', methods=['PATCH'])
@require_vendor_auth
def set_meal_availability(meal_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("is_available"), bool):
        return jsonify({"error": "is_available (boolean) is required"}), 400

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            f"""
            UPDATE meals SET is_available = %s
            WHERE meal_id = %s AND vendor_id = %s
            RETURNING {MEAL_COLUMNS}
            """,
            (data["is_available"], meal_id, g.vendor_id),
        )
        meal = cursor.fetchone()
        conn.commit()
        cursor.close()
        if not meal:
            return jsonify({"error": "Meal not found"}), 404
        return jsonify(serialize_meal(meal))
    finally:
        conn.close()


@app.route('/api/vendor/meals/<int:meal_id>', methods=['DELETE'])
@require_vendor_auth
def delete_vendor_meal(meal_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM meals WHERE meal_id = %s AND vendor_id = %s",
            (meal_id, g.vendor_id),
        )
        deleted = cursor.rowcount
        conn.commit()
        cursor.close()
        if not deleted:
            return jsonify({"error": "Meal not found"}), 404
        return jsonify({"status": "deleted", "meal_id": meal_id})
    finally:
        conn.close()


# ====================================================
# PUBLIC MARKETPLACE SEARCH (Feature 2) — only available meals
# ====================================================

@app.route('/api/meals/search', methods=['GET'])
def search_meals():
    conditions = ["m.is_available = TRUE"]
    params = []

    q = request.args.get("q", "").strip()
    if q:
        conditions.append("m.name ILIKE %s")
        params.append(f"%{q}%")

    for key, column in SEARCH_RANGE_FIELDS.items():
        min_value = request.args.get(f"min_{key}")
        max_value = request.args.get(f"max_{key}")
        if min_value not in (None, ""):
            try:
                params.append(float(min_value))
            except ValueError:
                return jsonify({"error": f"min_{key} must be a number"}), 400
            conditions.append(f"m.{column} >= %s")
        if max_value not in (None, ""):
            try:
                params.append(float(max_value))
            except ValueError:
                return jsonify({"error": f"max_{key} must be a number"}), 400
            conditions.append(f"m.{column} <= %s")

    where_clause = " AND ".join(conditions)

    conn = get_db()
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            f"""
            SELECT m.meal_id, m.name, m.description, m.base_price, m.base_calories,
                   m.base_protein, m.base_carbs, m.base_fats,
                   v.vendor_id, v.restaurant_name, v.cuisine_type
            FROM meals m
            JOIN vendors v ON v.vendor_id = m.vendor_id
            WHERE {where_clause}
            ORDER BY m.name
            """,
            params,
        )
        meals = cursor.fetchall()
        cursor.close()
        return jsonify(serialize_meals(meals))
    finally:
        conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
