from flask import jsonify, request
import psycopg2
import os
# Import the shared master app instance from your package folder
from app import app


def get_db_connection():
    # No hardcoded fallback — DATABASE_URL is always set by docker-compose.
    return psycopg2.connect(os.environ["DATABASE_URL"])


def fetch_customizable_meal(cursor, meal_id):
    cursor.execute(
        "SELECT meal_id, name, description, base_price, base_calories, "
        "base_protein, base_carbs, base_fats "
        "FROM meals WHERE meal_id = %s AND is_available = TRUE",
        (meal_id,),
    )
    meal_row = cursor.fetchone()
    if not meal_row:
        return None, None

    cursor.execute(
        "SELECT ingredients.ingredient_id, ingredients.name, ingredients.unit, "
        "ingredients.calories_per_unit, ingredients.protein_per_unit, "
        "ingredients.carbs_per_unit, ingredients.fats_per_unit, "
        "ingredients.price_per_unit, meal_ingredients.default_quantity "
        "FROM meal_ingredients "
        "JOIN ingredients ON meal_ingredients.ingredient_id = ingredients.ingredient_id "
        "WHERE meal_ingredients.meal_id = %s "
        "ORDER BY ingredients.name",
        (meal_id,),
    )
    ingredient_rows = cursor.fetchall()
    return meal_row, ingredient_rows


def ingredient_row_to_dict(row):
    (ingredient_id, name, unit, calories_per_unit, protein_per_unit,
     carbs_per_unit, fats_per_unit, price_per_unit, default_quantity) = row
    return {
        "ingredient_id": ingredient_id,
        "name": name,
        "unit": unit,
        "calories_per_unit": calories_per_unit,
        "protein_per_unit": protein_per_unit,
        "carbs_per_unit": carbs_per_unit,
        "fats_per_unit": fats_per_unit,
        "price_per_unit": float(price_per_unit),
        "default_quantity": default_quantity,
    }


@app.route('/meals/<int:meal_id>/customize', methods=['GET'])
def get_meal_customization_options(meal_id):
    # Public — same as menu browsing (Story 2), no auth required to look.
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        meal_row, ingredient_rows = fetch_customizable_meal(cursor, meal_id)
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load meal: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    if not meal_row:
        return jsonify({"error": "meal not found"}), 404

    (meal_id, name, description, base_price, base_calories,
     base_protein, base_carbs, base_fats) = meal_row

    return jsonify({
        "meal_id": meal_id,
        "name": name,
        "description": description,
        "base_price": float(base_price),
        "base_calories": base_calories,
        "base_protein": base_protein,
        "base_carbs": base_carbs,
        "base_fats": base_fats,
        "ingredients": [ingredient_row_to_dict(row) for row in ingredient_rows],
    }), 200


@app.route('/meals/<int:meal_id>/customize', methods=['POST'])
def customize_meal(meal_id):
    # Public and stateless — this endpoint only computes and validates a
    # customized meal's totals. Story 10 owns actually persisting it into a
    # cart; this is the "customized meal object" that build order note
    # said Story 10 would consume.
    data = request.get_json(silent=True) or {}
    overrides = data.get("ingredients")
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, dict):
        return jsonify({"error": "ingredients must be an object of {ingredient_id: quantity}"}), 400

    try:
        overrides = {int(k): v for k, v in overrides.items()}
    except (TypeError, ValueError):
        return jsonify({"error": "ingredient_id keys must be numeric"}), 400

    for ingredient_id, quantity in overrides.items():
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 0:
            return jsonify({"error": f"quantity for ingredient {ingredient_id} must be a non-negative integer"}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        meal_row, ingredient_rows = fetch_customizable_meal(cursor, meal_id)
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load meal: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    if not meal_row:
        return jsonify({"error": "meal not found"}), 404

    (meal_id, name, description, base_price, base_calories,
     base_protein, base_carbs, base_fats) = meal_row

    known_ingredient_ids = {row[0] for row in ingredient_rows}
    unknown = set(overrides.keys()) - known_ingredient_ids
    if unknown:
        return jsonify({"error": f"meal has no such ingredient(s): {sorted(unknown)}"}), 400

    total_price = float(base_price)
    total_calories = base_calories
    total_protein = base_protein
    total_carbs = base_carbs
    total_fats = base_fats
    line_items = []

    for row in ingredient_rows:
        ingredient = ingredient_row_to_dict(row)
        chosen_quantity = overrides.get(ingredient["ingredient_id"], ingredient["default_quantity"])
        delta = chosen_quantity - ingredient["default_quantity"]

        total_price += delta * ingredient["price_per_unit"]
        total_calories += delta * ingredient["calories_per_unit"]
        total_protein += delta * ingredient["protein_per_unit"]
        total_carbs += delta * ingredient["carbs_per_unit"]
        total_fats += delta * ingredient["fats_per_unit"]

        line_items.append({
            "ingredient_id": ingredient["ingredient_id"],
            "name": ingredient["name"],
            "unit": ingredient["unit"],
            "quantity": chosen_quantity,
            "default_quantity": ingredient["default_quantity"],
        })

    # Floor at 0 — a well-formed default recipe shouldn't be able to drive
    # totals negative, but this is a cheap guard against bad seed/menu data.
    total_price = max(total_price, 0)
    total_calories = max(total_calories, 0)
    total_protein = max(total_protein, 0)
    total_carbs = max(total_carbs, 0)
    total_fats = max(total_fats, 0)

    return jsonify({
        "meal_id": meal_id,
        "name": name,
        "ingredients": line_items,
        "total_price": round(total_price, 2),
        "total_calories": round(total_calories),
        "total_protein": round(total_protein),
        "total_carbs": round(total_carbs),
        "total_fats": round(total_fats),
    }), 200
