import unittest
import os
import json
from unittest.mock import patch, Mock
from web_app import app

class WebAppTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

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

    def test_token_saved_to_config(self):
        config_path = 'config.json'
        if os.path.exists(config_path):
            os.remove(config_path)
        resp = self.client.post('/', data={'token': 'abc'}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(os.path.exists(config_path))
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        self.assertEqual(cfg.get('token'), 'abc')
        os.remove(config_path)

if __name__ == '__main__':
    unittest.main()
