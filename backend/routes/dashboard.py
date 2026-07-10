from flask import Blueprint

from controllers.dashboard_controller import (
    complete_order,
    get_daily_log,
    get_daily_log_history,
    reset_daily_log,
)

bp = Blueprint('dashboard', __name__)

bp.add_url_rule('/api/daily-log', view_func=get_daily_log, methods=['GET'])
bp.add_url_rule('/api/daily-log/history', view_func=get_daily_log_history, methods=['GET'])
bp.add_url_rule('/api/orders/complete', view_func=complete_order, methods=['POST'])
bp.add_url_rule('/api/daily-log/reset', view_func=reset_daily_log, methods=['POST'])
