from flask import jsonify, request
import psycopg2
import os
import re
import datetime
from collections import defaultdict
import jwt
# Import the shared master app instance from your package folder
from app import app

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The weekly planner only covers Monday-Friday per Story 6's AC. Each slot
# maps to a fixed clock time so a modify/cancel cutoff can be computed
# against it — the schema only stores a VARCHAR label, not a timestamp.
DAY_NAMES = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"}
SLOT_TIMES = {
    "breakfast": datetime.time(8, 0),
    "lunch": datetime.time(12, 0),
    "dinner": datetime.time(18, 0),
}
CUTOFF_HOURS_BEFORE_DELIVERY = 2


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


def current_time():
    # Its own function (rather than calling datetime.datetime.now() inline)
    # purely so tests can patch "now" without freezing the whole clock.
    return datetime.datetime.now()


def next_occurrence(day_of_week, time_slot, now):
    """The next upcoming datetime this recurring (day_of_week, time_slot)
    slot lands on, given 'now'. If today IS that day but the slot time has
    already passed, rolls forward to next week rather than returning a
    time in the past."""
    slot_time = SLOT_TIMES[time_slot]
    days_ahead = (day_of_week - now.isoweekday()) % 7
    candidate_date = now.date() + datetime.timedelta(days=days_ahead)
    candidate_dt = datetime.datetime.combine(candidate_date, slot_time)
    if candidate_dt <= now:
        candidate_dt += datetime.timedelta(days=7)
    return candidate_dt


def is_editable(day_of_week, time_slot, now):
    """A scheduled day's meal can be modified/cancelled up until
    CUTOFF_HOURS_BEFORE_DELIVERY hours before its next occurrence."""
    occurrence = next_occurrence(day_of_week, time_slot, now)
    return now <= occurrence - datetime.timedelta(hours=CUTOFF_HOURS_BEFORE_DELIVERY)


def validate_schedule_entries(data):
    schedule = data.get("schedule")
    if not isinstance(schedule, list) or not schedule:
        return None, "schedule must be a non-empty list of {day_of_week, meal_id, time_slot}"

    parsed = []
    seen = set()
    for entry in schedule:
        if not isinstance(entry, dict):
            return None, "each schedule entry must be an object"
        try:
            day_of_week = int(entry.get("day_of_week"))
            meal_id = int(entry.get("meal_id"))
        except (TypeError, ValueError):
            return None, "day_of_week and meal_id must be integers"

        time_slot = (entry.get("time_slot") or "").strip().lower()
        if day_of_week not in DAY_NAMES:
            return None, "day_of_week must be between 1 (Monday) and 5 (Friday)"
        if time_slot not in SLOT_TIMES:
            return None, f"time_slot must be one of: {', '.join(SLOT_TIMES)}"

        key = (day_of_week, time_slot)
        if key in seen:
            return None, f"duplicate schedule entry for {DAY_NAMES[day_of_week]} {time_slot}"
        seen.add(key)

        parsed.append({"day_of_week": day_of_week, "meal_id": meal_id, "time_slot": time_slot})

    return parsed, None


def build_schedule_item(entry, meal_row):
    meal_id, name, base_price, base_calories, base_protein, base_carbs, base_fats = meal_row
    return {
        "schedule_id": entry["schedule_id"],
        "day_of_week": entry["day_of_week"],
        "day_name": DAY_NAMES[entry["day_of_week"]],
        "time_slot": entry["time_slot"],
        "meal_id": meal_id,
        "meal_name": name,
        "price": float(base_price),
        "calories": base_calories,
        "protein": base_protein,
        "carbs": base_carbs,
        "fats": base_fats,
    }


def subscription_summary(subscription_id, start_date, end_date, status, items):
    items = sorted(items, key=lambda i: (i["day_of_week"], i["time_slot"]))
    return {
        "subscription_id": subscription_id,
        "start_date": start_date.isoformat() if hasattr(start_date, "isoformat") else start_date,
        "end_date": end_date.isoformat() if hasattr(end_date, "isoformat") else end_date,
        "status": status,
        "schedule": items,
        "total_cost": round(sum(i["price"] for i in items), 2),
        "total_calories": sum(i["calories"] for i in items),
        "total_protein": sum(i["protein"] for i in items),
        "total_carbs": sum(i["carbs"] for i in items),
        "total_fats": sum(i["fats"] for i in items),
    }


@app.route('/subscriptions', methods=['POST'])
def create_subscription():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    if not (isinstance(start_date, str) and DATE_RE.match(start_date)):
        return jsonify({"error": "start_date must be in YYYY-MM-DD format"}), 400
    if not (isinstance(end_date, str) and DATE_RE.match(end_date)):
        return jsonify({"error": "end_date must be in YYYY-MM-DD format"}), 400
    if end_date <= start_date:
        return jsonify({"error": "end_date must be after start_date"}), 400

    schedule_entries, error = validate_schedule_entries(data)
    if error:
        return jsonify({"error": error}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        meal_ids = list({e["meal_id"] for e in schedule_entries})
        cursor.execute(
            "SELECT meal_id, name, base_price, base_calories, base_protein, "
            "base_carbs, base_fats FROM meals WHERE meal_id = ANY(%s)",
            (meal_ids,),
        )
        meal_map = {row[0]: row for row in cursor.fetchall()}
        missing = [mid for mid in meal_ids if mid not in meal_map]
        if missing:
            return jsonify({"error": f"meal(s) not found: {sorted(missing)}"}), 404

        cursor.execute(
            "INSERT INTO subscriptions (user_id, start_date, end_date) VALUES (%s, %s, %s) "
            "RETURNING subscription_id, start_date, end_date, status",
            (user_id, start_date, end_date),
        )
        subscription_id, saved_start, saved_end, status = cursor.fetchone()

        items = []
        for entry in schedule_entries:
            cursor.execute(
                "INSERT INTO subscription_schedule (subscription_id, delivery_day_of_week, "
                "meal_id, delivery_time_slot) VALUES (%s, %s, %s, %s) RETURNING schedule_id",
                (subscription_id, entry["day_of_week"], entry["meal_id"], entry["time_slot"]),
            )
            schedule_id = cursor.fetchone()[0]
            items.append(build_schedule_item({**entry, "schedule_id": schedule_id}, meal_map[entry["meal_id"]]))

        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to create subscription: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify(subscription_summary(subscription_id, saved_start, saved_end, status, items)), 201


def fetch_subscriptions_with_schedule(cursor, user_id, subscription_id=None):
    query = ("SELECT subscription_id, start_date, end_date, status FROM subscriptions "
              "WHERE user_id = %s")
    params = [user_id]
    if subscription_id is not None:
        query += " AND subscription_id = %s"
        params.append(subscription_id)
    query += " ORDER BY start_date DESC"
    cursor.execute(query, params)
    sub_rows = cursor.fetchall()
    if not sub_rows:
        return []

    sub_ids = [row[0] for row in sub_rows]
    cursor.execute(
        "SELECT subscription_schedule.subscription_id, subscription_schedule.schedule_id, "
        "subscription_schedule.delivery_day_of_week, subscription_schedule.delivery_time_slot, "
        "meals.meal_id, meals.name, meals.base_price, meals.base_calories, "
        "meals.base_protein, meals.base_carbs, meals.base_fats "
        "FROM subscription_schedule JOIN meals ON subscription_schedule.meal_id = meals.meal_id "
        "WHERE subscription_schedule.subscription_id = ANY(%s)",
        (sub_ids,),
    )
    grouped = defaultdict(list)
    for row in cursor.fetchall():
        (sub_id, schedule_id, day_of_week, time_slot, *meal_row) = row
        entry = {"schedule_id": schedule_id, "day_of_week": day_of_week, "time_slot": time_slot}
        grouped[sub_id].append(build_schedule_item(entry, meal_row))

    return [
        subscription_summary(row[0], row[1], row[2], row[3], grouped.get(row[0], []))
        for row in sub_rows
    ]


@app.route('/subscriptions', methods=['GET'])
def list_subscriptions():
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        subscriptions = fetch_subscriptions_with_schedule(cursor, user_id)
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load subscriptions: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify({"subscriptions": subscriptions}), 200


@app.route('/subscriptions/<int:subscription_id>', methods=['GET'])
def get_subscription(subscription_id):
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        subscriptions = fetch_subscriptions_with_schedule(cursor, user_id, subscription_id)
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to load subscription: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    if not subscriptions:
        return jsonify({"error": "subscription not found"}), 404

    return jsonify(subscriptions[0]), 200


def fetch_owned_schedule_entry(cursor, user_id, subscription_id, schedule_id):
    cursor.execute(
        "SELECT subscription_schedule.schedule_id, subscription_schedule.delivery_day_of_week, "
        "subscription_schedule.delivery_time_slot, subscription_schedule.meal_id "
        "FROM subscription_schedule JOIN subscriptions "
        "ON subscription_schedule.subscription_id = subscriptions.subscription_id "
        "WHERE subscription_schedule.schedule_id = %s "
        "AND subscription_schedule.subscription_id = %s AND subscriptions.user_id = %s",
        (schedule_id, subscription_id, user_id),
    )
    return cursor.fetchone()


@app.route('/subscriptions/<int:subscription_id>/schedule/<int:schedule_id>', methods=['PUT'])
def modify_scheduled_meal(subscription_id, schedule_id):
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    new_meal_id = data.get("meal_id")
    new_time_slot = data.get("time_slot")
    if new_meal_id is None and new_time_slot is None:
        return jsonify({"error": "meal_id or time_slot is required"}), 400

    if new_meal_id is not None:
        try:
            new_meal_id = int(new_meal_id)
        except (TypeError, ValueError):
            return jsonify({"error": "meal_id must be an integer"}), 400

    if new_time_slot is not None:
        new_time_slot = (new_time_slot or "").strip().lower()
        if new_time_slot not in SLOT_TIMES:
            return jsonify({"error": f"time_slot must be one of: {', '.join(SLOT_TIMES)}"}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        row = fetch_owned_schedule_entry(cursor, user_id, subscription_id, schedule_id)
        if not row:
            return jsonify({"error": "scheduled meal not found"}), 404

        _, day_of_week, current_slot, current_meal_id = row
        if not is_editable(day_of_week, current_slot, current_time()):
            return jsonify({"error": "the modification window for this delivery has closed"}), 409

        meal_id = new_meal_id if new_meal_id is not None else current_meal_id
        time_slot = new_time_slot if new_time_slot is not None else current_slot

        cursor.execute(
            "SELECT meal_id, name, base_price, base_calories, base_protein, "
            "base_carbs, base_fats FROM meals WHERE meal_id = %s",
            (meal_id,),
        )
        meal_row = cursor.fetchone()
        if not meal_row:
            return jsonify({"error": "meal not found"}), 404

        cursor.execute(
            "UPDATE subscription_schedule SET meal_id = %s, delivery_time_slot = %s "
            "WHERE schedule_id = %s",
            (meal_id, time_slot, schedule_id),
        )
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to modify scheduled meal: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    entry = {"schedule_id": schedule_id, "day_of_week": day_of_week, "time_slot": time_slot}
    return jsonify(build_schedule_item(entry, meal_row)), 200


@app.route('/subscriptions/<int:subscription_id>/schedule/<int:schedule_id>', methods=['DELETE'])
def cancel_scheduled_meal(subscription_id, schedule_id):
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        row = fetch_owned_schedule_entry(cursor, user_id, subscription_id, schedule_id)
        if not row:
            return jsonify({"error": "scheduled meal not found"}), 404

        _, day_of_week, current_slot, _ = row
        if not is_editable(day_of_week, current_slot, current_time()):
            return jsonify({"error": "the cancellation window for this delivery has closed"}), 409

        cursor.execute(
            "DELETE FROM subscription_schedule WHERE schedule_id = %s",
            (schedule_id,),
        )
        connection.commit()
        cursor.close()
    except Exception as e:
        return jsonify({"error": f"failed to cancel scheduled meal: {str(e)}"}), 500
    finally:
        if connection:
            connection.close()

    return jsonify({"message": "scheduled meal cancelled", "schedule_id": schedule_id}), 200
