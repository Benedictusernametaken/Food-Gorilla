from flask import jsonify, request
import psycopg2
import os
import jwt
# Import the shared master app instance from your package folder
from app import app

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"

# The cart (Story 10) is just an order sitting at order_status='pending'.
# Checkout is the transition out of that state: validate there's something
# to place, flip the status to 'confirmed', and the pending order becomes a
# real placed order. Story 10's own logic already treats "no pending order"
# as an empty cart, so the next add-to-cart call after checkout starts a
# fresh pending order automatically — that's what "cart is cleared after
# checkout" means here, no separate clearing step needed.


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


def fetch_order_detail(cursor, order_id):
    cursor.execute(
        "SELECT order_id, vendor_id, order_status, order_date, total_price, "
        "total_calories, total_protein, total_carbs, total_fats "
        "FROM orders WHERE order_id = %s",
        (order_id,),
    )
    order_row = cursor.fetchone()
    if not order_row:
        return None

    (order_id, vendor_id, order_status, order_date, total_price,
     total_calories, total_protein, total_carbs, total_fats) = order_row

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
        "order_status": order_status,
        "order_date": order_date.isoformat() if order_date else None,
        "items": items,
        "total_price": float(total_price),
        "total_calories": total_calories,
        "total_protein": total_protein,
        "total_carbs": total_carbs,
        "total_fats": total_fats,
    }


@app.route('/checkout', methods=['POST'])
def checkout():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT order_id FROM orders WHERE user_id = %s AND order_status = 'pending'",
            (user_id,),
        )
        pending_order = cursor.fetchone()
        if not pending_order:
            return jsonify({"error": "cart is empty"}), 400

        order_id = pending_order[0]

        cursor.execute(
            "UPDATE orders SET order_status = 'confirmed' WHERE order_id = %s",
            (order_id,),
        )
        order = fetch_order_detail(cursor, order_id)
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to check out: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify(order), 200


@app.route('/orders', methods=['GET'])
def list_orders():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT order_id, vendor_id, order_status, order_date, total_price, "
            "total_calories, total_protein, total_carbs, total_fats "
            "FROM orders WHERE user_id = %s AND order_status != 'pending' "
            "ORDER BY order_date DESC",
            (user_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load orders: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    orders = [
        {
            "order_id": row[0],
            "vendor_id": row[1],
            "order_status": row[2],
            "order_date": row[3].isoformat() if row[3] else None,
            "total_price": float(row[4]),
            "total_calories": row[5],
            "total_protein": row[6],
            "total_carbs": row[7],
            "total_fats": row[8],
        }
        for row in rows
    ]
    return jsonify({"orders": orders}), 200


@app.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT order_id FROM orders WHERE order_id = %s AND user_id = %s "
            "AND order_status != 'pending'",
            (order_id, user_id),
        )
        if not cursor.fetchone():
            return jsonify({"error": "order not found"}), 404

        order = fetch_order_detail(cursor, order_id)
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load order: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify(order), 200
