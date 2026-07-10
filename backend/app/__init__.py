from flask import Flask

from routes.dashboard import bp as dashboard_bp

# Initialize the master Flask instance once
app = Flask(__name__)
app.register_blueprint(dashboard_bp)