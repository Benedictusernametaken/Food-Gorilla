from flask import jsonify
import psycopg2
import os
# Import the shared master app instance from your package folder
from app import app


def get_db_connection():
    # No hardcoded fallback — DATABASE_URL is always set by docker-compose.
    return psycopg2.connect(os.environ["DATABASE_URL"])


def meal_row_to_dict(row):
    (meal_id, vendor_id, restaurant_name, name, description,
     price, calories, protein, carbs, fats) = row
    return {
        "meal_id": meal_id,
        "vendor_id": vendor_id,
        "restaurant_name": restaurant_name,
        "name": name,
        "description": description,
        "price": float(price),
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fats": fats,
    }


@app.route('/menu', methods=['GET'])
def browse_menu():
    # Public browsing endpoint — no auth required. Only meals the vendor has
    # marked in-stock (Story 5) are worth surfacing here; out-of-stock items
    # aren't orderable so there's nothing for a customer to do with them.
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT meals.meal_id, meals.vendor_id, vendors.restaurant_name, meals.name, "
            "meals.description, meals.base_price, meals.base_calories, meals.base_protein, "
            "meals.base_carbs, meals.base_fats "
            "FROM meals "
            "JOIN vendors ON meals.vendor_id = vendors.vendor_id "
            "WHERE meals.is_available = TRUE "
            "ORDER BY vendors.restaurant_name, meals.name"
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load menu: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify({"meals": [meal_row_to_dict(row) for row in rows]}), 200
