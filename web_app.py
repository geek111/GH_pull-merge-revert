from flask import Flask, request, redirect, url_for, session
from github import Github, GithubException
import git
import os

app = Flask(__name__)
app.secret_key = 'change-me'

REPO_BASE = '/tmp/gitpilot_repos'

os.makedirs(REPO_BASE, exist_ok=True)


def get_github():
    token = session.get('token')
    if not token:
        return None
    return Github(token, per_page=100)


def get_local_repo(token: str, full_name: str) -> git.Repo:
    path = os.path.join(REPO_BASE, full_name.replace('/', '_'))
    url = f"https://{token}@github.com/{full_name}.git"
    if os.path.isdir(path):
        repo = git.Repo(path)
        repo.remote().fetch()
    else:
        repo = git.Repo.clone_from(url, path)
    return repo


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['token'] = request.form.get('token', '').strip()
        return redirect(url_for('list_repos'))
    return '''
        <h2>GitHub Token</h2>
        <form method="post">
            <input type="password" name="token"/>
            <input type="submit" value="Load Repositories"/>
        </form>
    '''


@app.route('/repos')
def list_repos():
    gh = get_github()
    if not gh:
        return redirect(url_for('index'))
    repos = gh.get_user().get_repos()
    html = '<h2>Select Repository</h2><ul>'
    for repo in repos:
        html += f'<li><a href="{url_for("list_prs", full_name=repo.full_name)}">{repo.full_name}</a></li>'
    html += '</ul>'
    return html


@app.route('/repos/<path:full_name>', methods=['GET', 'POST'])
def list_prs(full_name):
    gh = get_github()
    if not gh:
        return redirect(url_for('index'))
    repo = gh.get_repo(full_name)
    if request.method == 'POST':
        action = request.form.get('action')
        selected = request.form.getlist('pr')
        for num in selected:
            pr = repo.get_pull(int(num))
            if action == 'merge':
                try:
                    pr.merge()
                except GithubException as e:
                    print(e.data)
            elif action == 'revert' and pr.merged:
                repo_obj = get_local_repo(session['token'], full_name)
                repo_obj.git.checkout(pr.base.ref)
                repo_obj.git.pull('origin', pr.base.ref)
                try:
                    repo_obj.git.revert('-m', '1', pr.merge_commit_sha)
                    repo_obj.git.push('origin', pr.base.ref)
                except git.exc.GitCommandError as e:
                    print(e)
        return redirect(url_for('list_prs', full_name=full_name))

    pulls = repo.get_pulls(state='all')
    html = f'<h2>Pull Requests for {full_name}</h2><form method="post">'
    for pr in pulls:
        html += f'<div><input type="checkbox" name="pr" value="{pr.number}">#{pr.number} {pr.title} ({pr.state})</div>'
    html += '''
        <button type="submit" name="action" value="merge">Merge Selected</button>
        <button type="submit" name="action" value="revert">Revert Selected</button>
    </form>'''
    return html


if __name__ == '__main__':
    app.run(debug=True)
