from flask import jsonify, request
import psycopg2
import os
import jwt
# Import the shared master app instance from your package folder
from app import app

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"

REQUIRED_FIELDS = ("name", "price", "calories", "protein", "carbs", "fats")


def get_db_connection():
    # No hardcoded fallback — DATABASE_URL is always set by docker-compose.
    return psycopg2.connect(os.environ["DATABASE_URL"])


def get_authenticated_vendor():
    """Reads the vendor's JWT from the Authorization header and returns
    (vendor_id, restaurant_name), or None if missing/invalid/not a vendor
    token. Signature is fully verified here — this is the trust boundary."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if payload.get("role") != "vendor":
        return None
    return payload.get("vendor_id"), payload.get("restaurant_name")


def meal_row_to_dict(row):
    (meal_id, vendor_id, name, description, price,
     calories, protein, carbs, fats, is_available) = row
    return {
        "meal_id": meal_id,
        "vendor_id": vendor_id,
        "name": name,
        "description": description,
        "price": float(price),
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fats": fats,
        "is_available": is_available,
    }


def validate_meal_payload(data):
    missing = [field for field in REQUIRED_FIELDS if data.get(field) in (None, "")]
    if missing:
        return f"missing required field(s): {', '.join(missing)}"

    try:
        price = float(data["price"])
        calories = int(data["calories"])
        protein = int(data["protein"])
        carbs = int(data["carbs"])
        fats = int(data["fats"])
    except (TypeError, ValueError):
        return "price, calories, protein, carbs, and fats must be numeric"

    if price < 0 or calories < 0 or protein < 0 or carbs < 0 or fats < 0:
        return "price and macro values must not be negative"

    return None


@app.route('/vendor/meals', methods=['GET'])
def list_vendor_meals():
    vendor = get_authenticated_vendor()
    if not vendor:
        return jsonify({"error": "vendor authentication required"}), 401
    vendor_id, _ = vendor

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT meal_id, vendor_id, name, description, base_price, "
            "base_calories, base_protein, base_carbs, base_fats, is_available "
            "FROM meals WHERE vendor_id = %s ORDER BY meal_id",
            (vendor_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to list meals: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify({"meals": [meal_row_to_dict(row) for row in rows]}), 200


@app.route('/vendor/meals', methods=['POST'])
def create_vendor_meal():
    vendor = get_authenticated_vendor()
    if not vendor:
        return jsonify({"error": "vendor authentication required"}), 401
    vendor_id, _ = vendor

    data = request.get_json(silent=True) or {}
    error = validate_meal_payload(data)
    if error:
        return jsonify({"error": error}), 400

    name = str(data["name"]).strip()
    description = (data.get("description") or "").strip() or None

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO meals (vendor_id, name, description, base_price, "
            "base_calories, base_protein, base_carbs, base_fats, is_available) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE) "
            "RETURNING meal_id, vendor_id, name, description, base_price, "
            "base_calories, base_protein, base_carbs, base_fats, is_available",
            (vendor_id, name, description, data["price"],
             data["calories"], data["protein"], data["carbs"], data["fats"]),
        )
        row = cursor.fetchone()
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to create meal: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify(meal_row_to_dict(row)), 201


def fetch_owned_meal(cursor, meal_id, vendor_id):
    cursor.execute(
        "SELECT meal_id, vendor_id, name, description, base_price, "
        "base_calories, base_protein, base_carbs, base_fats, is_available "
        "FROM meals WHERE meal_id = %s AND vendor_id = %s",
        (meal_id, vendor_id),
    )
    return cursor.fetchone()


@app.route('/vendor/meals/<int:meal_id>', methods=['GET'])
def get_vendor_meal(meal_id):
    vendor = get_authenticated_vendor()
    if not vendor:
        return jsonify({"error": "vendor authentication required"}), 401
    vendor_id, _ = vendor

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        row = fetch_owned_meal(cursor, meal_id, vendor_id)
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to fetch meal: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    if not row:
        return jsonify({"error": "meal not found"}), 404

    return jsonify(meal_row_to_dict(row)), 200


@app.route('/vendor/meals/<int:meal_id>', methods=['PUT'])
def update_vendor_meal(meal_id):
    vendor = get_authenticated_vendor()
    if not vendor:
        return jsonify({"error": "vendor authentication required"}), 401
    vendor_id, _ = vendor

    data = request.get_json(silent=True) or {}
    error = validate_meal_payload(data)
    if error:
        return jsonify({"error": error}), 400

    name = str(data["name"]).strip()
    description = (data.get("description") or "").strip() or None

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        existing = fetch_owned_meal(cursor, meal_id, vendor_id)
        if not existing:
            return jsonify({"error": "meal not found"}), 404

        cursor.execute(
            "UPDATE meals SET name = %s, description = %s, base_price = %s, "
            "base_calories = %s, base_protein = %s, base_carbs = %s, base_fats = %s "
            "WHERE meal_id = %s AND vendor_id = %s "
            "RETURNING meal_id, vendor_id, name, description, base_price, "
            "base_calories, base_protein, base_carbs, base_fats, is_available",
            (name, description, data["price"], data["calories"], data["protein"],
             data["carbs"], data["fats"], meal_id, vendor_id),
        )
        row = cursor.fetchone()
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to update meal: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify(meal_row_to_dict(row)), 200


@app.route('/vendor/meals/<int:meal_id>', methods=['DELETE'])
def delete_vendor_meal(meal_id):
    vendor = get_authenticated_vendor()
    if not vendor:
        return jsonify({"error": "vendor authentication required"}), 401
    vendor_id, _ = vendor

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM meals WHERE meal_id = %s AND vendor_id = %s RETURNING meal_id",
            (meal_id, vendor_id),
        )
        deleted = cursor.fetchone()
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to delete meal: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    if not deleted:
        return jsonify({"error": "meal not found"}), 404

    return jsonify({"message": "meal deleted", "meal_id": meal_id}), 200


@app.route('/vendor/meals/<int:meal_id>/availability', methods=['PATCH'])
def toggle_vendor_meal_availability(meal_id):
    vendor = get_authenticated_vendor()
    if not vendor:
        return jsonify({"error": "vendor authentication required"}), 401
    vendor_id, _ = vendor

    data = request.get_json(silent=True) or {}
    if "is_available" not in data or not isinstance(data["is_available"], bool):
        return jsonify({"error": "is_available (boolean) is required"}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE meals SET is_available = %s WHERE meal_id = %s AND vendor_id = %s "
            "RETURNING meal_id, vendor_id, name, description, base_price, "
            "base_calories, base_protein, base_carbs, base_fats, is_available",
            (data["is_available"], meal_id, vendor_id),
        )
        row = cursor.fetchone()
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to update availability: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    if not row:
        return jsonify({"error": "meal not found"}), 404

    return jsonify(meal_row_to_dict(row)), 200
