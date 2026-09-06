import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app


class SiteApiTest(unittest.TestCase):
    def test_health_response_uses_common_format(self):
        response = app.test_client().get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['success'])


if __name__ == '__main__':
    unittest.main()
