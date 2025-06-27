import unittest
from unittest.mock import patch, MagicMock
from web_app import app

class WebAppTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_index_page_loads(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'GitHub Bulk Merger - Web', resp.data)

    @patch('web_app.Github')
    def test_repo_page_contains_links(self, MockGithub):
        repo_mock = MagicMock()
        repo_mock.full_name = 'owner/repo'
        repo_mock.html_url = 'https://github.com/owner/repo'
        pr_mock = MagicMock()
        pr_mock.number = 1
        pr_mock.title = 'Test PR'
        pr_mock.html_url = 'https://github.com/owner/repo/pull/1'
        repo_mock.get_pulls.return_value = [pr_mock]
        user_mock = MagicMock()
        user_mock.get_repos.return_value = [repo_mock]
        MockGithub.return_value.get_user.return_value = user_mock
        MockGithub.return_value.get_repo.return_value = repo_mock

        with self.client.session_transaction() as sess:
            sess['token'] = 'dummy'

        resp = self.client.get('/repo/owner/repo')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(pr_mock.html_url.encode(), resp.data)
        self.assertIn(repo_mock.html_url.encode(), resp.data)

if __name__ == '__main__':
    unittest.main()
