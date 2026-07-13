from flask import jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.errors import UniqueViolation
import os
# Import the shared master app instance from your package folder
from app import app


def get_db_connection():
    db_url = os.environ["DATABASE_URL"]
    return psycopg2.connect(db_url)


def user_to_dict(row):
    return {
        "id": row[0],
        "username": row[1],
        "email": row[2],
    }


@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "message": "Welcome to the Food Gorilla Backend API!"
    })


@app.route('/health-check')
def health_check():
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1;")
        cursor.fetchone()
        cursor.close()

        return jsonify({
            "status": "healthy",
            "database_connectivity": "CONNECTED"
        })

    except Exception as e:
        return jsonify({
            "status": "degraded",
            "database_connectivity": f"FAILED: {str(e)}"
        }), 500

    finally:
        if connection:
            connection.close()


@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    password_confirm = data.get('passwordConfirm', '')

    if not name or not email or not password or not password_confirm:
        return jsonify({'error': 'Name, email, and password are required.'}), 400

    if password != password_confirm:
        return jsonify({'error': 'Password and confirmation do not match.'}), 400

    password_hash = generate_password_hash(password)
    username = email

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING user_id;",
            (username, email, password_hash)
        )
        user_id = cursor.fetchone()[0]
        connection.commit()
        cursor.close()

        session.clear()
        session['user_id'] = user_id

        return jsonify({'message': 'Signup successful.', 'user': {'id': user_id, 'name': name, 'email': email}})

    except UniqueViolation:
        if connection:
            connection.rollback()
        return jsonify({'error': 'A user with that email already exists.'}), 409
    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({'error': 'Unable to create account.', 'details': str(e)}), 500
    finally:
        if connection:
            connection.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT user_id, username, email, password_hash FROM users WHERE email = %s OR username = %s;",
            (email, email)
        )
        row = cursor.fetchone()
        cursor.close()

        if not row or not check_password_hash(row[3], password):
            return jsonify({'error': 'Invalid email or password.'}), 401

        session.clear()
        session['user_id'] = row[0]

        return jsonify({'message': 'Login successful.', 'user': user_to_dict(row)})

    except Exception as e:
        return jsonify({'error': 'Unable to sign in.', 'details': str(e)}), 500
    finally:
        if connection:
            connection.close()


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out.'})


@app.route('/api/me')
def me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'user': None}), 401

    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT user_id, username, email FROM users WHERE user_id = %s;",
            (user_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            session.clear()
            return jsonify({'user': None}), 401

        return jsonify({'user': user_to_dict(row)})
    except Exception:
        return jsonify({'user': None}), 500
    finally:
        if connection:
            connection.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)