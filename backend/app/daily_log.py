from flask import jsonify, request
import psycopg2
import os
import re
import jwt
# Import the shared master app instance from your package folder
from app import app

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The actual writing into daily_logs happens at checkout time (Story 9's
# /checkout adds an order's macros onto today's row) — this file only reads
# it back out, per Story 11's "so I can track my progress over time".


def get_db_connection():
    # No hardcoded fallback — DATABASE_URL is always set by docker-compose.
    return psycopg2.connect(os.environ["DATABASE_URL"])


def get_authenticated_user():
    """Reads the customer's JWT from the Authorization header and returns
    user_id, or None if missing/invalid/not an auth-purpose token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if payload.get("purpose") != "auth":
        return None
    return payload.get("user_id")


def empty_log(log_date):
    return {
        "log_date": log_date,
        "total_calories_consumed": 0,
        "total_protein_consumed": 0,
        "total_carbs_consumed": 0,
        "total_fats_consumed": 0,
    }


@app.route('/daily-log', methods=['GET'])
def get_daily_log():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    date_param = request.args.get('date')
    if date_param is not None and not DATE_RE.match(date_param):
        return jsonify({"error": "date must be in YYYY-MM-DD format"}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        if date_param:
            cursor.execute(
                "SELECT log_date, total_calories_consumed, total_protein_consumed, "
                "total_carbs_consumed, total_fats_consumed FROM daily_logs "
                "WHERE user_id = %s AND log_date = %s",
                (user_id, date_param),
            )
        else:
            cursor.execute(
                "SELECT log_date, total_calories_consumed, total_protein_consumed, "
                "total_carbs_consumed, total_fats_consumed FROM daily_logs "
                "WHERE user_id = %s AND log_date = CURRENT_DATE",
                (user_id,),
            )
        row = cursor.fetchone()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load daily log: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    if not row:
        return jsonify(empty_log(date_param)), 200

    log_date, calories, protein, carbs, fats = row
    return jsonify({
        "log_date": log_date.isoformat(),
        "total_calories_consumed": calories,
        "total_protein_consumed": protein,
        "total_carbs_consumed": carbs,
        "total_fats_consumed": fats,
    }), 200


@app.route('/daily-log/history', methods=['GET'])
def get_daily_log_history():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT log_date, total_calories_consumed, total_protein_consumed, "
            "total_carbs_consumed, total_fats_consumed FROM daily_logs "
            "WHERE user_id = %s ORDER BY log_date DESC",
            (user_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load daily log history: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    logs = [
        {
            "log_date": row[0].isoformat(),
            "total_calories_consumed": row[1],
            "total_protein_consumed": row[2],
            "total_carbs_consumed": row[3],
            "total_fats_consumed": row[4],
        }
        for row in rows
    ]
    return jsonify({"logs": logs}), 200
