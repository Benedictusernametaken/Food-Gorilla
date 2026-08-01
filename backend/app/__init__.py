from flask import Flask

# Initialize the master Flask instance once
app = Flask(__name__)

from . import (
    auth,  # noqa: F401
    cart,  # noqa: F401
    checkout,  # noqa: F401
    daily_log,  # noqa: F401
    dashboard,  # noqa: F401
    macro_profile,  # noqa: F401
    meal_builder,  # noqa: F401
    menu,  # noqa: F401
    subscriptions,  # noqa: F401
    vendor_auth,  # noqa: F401
    vendor_meals,  # noqa: F401
)
