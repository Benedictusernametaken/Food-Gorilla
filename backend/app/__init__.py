from flask import Flask

# Initialize the master Flask instance once
app = Flask(__name__)

from . import auth  # noqa: F401