from flask import Flask

# Initialize the master Flask instance once
app = Flask(__name__)

from . import auth  # noqa: F401
from . import vendor_auth  # noqa: F401
from . import vendor_meals  # noqa: F401
from . import macro_profile  # noqa: F401
from . import menu  # noqa: F401
from . import meal_builder  # noqa: F401
from . import cart  # noqa: F401
from . import checkout  # noqa: F401