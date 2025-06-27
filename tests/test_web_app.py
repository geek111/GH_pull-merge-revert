import unittest
import os
import json
import tempfile
from unittest.mock import patch, Mock
from web_app import app

class WebAppTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.temp_config = tempfile.NamedTemporaryFile(delete=False)
        self.addCleanup(os.unlink, self.temp_config.name)
        self.config_patcher = patch('web_app.CONFIG_FILE', self.temp_config.name)
        self.config_patcher.start()
        self.client = app.test_client()

    def tearDown(self):
        self.config_patcher.stop()

    def test_repo_list_includes_github_links(self):
        with patch('web_app.Github') as MockGithub:
            g = MockGithub.return_value
            user = g.get_user.return_value
            repo = Mock()
            repo.full_name = 'owner/repo'
            repo.html_url = 'https://github.com/owner/repo'
            user.get_repos.return_value = [repo]
            with self.client.session_transaction() as sess:
                sess['token'] = 'token'
            resp = self.client.get('/repos')
            self.assertEqual(resp.status_code, 200)
            self.assertIn(repo.html_url.encode(), resp.data)

    def test_pr_list_includes_github_links(self):
        with patch('web_app.Github') as MockGithub:
            g = MockGithub.return_value
            repo = Mock()
            repo.full_name = 'owner/repo'
            pr = Mock()
            pr.number = 1
            pr.title = 'Test'
            pr.html_url = 'https://github.com/owner/repo/pull/1'
            repo.get_pulls.return_value = [pr]
            g.get_repo.return_value = repo
            with self.client.session_transaction() as sess:
                sess['token'] = 'token'
            resp = self.client.get('/repo/owner/repo')
            self.assertEqual(resp.status_code, 200)
            self.assertIn(pr.html_url.encode(), resp.data)

    def test_index_page_loads(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'GitHub Bulk Merger - Web', resp.data)

    def test_token_saved_to_file(self):
        self.client.post('/', data={'token': 'abc'}, follow_redirects=False)
        with open(self.temp_config.name, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data.get('token'), 'abc')

    def test_index_loads_saved_token(self):
        with open(self.temp_config.name, 'w', encoding='utf-8') as f:
            json.dump({'token': 'xyz'}, f)
        resp = self.client.get('/')
        self.assertIn(b'Token configured', resp.data)

if __name__ == '__main__':
    unittest.main()
