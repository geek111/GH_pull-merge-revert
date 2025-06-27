import unittest
from web_app import app

class WebAppTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_index_page_loads(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'GitHub Bulk Merger - Web', resp.data)

if __name__ == '__main__':
    unittest.main()
