import os
import uuid

import bcrypt
import psycopg2
from flask import jsonify, request
from psycopg2.extras import RealDictCursor

# Import the shared master app instance from your package folder
from app import app
from app.auth import SESSION_TOKENS, get_authenticated_user_id, get_session_token


def get_db_connection():
    connection = psycopg2.connect(os.environ["DATABASE_URL"])
    connection.autocommit = False
    return connection


def get_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    if request.form:
        return request.form.to_dict()
    return {}


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
        db_url = os.environ["DATABASE_URL"]
        connection = psycopg2.connect(db_url)
        cursor = connection.cursor()
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


@app.route('/meals')
def meals():
    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
                m.meal_id,
                m.name,
                m.description,
                m.base_price,
                m.base_calories,
                m.base_protein,
                m.base_carbs,
                m.base_fats,
                v.restaurant_name AS vendor_name
            FROM meals m
            LEFT JOIN vendors v ON m.vendor_id = v.vendor_id
            ORDER BY m.name
            """
        )
        meals_data = cursor.fetchall()
        cursor.close()
        return jsonify(meals_data)
    finally:
        connection.close()


@app.route('/meals/filter')
def meals_filter():
    filters = []
    values = []

    calories_max = request.args.get("caloriesMax")
    if calories_max:
        filters.append("m.base_calories <= %s")
        values.append(int(calories_max))

    protein_max = request.args.get("proteinMax")
    if protein_max:
        filters.append("m.base_protein <= %s")
        values.append(int(protein_max))

    carbs_max = request.args.get("carbsMax")
    if carbs_max:
        filters.append("m.base_carbs <= %s")
        values.append(int(carbs_max))

    fats_max = request.args.get("fatsMax")
    if fats_max:
        filters.append("m.base_fats <= %s")
        values.append(int(fats_max))

    query = """
        SELECT
            m.meal_id,
            m.name,
            m.description,
            m.base_price,
            m.base_calories,
            m.base_protein,
            m.base_carbs,
            m.base_fats,
            v.restaurant_name AS vendor_name
        FROM meals m
        LEFT JOIN vendors v ON m.vendor_id = v.vendor_id
    """

    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += " ORDER BY m.name"

    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, values)
        meals_data = cursor.fetchall()
        cursor.close()
        return jsonify(meals_data)
    finally:
        connection.close()


@app.route('/register', methods=['POST'])
def register():
    data = get_request_data()
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required."}), 400

    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            return jsonify({"error": "Email already exists."}), 409

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING user_id",
            (username, email, password_hash),
        )
        user_id = cursor.fetchone()["user_id"]
        connection.commit()
        cursor.close()
        return jsonify({"message": "User registered successfully.", "user_id": user_id})
    except Exception as exc:
        connection.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        connection.close()


@app.route('/login', methods=['POST'])
def login():
    data = get_request_data()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT user_id, username, email, password_hash FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()

        if not user:
            return jsonify({"error": "Invalid credentials."}), 401

        if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            return jsonify({"error": "Invalid credentials."}), 401

        token = str(uuid.uuid4())
        SESSION_TOKENS[token] = user["user_id"]
        return jsonify({
            "message": "Login successful.",
            "token": token,
            "user": {
                "user_id": user["user_id"],
                "username": user["username"],
                "email": user["email"]
            }
        })
    finally:
        connection.close()


@app.route('/checkout', methods=['POST'])
def checkout():
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"error": "Authentication required."}), 401

    data = get_request_data()
    meal_id = data.get('meal_id')
    quantity = int(data.get('quantity', 1) or 1)

    if not meal_id:
        return jsonify({"error": "Meal selection is required."}), 400

    connection = get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT meal_id, base_price, base_calories, base_protein, base_carbs, base_fats FROM meals WHERE meal_id = %s",
            (meal_id,),
        )
        meal = cursor.fetchone()
        if not meal:
            cursor.close()
            return jsonify({"error": "Meal not found."}), 404

        total_price = float(meal["base_price"]) * quantity
        total_calories = int(meal["base_calories"]) * quantity
        total_protein = int(meal["base_protein"]) * quantity
        total_carbs = int(meal["base_carbs"]) * quantity
        total_fats = int(meal["base_fats"]) * quantity

        cursor.execute(
            """
            INSERT INTO orders (user_id, vendor_id, total_price, total_calories, total_protein, total_carbs, total_fats)
            VALUES (%s, (SELECT vendor_id FROM meals WHERE meal_id = %s), %s, %s, %s, %s, %s)
            RETURNING order_id
            """,
            (user_id, meal_id, total_price, total_calories, total_protein, total_carbs, total_fats),
        )
        order_id = cursor.fetchone()["order_id"]

        cursor.execute(
            """
            INSERT INTO order_items (order_id, meal_id, quantity, item_price, item_calories, item_protein, item_carbs, item_fats)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (order_id, meal_id, quantity, total_price, total_calories, total_protein, total_carbs, total_fats),
        )

        cursor.execute(
            "SELECT log_id, total_calories_consumed, total_protein_consumed, total_carbs_consumed, total_fats_consumed FROM daily_logs WHERE user_id = %s AND log_date = CURRENT_DATE",
            (user_id,),
        )
        existing_log = cursor.fetchone()

        if existing_log:
            cursor.execute(
                """
                UPDATE daily_logs
                SET total_calories_consumed = total_calories_consumed + %s,
                    total_protein_consumed = total_protein_consumed + %s,
                    total_carbs_consumed = total_carbs_consumed + %s,
                    total_fats_consumed = total_fats_consumed + %s
                WHERE log_id = %s
                """,
                (total_calories, total_protein, total_carbs, total_fats, existing_log["log_id"]),
            )
        else:
            cursor.execute(
                """
                INSERT INTO daily_logs (user_id, log_date, total_calories_consumed, total_protein_consumed, total_carbs_consumed, total_fats_consumed)
                VALUES (%s, CURRENT_DATE, %s, %s, %s, %s)
                """,
                (user_id, total_calories, total_protein, total_carbs, total_fats),
            )

        connection.commit()
        cursor.close()
        return jsonify({"message": "Order placed successfully.", "order_id": order_id})
    except Exception as exc:
        connection.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        connection.close()


@app.route('/logout')
def logout():
    token = get_session_token()
    if token in SESSION_TOKENS:
        del SESSION_TOKENS[token]

    return jsonify({"message": "Logged out successfully."})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)