import unittest
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
            resp = self.client.get('/repos_stream')
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
            resp = self.client.get('/repo/owner/repo/prs_stream')
            self.assertEqual(resp.status_code, 200)
            self.assertIn(pr.html_url.encode(), resp.data)

    def test_index_page_loads(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'GitHub Bulk Merger - Web', resp.data)

    def test_token_saved_when_remember_checked(self):
        with patch('web_app.save_token') as mock_save:
            resp = self.client.post('/', data={'token': 'abc', 'remember': 'on'})
            self.assertEqual(resp.status_code, 302)
            mock_save.assert_called_once_with('abc')

    def test_saved_tokens_displayed_on_index(self):
        tokens = ['1234567890', 'abcdefabcdef']
        with patch('web_app.load_config', return_value={'tokens': tokens}):
            resp = self.client.get('/')
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b'-- Select saved token --', resp.data)
            self.assertIn(b'1234...7890', resp.data)
            self.assertIn(b'abcd...cdef', resp.data)

    def test_selecting_saved_token_sets_session(self):
        with self.client as c:
            with patch('web_app.load_config', return_value={'tokens': ['token1234']}):
                resp = c.post('/', data={'saved_token': 'token1234'})
                self.assertEqual(resp.status_code, 302)
                with c.session_transaction() as sess:
                    self.assertEqual(sess['token'], 'token1234')

    def test_manage_branches_lists_branches(self):
        with patch('web_app.Github') as MockGithub:
            g = MockGithub.return_value
            repo = Mock()
            repo.full_name = 'owner/repo'
            branch = Mock()
            branch.name = 'feature'
            repo.get_branches.return_value = [branch]
            g.get_repo.return_value = repo
            with self.client.session_transaction() as sess:
                sess['token'] = 'token'
            resp = self.client.get('/repo/owner/repo/branches')
            self.assertEqual(resp.status_code, 200)
            self.assertIn(branch.name.encode(), resp.data)

    def test_delete_branch_calls_github(self):
        with patch('web_app.Github') as MockGithub:
            g = MockGithub.return_value
            repo = Mock()
            repo.full_name = 'owner/repo'
            branch = Mock()
            branch.name = 'old'
            repo.get_branches.return_value = [branch]
            ref = Mock()
            repo.get_git_ref.return_value = ref
            g.get_repo.return_value = repo
            with self.client.session_transaction() as sess:
                sess['token'] = 'token'
            resp = self.client.post('/repo/owner/repo/branches', data={'branch': 'old'})
            self.assertEqual(resp.status_code, 200)
            repo.get_git_ref.assert_called_once_with('heads/old')
            ref.delete.assert_called_once()

if __name__ == '__main__':
    unittest.main()
