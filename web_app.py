from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import os
import subprocess
from github import Github, GithubException

app = Flask(__name__)
app.secret_key = 'change-me'
CACHE_DIR = "web_cache"

INDEX_HTML = """
<!doctype html>
<title>GitHub Bulk Merger Web</title>
<h2>Enter GitHub Token</h2>
<form method=post>
  <input type=password name=token required>
  <input type=submit value=Load>
</form>
"""

REPOS_HTML = """
<!doctype html>
<title>Select Repository</title>
<h2>Select Repository</h2>
<form method=post>
  <select name=repo required>
    {% for name in repos %}
    <option value="{{name}}" {% if name==selected %}selected{% endif %}>{{name}}</option>
    {% endfor %}
  </select>
  <input type=submit value=Load>
</form>
"""

PULLS_HTML = """
<!doctype html>
<title>Pull Requests</title>
<h2>Pull Requests for {{repo}}</h2>
{% with messages = get_flashed_messages(with_categories=true) %}
  {% if messages %}
    <ul>
    {% for category, message in messages %}
      <li><strong>{{category}}:</strong> {{message}}</li>
    {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
<form method=post>
  <table border=1>
    <tr><th></th><th>Number</th><th>Title</th></tr>
    {% for pr in prs %}
    <tr>
      <td><input type=checkbox name=pr value="{{pr.number}}"></td>
      <td>{{pr.number}}</td>
      <td>{{pr.title}}</td>
    </tr>
    {% endfor %}
  </table>
  <button type=submit name=action value=merge>Merge Selected</button>
  <button type=submit name=action value=revert>Revert Selected</button>
</form>
"""

def get_github():
    token = session.get('token')
    if not token:
        return None
    return Github(token, per_page=100)

def get_repo():
    g = get_github()
    repo_name = session.get('repo')
    if not g or not repo_name:
        return None
    return g.get_repo(repo_name)

def get_local_repo(repo_url):
    os.makedirs(CACHE_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(repo_url))[0]
    path = os.path.join(CACHE_DIR, name)
    if not os.path.exists(path):
        subprocess.run(["git", "clone", repo_url, path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        subprocess.run(["git", "-C", path, "remote", "set-url", "origin", repo_url], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "-C", path, "fetch", "origin"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return path

def revert_pr(repo, token, pr):
    repo_url = repo.clone_url.replace("https://", f"https://{token}@")
    repo_path = get_local_repo(repo_url)
    subprocess.run(["git", "-C", repo_path, "pull"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "-C", repo_path, "checkout", pr.base.ref], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "-C", repo_path, "pull", "origin", pr.base.ref], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    result = subprocess.run(["git", "-C", repo_path, "revert", "-m", "1", pr.merge_commit_sha], capture_output=True)
    if result.returncode == 0:
        subprocess.run(["git", "-C", repo_path, "push", "origin", pr.base.ref], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True, ''
    return False, result.stderr.decode()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['token'] = request.form['token']
        return redirect(url_for('repos'))
    return render_template_string(INDEX_HTML)

@app.route('/repos', methods=['GET', 'POST'])
def repos():
    g = get_github()
    if not g:
        return redirect(url_for('index'))
    repos = [r.full_name for r in g.get_user().get_repos()]
    if request.method == 'POST':
        session['repo'] = request.form['repo']
        return redirect(url_for('pulls'))
    return render_template_string(REPOS_HTML, repos=repos, selected=session.get('repo'))

@app.route('/pulls', methods=['GET', 'POST'])
def pulls():
    repo = get_repo()
    if not repo:
        return redirect(url_for('index'))
    prs = list(repo.get_pulls(state='open'))
    if request.method == 'POST':
        selected = request.form.getlist('pr')
        action = request.form.get('action')
        token = session.get('token')
        for pr_num in selected:
            pr = repo.get_pull(int(pr_num))
            if action == 'merge':
                try:
                    pr.merge()
                    flash(f'Merged PR #{pr.number}', 'info')
                except GithubException as e:
                    flash(f'Failed to merge PR #{pr.number}: {e.data}', 'error')
            elif action == 'revert':
                success, detail = revert_pr(repo, token, pr)
                if success:
                    flash(f'Reverted PR #{pr.number}', 'info')
                else:
                    flash(f'Failed to revert PR #{pr.number}: {detail}', 'error')
        return redirect(url_for('pulls'))
    return render_template_string(PULLS_HTML, prs=prs, repo=repo.full_name)

if __name__ == '__main__':
    app.run(debug=True)
