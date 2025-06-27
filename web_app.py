from flask import Flask, request, redirect, url_for, render_template_string
from github import Github, GithubException
import os
import subprocess
import tempfile

app = Flask(__name__)

INDEX_HTML = """
<!doctype html>
<title>GitHub Bulk Merger Web</title>
<h1>GitHub Bulk Merger Web</h1>
{% if not token %}
<form method="get" action="/">
  <label>Token: <input type="password" name="token"></label>
  <input type="submit" value="Load Repositories">
</form>
{% else %}
<form method="get" action="/">
  <input type="hidden" name="token" value="{{ token }}">
  <select name="repo">
    {% for repo in repos %}
      <option value="{{ repo.full_name }}">{{ repo.full_name }}</option>
    {% endfor %}
  </select>
  <input type="submit" value="Load PRs">
</form>
{% endif %}
"""

PRS_HTML = """
<!doctype html>
<title>Pull Requests</title>
<h1>{{ repo.full_name }}</h1>
<form method="post" action="/merge">
  <input type="hidden" name="token" value="{{ token }}">
  <input type="hidden" name="repo" value="{{ repo.full_name }}">
  {% for pr in prs %}
    <label><input type="checkbox" name="pr" value="{{ pr.number }}">#{{ pr.number }} {{ pr.title }}</label><br>
  {% endfor %}
  <input type="submit" value="Merge Selected">
</form>
<form method="post" action="/close">
  <input type="hidden" name="token" value="{{ token }}">
  <input type="hidden" name="repo" value="{{ repo.full_name }}">
  {% for pr in prs %}
    <label><input type="checkbox" name="pr" value="{{ pr.number }}">#{{ pr.number }} {{ pr.title }}</label><br>
  {% endfor %}
  <input type="submit" value="Close Selected">
</form>
<form method="post" action="/revert">
  <input type="hidden" name="token" value="{{ token }}">
  <input type="hidden" name="repo" value="{{ repo.full_name }}">
  {% for pr in merged_prs %}
    <label><input type="checkbox" name="pr" value="{{ pr.number }}">#{{ pr.number }} {{ pr.title }}</label><br>
  {% endfor %}
  <input type="submit" value="Revert Selected">
</form>
"""

@app.route('/')
def index():
    token = request.args.get('token', '')
    repo_name = request.args.get('repo')
    if not token:
        return render_template_string(INDEX_HTML, token=None)
    g = Github(token, per_page=100)
    if not repo_name:
        repos = list(g.get_user().get_repos())
        return render_template_string(INDEX_HTML, token=token, repos=repos)
    repo = g.get_repo(repo_name)
    prs = list(repo.get_pulls(state='open'))
    merged_prs = [pr for pr in repo.get_pulls(state='closed') if pr.merged]
    return render_template_string(PRS_HTML, token=token, repo=repo, prs=prs, merged_prs=merged_prs)

@app.route('/merge', methods=['POST'])
def merge():
    token = request.form['token']
    repo_name = request.form['repo']
    numbers = request.form.getlist('pr')
    g = Github(token, per_page=100)
    repo = g.get_repo(repo_name)
    for num in numbers:
        pr = repo.get_pull(int(num))
        try:
            pr.merge()
        except GithubException:
            pass
    return redirect(url_for('index', token=token, repo=repo_name))

@app.route('/close', methods=['POST'])
def close():
    token = request.form['token']
    repo_name = request.form['repo']
    numbers = request.form.getlist('pr')
    g = Github(token, per_page=100)
    repo = g.get_repo(repo_name)
    for num in numbers:
        pr = repo.get_pull(int(num))
        if pr.state != 'closed':
            try:
                pr.edit(state='closed')
            except GithubException:
                pass
    return redirect(url_for('index', token=token, repo=repo_name))

@app.route('/revert', methods=['POST'])
def revert():
    token = request.form['token']
    repo_name = request.form['repo']
    numbers = request.form.getlist('pr')
    g = Github(token, per_page=100)
    repo = g.get_repo(repo_name)
    repo_url = repo.clone_url.replace('https://', f'https://{token}@')
    for num in numbers:
        pr = repo.get_pull(int(num))
        if pr.merged:
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(['git', 'clone', repo_url, tmp], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                cwd = os.getcwd()
                os.chdir(tmp)
                subprocess.run(['git', 'checkout', pr.base.ref], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(['git', 'pull', 'origin', pr.base.ref], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(['git', 'revert', '-m', '1', pr.merge_commit_sha], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(['git', 'push', 'origin', pr.base.ref], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                os.chdir(cwd)
    return redirect(url_for('index', token=token, repo=repo_name))

if __name__ == '__main__':
    app.run(debug=True)
