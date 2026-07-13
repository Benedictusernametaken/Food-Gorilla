from flask import jsonify, request
import psycopg2
import os
import jwt
# Import the shared master app instance from your package folder
from app import app

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"

# Story 4 doesn't own any writes — Story 1's macro_profiles (targets) and
# Story 9/11's daily_logs (consumed, updated at checkout) already hold
# everything the dashboard needs. This route just joins the most recent
# profile with today's log and does the target-vs-consumed comparison so
# the frontend can render progress bars without two separate calls.


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


@app.route('/dashboard', methods=['GET'])
def get_dashboard():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT daily_calorie_target, target_protein_g, target_carbs_g, "
            "target_fats_g FROM macro_profiles WHERE user_id = %s "
            "ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        )
        profile_row = cursor.fetchone()

        cursor.execute(
            "SELECT log_date, total_calories_consumed, total_protein_consumed, "
            "total_carbs_consumed, total_fats_consumed FROM daily_logs "
            "WHERE user_id = %s AND log_date = CURRENT_DATE",
            (user_id,),
        )
        log_row = cursor.fetchone()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load dashboard: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    targets = None
    if profile_row:
        targets = {
            "calories": profile_row[0],
            "protein_g": profile_row[1],
            "carbs_g": profile_row[2],
            "fats_g": profile_row[3],
        }

    if log_row:
        log_date = log_row[0].isoformat()
        consumed = {
            "calories": log_row[1],
            "protein": log_row[2],
            "carbs": log_row[3],
            "fats": log_row[4],
        }
    else:
        log_date = None
        consumed = {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}

    remaining = None
    exceeded = {"calories": False, "protein": False, "carbs": False, "fats": False}
    if targets:
        remaining = {
            "calories": targets["calories"] - consumed["calories"],
            "protein_g": targets["protein_g"] - consumed["protein"],
            "carbs_g": targets["carbs_g"] - consumed["carbs"],
            "fats_g": targets["fats_g"] - consumed["fats"],
        }
        exceeded = {
            "calories": consumed["calories"] > targets["calories"],
            "protein": consumed["protein"] > targets["protein_g"],
            "carbs": consumed["carbs"] > targets["carbs_g"],
            "fats": consumed["fats"] > targets["fats_g"],
        }

    return jsonify({
        "log_date": log_date,
        "targets": targets,
        "consumed": consumed,
        "remaining": remaining,
        "exceeded": exceeded,
    }), 200
