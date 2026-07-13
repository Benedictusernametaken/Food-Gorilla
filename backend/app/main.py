from flask import jsonify, send_file
import psycopg2
import os
# Import the shared master app instance from your package folder
from app import app


@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "message": "Welcome to the Food Gorilla Backend API!"
    })

# ======================
# Authentication
# ======================

@app.route('/api/signup', methods=['POST'])
def signup():
    # Implementation for user signup
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    # hash password
    # insert into users table

    return jsonify({"message": "User created successfully"})

@app.route('/api/login', methods=['POST'])
def login():
    #Implementation for user login
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    # Verify user credentials

    return jsonify({"message": "User logged in successfully"})

@app.route('/api/logout', methods=['POST'])
def logout():
    # Implementation for user logout
    return jsonify({"message": "User logged out successfully"})



@app.route('/health-check')
def health_check():
    connection = None
    try:
        # No hardcoded fallback — DATABASE_URL is always set by docker-compose.
        # Fail loudly if it's missing rather than silently connecting elsewhere.
        db_url = os.environ["DATABASE_URL"]
        connection = psycopg2.connect(db_url)
        cursor = connection.cursor()

        # Pure connectivity check — no dependency on any specific table,
        # so this keeps working no matter how the schema evolves.
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)