import unittest

from flask import Flask

from app.auth import SESSION_TOKENS, get_authenticated_user_id
from controllers.dashboard_controller import build_macro_response, calculate_macro_alert_status, get_tier_rank


class DashboardLogicTests(unittest.TestCase):
    def test_calculate_macro_alert_status(self):
        self.assertEqual(calculate_macro_alert_status(74, 100), 'green')
        self.assertEqual(calculate_macro_alert_status(75, 100), 'yellow')
        self.assertEqual(calculate_macro_alert_status(99, 100), 'yellow')
        self.assertEqual(calculate_macro_alert_status(100, 100), 'red')

    def test_get_authenticated_user_id_uses_session_token_header(self):
        app = Flask(__name__)
        SESSION_TOKENS.clear()
        SESSION_TOKENS['dev-demo-token'] = 1
        with app.test_request_context('/', headers={'X-Session-Token': 'dev-demo-token'}):
            self.assertEqual(get_authenticated_user_id(), 1)

    def test_get_authenticated_user_id_uses_bearer_token_header(self):
        app = Flask(__name__)
        SESSION_TOKENS.clear()
        SESSION_TOKENS['bearer-token'] = 7
        with app.test_request_context('/', headers={'Authorization': 'Bearer bearer-token'}):
            self.assertEqual(get_authenticated_user_id(), 7)

    def test_get_authenticated_user_id_rejects_missing_token(self):
        app = Flask(__name__)
        SESSION_TOKENS.clear()
        with app.test_request_context('/'):
            self.assertIsNone(get_authenticated_user_id())

    def test_build_macro_response_uses_percent_and_tier(self):
        response = build_macro_response(80, 100)
        self.assertEqual(response['consumed'], 80)
        self.assertEqual(response['target'], 100)
        self.assertEqual(response['percent'], 80)
        self.assertEqual(response['tier'], 'yellow')

    def test_tier_rank_orders_alert_severity(self):
        self.assertGreater(get_tier_rank('red'), get_tier_rank('yellow'))
        self.assertGreater(get_tier_rank('yellow'), get_tier_rank('green'))


if __name__ == '__main__':
    unittest.main()
