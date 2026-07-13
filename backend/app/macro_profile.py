from flask import jsonify, request
import psycopg2
import os
import jwt
# Import the shared master app instance from your package folder
from app import app

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"

VALID_GENDERS = ("male", "female", "other")
VALID_ACTIVITY_LEVELS = ("sedentary", "light", "moderate", "active", "very_active")
VALID_GOALS = ("lose_weight", "maintain", "gain_muscle")

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

# Calorie offset applied to maintenance TDEE per goal, and the macro split
# (protein/carbs/fats as a fraction of total calories) that goes with it —
# e.g. gain_muscle skews toward more carbs to fuel training, lose_weight
# skews toward more protein to preserve muscle in a deficit.
GOAL_ADJUSTMENTS = {
    "lose_weight": {"calorie_offset": -500, "protein_pct": 0.35, "carbs_pct": 0.35, "fats_pct": 0.30},
    "maintain": {"calorie_offset": 0, "protein_pct": 0.30, "carbs_pct": 0.40, "fats_pct": 0.30},
    "gain_muscle": {"calorie_offset": 500, "protein_pct": 0.30, "carbs_pct": 0.45, "fats_pct": 0.25},
}


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


def calculate_targets(age, gender, weight_kg, height_cm, activity_level, goal):
    # Mifflin-St Jeor equation. "other" splits the difference between the
    # male/female offsets rather than picking either one.
    if gender == "male":
        offset = 5
    elif gender == "female":
        offset = -161
    else:
        offset = -78

    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + offset
    tdee = bmr * ACTIVITY_MULTIPLIERS[activity_level]

    adjustment = GOAL_ADJUSTMENTS[goal]
    calories = tdee + adjustment["calorie_offset"]

    protein_g = (calories * adjustment["protein_pct"]) / 4
    carbs_g = (calories * adjustment["carbs_pct"]) / 4
    fats_g = (calories * adjustment["fats_pct"]) / 9

    return {
        "calories": round(calories),
        "protein_g": round(protein_g),
        "carbs_g": round(carbs_g),
        "fats_g": round(fats_g),
    }


def validate_profile_payload(data):
    try:
        age = int(data.get("age"))
        weight_kg = float(data.get("weight_kg"))
        height_cm = float(data.get("height_cm"))
    except (TypeError, ValueError):
        return None, "age, weight_kg, and height_cm must be numeric"

    gender = (data.get("gender") or "").strip().lower()
    activity_level = (data.get("activity_level") or "").strip().lower()
    goal = (data.get("goal") or "").strip().lower()

    if not (13 <= age <= 100):
        return None, "age must be between 13 and 100"
    if not (30 <= weight_kg <= 300):
        return None, "weight_kg must be between 30 and 300"
    if not (100 <= height_cm <= 250):
        return None, "height_cm must be between 100 and 250"
    if gender not in VALID_GENDERS:
        return None, f"gender must be one of: {', '.join(VALID_GENDERS)}"
    if activity_level not in VALID_ACTIVITY_LEVELS:
        return None, f"activity_level must be one of: {', '.join(VALID_ACTIVITY_LEVELS)}"
    if goal not in VALID_GOALS:
        return None, f"goal must be one of: {', '.join(VALID_GOALS)}"

    return {
        "age": age,
        "gender": gender,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "activity_level": activity_level,
        "goal": goal,
    }, None


def profile_row_to_dict(row):
    profile_id, daily_calorie_target, target_protein_g, target_carbs_g, target_fats_g, updated_at = row
    return {
        "profile_id": profile_id,
        "calories": daily_calorie_target,
        "protein_g": target_protein_g,
        "carbs_g": target_carbs_g,
        "fats_g": target_fats_g,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


@app.route('/profile/macros', methods=['POST'])
def create_macro_profile():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    inputs, error = validate_profile_payload(data)
    if error:
        return jsonify({"error": error}), 400

    targets = calculate_targets(**inputs)

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO macro_profiles (user_id, daily_calorie_target, target_protein_g, "
            "target_carbs_g, target_fats_g) VALUES (%s, %s, %s, %s, %s) "
            "RETURNING profile_id, daily_calorie_target, target_protein_g, target_carbs_g, "
            "target_fats_g, updated_at",
            (user_id, targets["calories"], targets["protein_g"], targets["carbs_g"], targets["fats_g"]),
        )
        row = cursor.fetchone()
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to save macro profile: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify(profile_row_to_dict(row)), 201


@app.route('/profile/macros', methods=['GET'])
def list_macro_profiles():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT profile_id, daily_calorie_target, target_protein_g, target_carbs_g, "
            "target_fats_g, updated_at FROM macro_profiles WHERE user_id = %s "
            "ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to list macro profiles: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify({"profiles": [profile_row_to_dict(row) for row in rows]}), 200


@app.route('/profile/macros/<int:profile_id>', methods=['DELETE'])
def delete_macro_profile(profile_id):
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM macro_profiles WHERE profile_id = %s AND user_id = %s RETURNING profile_id",
            (profile_id, user_id),
        )
        deleted = cursor.fetchone()
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to delete macro profile: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    if not deleted:
        return jsonify({"error": "macro profile not found"}), 404

    return jsonify({"message": "macro profile deleted", "profile_id": profile_id}), 200
