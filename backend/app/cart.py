from flask import jsonify, request
import psycopg2
import os
import jwt
# Import the shared master app instance from your package folder
from app import app

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"

# The cart IS the customer's pending order — orders/order_items/
# order_item_ingredients already model "a set of customized meals with a
# price/macro total", so a cart is just an order that hasn't been checked
# out yet. Story 9 (checkout) flips order_status away from 'pending', which
# is what "cart is cleared after checkout" means in practice: the next
# add-to-cart call finds no pending order and starts a fresh one.


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


def parse_ingredient_overrides(data):
    """Validates the {ingredient_id: quantity} override map — same rule
    Story 3's /meals/<id>/customize uses. Returns (overrides, error)."""
    overrides = data.get("ingredients")
    if overrides is None:
        return {}, None
    if not isinstance(overrides, dict):
        return None, "ingredients must be an object of {ingredient_id: quantity}"
    try:
        overrides = {int(k): v for k, v in overrides.items()}
    except (TypeError, ValueError):
        return None, "ingredient_id keys must be numeric"
    for ingredient_id, quantity in overrides.items():
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 0:
            return None, f"quantity for ingredient {ingredient_id} must be a non-negative integer"
    return overrides, None


def fetch_meal_with_ingredients(cursor, meal_id):
    cursor.execute(
        "SELECT meal_id, vendor_id, name, base_price, base_calories, "
        "base_protein, base_carbs, base_fats "
        "FROM meals WHERE meal_id = %s AND is_available = TRUE",
        (meal_id,),
    )
    meal_row = cursor.fetchone()
    if not meal_row:
        return None, None

    cursor.execute(
        "SELECT ingredients.ingredient_id, ingredients.calories_per_unit, "
        "ingredients.protein_per_unit, ingredients.carbs_per_unit, "
        "ingredients.fats_per_unit, ingredients.price_per_unit, "
        "meal_ingredients.default_quantity "
        "FROM meal_ingredients "
        "JOIN ingredients ON meal_ingredients.ingredient_id = ingredients.ingredient_id "
        "WHERE meal_ingredients.meal_id = %s",
        (meal_id,),
    )
    return meal_row, cursor.fetchall()


def compute_serving(meal_row, ingredient_rows, overrides):
    """Computes what one serving of this customized meal costs — price and
    macros — plus the actual per-ingredient quantities used. Mirrors Story
    3's customize_meal math so a cart item's totals match what the
    customization screen already showed the user."""
    (meal_id, vendor_id, name, base_price, base_calories,
     base_protein, base_carbs, base_fats) = meal_row

    known_ids = {row[0] for row in ingredient_rows}
    unknown = set(overrides.keys()) - known_ids
    if unknown:
        return None, f"meal has no such ingredient(s): {sorted(unknown)}"

    price = float(base_price)
    calories, protein, carbs, fats = base_calories, base_protein, base_carbs, base_fats
    ingredient_quantities = []

    for row in ingredient_rows:
        (ingredient_id, calories_per_unit, protein_per_unit, carbs_per_unit,
         fats_per_unit, price_per_unit, default_quantity) = row
        chosen_quantity = overrides.get(ingredient_id, default_quantity)
        delta = chosen_quantity - default_quantity

        price += delta * float(price_per_unit)
        calories += delta * calories_per_unit
        protein += delta * protein_per_unit
        carbs += delta * carbs_per_unit
        fats += delta * fats_per_unit

        ingredient_quantities.append((ingredient_id, chosen_quantity))

    serving = {
        "vendor_id": vendor_id,
        "name": name,
        "price": max(price, 0),
        "calories": max(calories, 0),
        "protein": max(protein, 0),
        "carbs": max(carbs, 0),
        "fats": max(fats, 0),
        "ingredient_quantities": ingredient_quantities,
    }
    return serving, None


def recompute_order_totals(cursor, order_id):
    cursor.execute(
        "SELECT COALESCE(SUM(item_price), 0), COALESCE(SUM(item_calories), 0), "
        "COALESCE(SUM(item_protein), 0), COALESCE(SUM(item_carbs), 0), "
        "COALESCE(SUM(item_fats), 0) FROM order_items WHERE order_id = %s",
        (order_id,),
    )
    totals = cursor.fetchone()
    cursor.execute(
        "UPDATE orders SET total_price = %s, total_calories = %s, total_protein = %s, "
        "total_carbs = %s, total_fats = %s WHERE order_id = %s",
        (*totals, order_id),
    )


def fetch_cart(cursor, user_id):
    cursor.execute(
        "SELECT order_id, vendor_id, total_price, total_calories, "
        "total_protein, total_carbs, total_fats "
        "FROM orders WHERE user_id = %s AND order_status = 'pending'",
        (user_id,),
    )
    order_row = cursor.fetchone()
    if not order_row:
        return {
            "order_id": None, "vendor_id": None, "items": [],
            "total_price": 0, "total_calories": 0, "total_protein": 0,
            "total_carbs": 0, "total_fats": 0,
        }

    (order_id, vendor_id, total_price, total_calories,
     total_protein, total_carbs, total_fats) = order_row

    cursor.execute(
        "SELECT order_items.order_item_id, order_items.meal_id, meals.name, "
        "order_items.quantity, order_items.item_price, order_items.item_calories, "
        "order_items.item_protein, order_items.item_carbs, order_items.item_fats "
        "FROM order_items JOIN meals ON order_items.meal_id = meals.meal_id "
        "WHERE order_items.order_id = %s ORDER BY order_items.order_item_id",
        (order_id,),
    )
    item_rows = cursor.fetchall()

    items = []
    for row in item_rows:
        (order_item_id, meal_id, name, quantity, item_price, item_calories,
         item_protein, item_carbs, item_fats) = row

        cursor.execute(
            "SELECT ingredients.ingredient_id, ingredients.name, "
            "order_item_ingredients.quantity "
            "FROM order_item_ingredients "
            "JOIN ingredients ON order_item_ingredients.ingredient_id = ingredients.ingredient_id "
            "WHERE order_item_ingredients.order_item_id = %s "
            "ORDER BY ingredients.name",
            (order_item_id,),
        )
        items.append({
            "order_item_id": order_item_id,
            "meal_id": meal_id,
            "name": name,
            "quantity": quantity,
            "item_price": float(item_price),
            "item_calories": item_calories,
            "item_protein": item_protein,
            "item_carbs": item_carbs,
            "item_fats": item_fats,
            "ingredients": [
                {"ingredient_id": r[0], "name": r[1], "quantity": r[2]}
                for r in cursor.fetchall()
            ],
        })

    return {
        "order_id": order_id,
        "vendor_id": vendor_id,
        "items": items,
        "total_price": float(total_price),
        "total_calories": total_calories,
        "total_protein": total_protein,
        "total_carbs": total_carbs,
        "total_fats": total_fats,
    }


@app.route('/cart', methods=['GET'])
def get_cart():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cart = fetch_cart(cursor, user_id)
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load cart: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify(cart), 200


@app.route('/cart', methods=['DELETE'])
def clear_cart():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        # Cascades to order_items -> order_item_ingredients.
        cursor.execute(
            "DELETE FROM orders WHERE user_id = %s AND order_status = 'pending'",
            (user_id,),
        )
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to clear cart: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify({
        "order_id": None, "vendor_id": None, "items": [],
        "total_price": 0, "total_calories": 0, "total_protein": 0,
        "total_carbs": 0, "total_fats": 0,
    }), 200


@app.route('/cart/items', methods=['POST'])
def add_to_cart():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}

    try:
        meal_id = int(data.get("meal_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "meal_id (integer) is required"}), 400

    quantity = data.get("quantity", 1)
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
        return jsonify({"error": "quantity must be a positive integer"}), 400

    overrides, error = parse_ingredient_overrides(data)
    if error:
        return jsonify({"error": error}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        meal_row, ingredient_rows = fetch_meal_with_ingredients(cursor, meal_id)
        if not meal_row:
            return jsonify({"error": "meal not found"}), 404

        serving, error = compute_serving(meal_row, ingredient_rows, overrides)
        if error:
            return jsonify({"error": error}), 400

        cursor.execute(
            "SELECT order_id, vendor_id FROM orders WHERE user_id = %s AND order_status = 'pending'",
            (user_id,),
        )
        existing_order = cursor.fetchone()

        if existing_order:
            order_id, cart_vendor_id = existing_order
            if cart_vendor_id != serving["vendor_id"]:
                return jsonify({
                    "error": "cart already contains items from a different vendor; "
                             "clear your cart before ordering from another vendor",
                }), 400
        else:
            cursor.execute(
                "INSERT INTO orders (user_id, vendor_id, total_price, total_calories, "
                "total_protein, total_carbs, total_fats) "
                "VALUES (%s, %s, 0, 0, 0, 0, 0) RETURNING order_id",
                (user_id, serving["vendor_id"]),
            )
            order_id = cursor.fetchone()[0]

        item_price = round(serving["price"] * quantity, 2)
        item_calories = round(serving["calories"] * quantity)
        item_protein = round(serving["protein"] * quantity)
        item_carbs = round(serving["carbs"] * quantity)
        item_fats = round(serving["fats"] * quantity)

        cursor.execute(
            "INSERT INTO order_items (order_id, meal_id, quantity, item_price, "
            "item_calories, item_protein, item_carbs, item_fats) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING order_item_id",
            (order_id, meal_id, quantity, item_price, item_calories,
             item_protein, item_carbs, item_fats),
        )
        order_item_id = cursor.fetchone()[0]

        for ingredient_id, chosen_quantity in serving["ingredient_quantities"]:
            cursor.execute(
                "INSERT INTO order_item_ingredients (order_item_id, ingredient_id, quantity) "
                "VALUES (%s, %s, %s)",
                (order_item_id, ingredient_id, chosen_quantity),
            )

        recompute_order_totals(cursor, order_id)
        cart = fetch_cart(cursor, user_id)
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to add to cart: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify(cart), 201


@app.route('/cart/items/<int:order_item_id>', methods=['PUT'])
def update_cart_item(order_item_id):
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    if "quantity" not in data and "ingredients" not in data:
        return jsonify({"error": "quantity and/or ingredients must be provided"}), 400

    quantity = data.get("quantity")
    if quantity is not None and (not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1):
        return jsonify({"error": "quantity must be a positive integer"}), 400

    explicit_overrides = "ingredients" in data
    overrides, error = parse_ingredient_overrides(data)
    if error:
        return jsonify({"error": error}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT order_items.order_id, order_items.meal_id, order_items.quantity "
            "FROM order_items "
            "JOIN orders ON order_items.order_id = orders.order_id "
            "WHERE order_items.order_item_id = %s AND orders.user_id = %s "
            "AND orders.order_status = 'pending'",
            (order_item_id, user_id),
        )
        item_row = cursor.fetchone()
        if not item_row:
            return jsonify({"error": "cart item not found"}), 404

        order_id, meal_id, current_quantity = item_row

        if not explicit_overrides:
            # Quantity-only update — keep the existing customization by
            # replaying it as the override map instead of falling back to
            # the meal's plain defaults.
            cursor.execute(
                "SELECT ingredient_id, quantity FROM order_item_ingredients "
                "WHERE order_item_id = %s",
                (order_item_id,),
            )
            overrides = dict(cursor.fetchall())

        meal_row, ingredient_rows = fetch_meal_with_ingredients(cursor, meal_id)
        if not meal_row:
            return jsonify({"error": "meal is no longer available"}), 404

        serving, error = compute_serving(meal_row, ingredient_rows, overrides)
        if error:
            return jsonify({"error": error}), 400

        final_quantity = quantity if quantity is not None else current_quantity

        item_price = round(serving["price"] * final_quantity, 2)
        item_calories = round(serving["calories"] * final_quantity)
        item_protein = round(serving["protein"] * final_quantity)
        item_carbs = round(serving["carbs"] * final_quantity)
        item_fats = round(serving["fats"] * final_quantity)

        cursor.execute(
            "UPDATE order_items SET quantity = %s, item_price = %s, item_calories = %s, "
            "item_protein = %s, item_carbs = %s, item_fats = %s WHERE order_item_id = %s",
            (final_quantity, item_price, item_calories, item_protein,
             item_carbs, item_fats, order_item_id),
        )

        cursor.execute(
            "DELETE FROM order_item_ingredients WHERE order_item_id = %s",
            (order_item_id,),
        )
        for ingredient_id, chosen_quantity in serving["ingredient_quantities"]:
            cursor.execute(
                "INSERT INTO order_item_ingredients (order_item_id, ingredient_id, quantity) "
                "VALUES (%s, %s, %s)",
                (order_item_id, ingredient_id, chosen_quantity),
            )

        recompute_order_totals(cursor, order_id)
        cart = fetch_cart(cursor, user_id)
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to update cart item: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify(cart), 200


@app.route('/cart/items/<int:order_item_id>', methods=['DELETE'])
def remove_cart_item(order_item_id):
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT order_items.order_id FROM order_items "
            "JOIN orders ON order_items.order_id = orders.order_id "
            "WHERE order_items.order_item_id = %s AND orders.user_id = %s "
            "AND orders.order_status = 'pending'",
            (order_item_id, user_id),
        )
        item_row = cursor.fetchone()
        if not item_row:
            return jsonify({"error": "cart item not found"}), 404

        order_id = item_row[0]

        cursor.execute("DELETE FROM order_items WHERE order_item_id = %s", (order_item_id,))

        cursor.execute("SELECT COUNT(*) FROM order_items WHERE order_id = %s", (order_id,))
        remaining = cursor.fetchone()[0]

        if remaining == 0:
            # Empty cart — drop the pending order itself rather than leaving
            # a zeroed-out husk behind; the next add-to-cart starts fresh.
            cursor.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))
        else:
            recompute_order_totals(cursor, order_id)

        cart = fetch_cart(cursor, user_id)
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to remove cart item: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify(cart), 200
