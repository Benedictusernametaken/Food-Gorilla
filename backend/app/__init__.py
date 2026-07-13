from flask import Flask

# Initialize the master Flask instance once
app = Flask(__name__)

from . import auth  # noqa: F401
from . import vendor_auth  # noqa: F401
from . import vendor_meals  # noqa: F401