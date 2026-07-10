import os
from datetime import date, datetime, timedelta

import psycopg2
from flask import jsonify, request
from psycopg2.extras import RealDictCursor

from app.auth import get_authenticated_user_id


def _get_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise RuntimeError('DATABASE_URL is not configured')
    return psycopg2.connect(db_url)


def _ensure_user_defaults(user_id):
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO macro_profiles (user_id, daily_calorie_target, target_protein_g, target_carbs_g, target_fats_g)
                SELECT %s, %s, %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM macro_profiles WHERE user_id = %s
                )
                """,
                (user_id, 2200, 150, 250, 70, user_id),
            )

            cursor.execute(
                """
                INSERT INTO daily_logs (user_id, log_date, total_calories_consumed, total_protein_consumed, total_carbs_consumed, total_fats_consumed)
                SELECT %s, %s, 0, 0, 0, 0
                WHERE NOT EXISTS (
                    SELECT 1 FROM daily_logs WHERE user_id = %s AND log_date = %s
                )
                """,
                (user_id, date.today().isoformat(), user_id, date.today().isoformat()),
            )

        conn.commit()
    finally:
        conn.close()


def _get_targets(user_id):
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT daily_calorie_target, target_protein_g, target_carbs_g, target_fats_g
                FROM macro_profiles
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def _get_daily_log_row(user_id, target_date):
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT log_id, user_id, log_date, total_calories_consumed, total_protein_consumed,
                       total_carbs_consumed, total_fats_consumed
                FROM daily_logs
                WHERE user_id = %s AND log_date = %s
                """,
                (user_id, target_date),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def _get_macro_rows(user_id, target_date):
    targets = _get_targets(user_id)
    log_row = _get_daily_log_row(user_id, target_date)

    if not targets:
        raise LookupError('No macro profile found for user')

    consumed = {
        'calories': log_row['total_calories_consumed'] if log_row else 0,
        'protein': log_row['total_protein_consumed'] if log_row else 0,
        'carbs': log_row['total_carbs_consumed'] if log_row else 0,
        'fats': log_row['total_fats_consumed'] if log_row else 0,
    }

    return targets, consumed


def calculate_macro_alert_status(consumed, target):
    if target <= 0:
        return 'green'
    percent = round((consumed / target) * 100)
    if percent >= 100:
        return 'red'
    if percent >= 75:
        return 'yellow'
    return 'green'


def get_tier_rank(tier):
    if tier == 'red':
        return 2
    if tier == 'yellow':
        return 1
    return 0


def build_macro_response(consumed, target):
    percent = round((consumed / target) * 100) if target > 0 else 0
    return {
        'consumed': consumed,
        'target': target,
        'percent': percent,
        'tier': calculate_macro_alert_status(consumed, target),
    }


def get_daily_log():
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    _ensure_user_defaults(user_id)
    target_date = request.args.get('date') or date.today().isoformat()
    if not target_date:
        return jsonify({'error': 'date is required query parameter'}), 400

    try:
        targets, consumed = _get_macro_rows(user_id, target_date)
    except LookupError as exc:
        return jsonify({'error': str(exc)}), 404

    response = {
        'calories': build_macro_response(consumed['calories'], targets['daily_calorie_target']),
        'protein': build_macro_response(consumed['protein'], targets['target_protein_g']),
        'carbs': build_macro_response(consumed['carbs'], targets['target_carbs_g']),
        'fats': build_macro_response(consumed['fats'], targets['target_fats_g']),
    }
    return jsonify(response)


def get_daily_log_history():
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    _ensure_user_defaults(user_id)
    days = request.args.get('days', default=7, type=int)
    if days <= 0:
        return jsonify({'error': 'positive days are required'}), 400

    targets = _get_targets(user_id)
    if not targets:
        return jsonify({'error': 'No macro profile found for user'}), 404

    dates = []
    today = date.today()
    for offset in range(days - 1, -1, -1):
        dates.append((today - timedelta(days=offset)).isoformat())

    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            placeholders = ','.join(['%s'] * len(dates))
            cursor.execute(
                f"""
                SELECT log_date, total_calories_consumed, total_protein_consumed,
                       total_carbs_consumed, total_fats_consumed
                FROM daily_logs
                WHERE user_id = %s AND log_date IN ({placeholders})
                ORDER BY log_date ASC
                """,
                [user_id, *dates],
            )
            rows = cursor.fetchall()
    finally:
        conn.close()

    row_map = {row['log_date']: row for row in rows}
    history = []
    for target_date in dates:
        row = row_map.get(target_date)
        history.append({
            'date': target_date,
            'consumed_calories': row['total_calories_consumed'] if row else 0,
            'consumed_protein_g': row['total_protein_consumed'] if row else 0,
            'consumed_carbs_g': row['total_carbs_consumed'] if row else 0,
            'consumed_fats_g': row['total_fats_consumed'] if row else 0,
            'target_calories': targets['daily_calorie_target'],
            'target_protein_g': targets['target_protein_g'],
            'target_carbs_g': targets['target_carbs_g'],
            'target_fats_g': targets['target_fats_g'],
        })

    return jsonify(history)


def complete_order():
    payload = request.get_json(silent=True) or {}
    user_id = get_authenticated_user_id()
    calories = float(payload.get('calories')) if payload.get('calories') is not None else None
    protein_g = float(payload.get('protein_g')) if payload.get('protein_g') is not None else None
    carbs_g = float(payload.get('carbs_g')) if payload.get('carbs_g') is not None else None
    fats_g = float(payload.get('fats_g')) if payload.get('fats_g') is not None else None

    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    _ensure_user_defaults(user_id)
    if any(value is None for value in [calories, protein_g, carbs_g, fats_g]):
        return jsonify({'error': 'calories, protein_g, carbs_g, and fats_g are required and must be numbers'}), 400

    try:
        targets = _get_targets(user_id)
    except Exception:
        targets = None
    if not targets:
        return jsonify({'error': 'No macro profile found for user'}), 404

    today = date.today().isoformat()
    conn = _get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT log_id, total_calories_consumed, total_protein_consumed,
                       total_carbs_consumed, total_fats_consumed
                FROM daily_logs
                WHERE user_id = %s AND log_date = %s
                """,
                (user_id, today),
            )
            existing_log = cursor.fetchone()

            previous_totals = {
                'calories': existing_log['total_calories_consumed'] if existing_log else 0,
                'protein': existing_log['total_protein_consumed'] if existing_log else 0,
                'carbs': existing_log['total_carbs_consumed'] if existing_log else 0,
                'fats': existing_log['total_fats_consumed'] if existing_log else 0,
            }

            updated_totals = {
                'calories': previous_totals['calories'] + calories,
                'protein': previous_totals['protein'] + protein_g,
                'carbs': previous_totals['carbs'] + carbs_g,
                'fats': previous_totals['fats'] + fats_g,
            }

            if existing_log:
                cursor.execute(
                    """
                    UPDATE daily_logs
                    SET total_calories_consumed = %s,
                        total_protein_consumed = %s,
                        total_carbs_consumed = %s,
                        total_fats_consumed = %s
                    WHERE log_id = %s
                    """,
                    (updated_totals['calories'], updated_totals['protein'], updated_totals['carbs'], updated_totals['fats'], existing_log['log_id']),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO daily_logs (user_id, log_date, total_calories_consumed, total_protein_consumed, total_carbs_consumed, total_fats_consumed)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, today, updated_totals['calories'], updated_totals['protein'], updated_totals['carbs'], updated_totals['fats']),
                )
        conn.commit()
    finally:
        conn.close()

    response = {
        'calories': build_macro_response(updated_totals['calories'], targets['daily_calorie_target']),
        'protein': build_macro_response(updated_totals['protein'], targets['target_protein_g']),
        'carbs': build_macro_response(updated_totals['carbs'], targets['target_carbs_g']),
        'fats': build_macro_response(updated_totals['fats'], targets['target_fats_g']),
    }

    previous_response = {
        'calories': build_macro_response(previous_totals['calories'], targets['daily_calorie_target']),
        'protein': build_macro_response(previous_totals['protein'], targets['target_protein_g']),
        'carbs': build_macro_response(previous_totals['carbs'], targets['target_carbs_g']),
        'fats': build_macro_response(previous_totals['fats'], targets['target_fats_g']),
    }

    new_alerts = []
    for macro_key in response:
        previous_tier_rank = get_tier_rank(previous_response[macro_key]['tier'])
        current_tier_rank = get_tier_rank(response[macro_key]['tier'])
        if current_tier_rank > previous_tier_rank:
            target_key = 'daily_calorie_target' if macro_key == 'calories' else {
                'protein': 'target_protein_g',
                'carbs': 'target_carbs_g',
                'fats': 'target_fats_g',
            }[macro_key]
            over = response[macro_key]['consumed'] - targets[target_key]
            if response[macro_key]['tier'] == 'red':
                if over > 0:
                    message = f"⚠️ {macro_key.capitalize()} exceeded by {over}{' kcal' if macro_key == 'calories' else 'g'} after your last order."
                else:
                    message = f"⚠️ {macro_key.capitalize()} is exactly at your daily target after your last order."
            else:
                message = f"You're at {response[macro_key]['percent']}% of your daily {macro_key} target"
            new_alerts.append({
                'macro': macro_key,
                'percent': response[macro_key]['percent'],
                'tier': response[macro_key]['tier'],
                'message': message,
            })

    return jsonify({'totals': response, 'new_alerts': new_alerts})


def reset_daily_log():
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    _ensure_user_defaults(user_id)

    today = date.today().isoformat()
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO daily_logs (user_id, log_date, total_calories_consumed, total_protein_consumed, total_carbs_consumed, total_fats_consumed)
                SELECT %s, %s, 0, 0, 0, 0
                WHERE NOT EXISTS (
                    SELECT 1 FROM daily_logs WHERE user_id = %s AND log_date = %s
                )
                """,
                (user_id, today, user_id, today),
            )
            cursor.execute(
                """
                UPDATE daily_logs
                SET total_calories_consumed = 0,
                    total_protein_consumed = 0,
                    total_carbs_consumed = 0,
                    total_fats_consumed = 0
                WHERE user_id = %s AND log_date = %s
                """,
                (user_id, today),
            )
        conn.commit()
    finally:
        conn.close()

    return jsonify({'message': 'Daily log reset for today'})
