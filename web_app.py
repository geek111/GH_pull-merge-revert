import os
import subprocess
import json
from flask import (
    Flask,
    render_template_string,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from github import Github
from github.GithubException import GithubException

app = Flask(__name__)
app.secret_key = "replace-this"  # In production use env var

__version__ = "1.7.0"

CACHE_DIR = "repo_cache"
BRANCH_CACHE_FILE = "branch_cache.json"
CONFIG_FILE = "config.json"


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_token(token: str) -> None:
    cfg = load_config()
    tokens = cfg.get("tokens", [])
    if token not in tokens:
        tokens.append(token)
    cfg["tokens"] = tokens
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f)


def get_local_repo(repo_url: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(repo_url))[0]
    path = os.path.join(CACHE_DIR, name)
    if not os.path.exists(path):
        subprocess.run(["git", "clone", repo_url, path], check=True)
    else:
        subprocess.run(["git", "-C", path, "remote", "set-url", "origin", repo_url], check=True)
        subprocess.run(["git", "-C", path, "fetch", "origin"], check=True)
    return path


def attempt_conflict_resolution(repo_url: str, base_branch: str, pr_branch: str) -> tuple[bool, str]:
    repo_path = get_local_repo(repo_url)
    cwd = os.getcwd()
    os.chdir(repo_path)
    try:
        subprocess.run(["git", "checkout", base_branch], check=True)
        subprocess.run(["git", "pull", "origin", base_branch], check=True)
        subprocess.run(["git", "fetch", "origin", pr_branch], check=True)
        proc = subprocess.run(["git", "merge", f"origin/{pr_branch}", "-X", "theirs"], capture_output=True)
        if proc.returncode != 0:
            return False, proc.stderr.decode()
        subprocess.run(["git", "commit", "-am", f"Auto-merge PR {pr_branch}"], check=True)
        subprocess.run(["git", "push", "origin", base_branch], check=True)
        return True, "Conflict resolved"
    finally:
        os.chdir(cwd)


@app.route("/", methods=["GET", "POST"])
def index():
    cfg = load_config()
    saved_tokens = cfg.get("tokens", [])
    if request.method == "POST":
        token = request.form.get("token") or request.form.get("saved_token")
        if token:
            token = token.strip()
            session["token"] = token
            if request.form.get("remember"):
                save_token(token)
            return redirect(url_for("repos"))
    token = session.get("token")
    if token:
        session["token"] = token
    return render_template_string(
        """
        <h2>GitHub Bulk Merger - Web</h2>
        {% if token %}<p>Token configured.</p>{% endif %}
        <form method='post'>
            {% if saved_tokens %}
            <select name='saved_token'>
              <option value=''>-- Select saved token --</option>
              {% for t in saved_tokens %}
                <option value='{{ t }}'>{{ t[:4] + "..." + t[-4:] }}</option>
              {% endfor %}
            </select>
            <p>or</p>
            {% endif %}
            <input name='token' type='password' placeholder='GitHub token'>
            <label><input type='checkbox' name='remember'> Remember token</label>
            <button type='submit'>Load Repositories</button>
        </form>
        """,
        token=token,
        saved_tokens=saved_tokens,
    )


@app.route("/repos")
def repos():
    token = session.get("token")
    if not token:
        return redirect(url_for("index"))
    g = Github(token, per_page=100)
    try:
        repos = list(g.get_user().get_repos())
    except GithubException as e:
        flash(f"Failed to load repositories: {e.data}")
        return redirect(url_for("index"))
    return render_template_string(
        """
        <h2>Select Repository</h2>
        <ul>
        {% for repo in repos %}
          <li>
            <a href='{{ url_for("repo", full_name=repo.full_name) }}'>{{ repo.full_name }}</a>
            - <a href='{{ repo.html_url }}' target='_blank'>GitHub</a>
          </li>
        {% endfor %}
        </ul>
        """,
        repos=repos,
    )


@app.route("/repo/<path:full_name>", methods=["GET", "POST"])
def repo(full_name):
    token = session.get("token")
    if not token:
        return redirect(url_for("index"))
    g = Github(token, per_page=100)
    repo = g.get_repo(full_name)
    if request.method == "POST":
        action = request.form.get("action")
        numbers = [int(n) for n in request.form.getlist("pr")]
        prs = [repo.get_pull(n) for n in numbers]
        if action == "merge":
            for pr in prs:
                try:
                    pr.merge()
                except GithubException as e:
                    flash(f"Failed to merge PR #{pr.number}: {e.data}")
        elif action == "revert":
            repo_url = repo.clone_url.replace("https://", f"https://{token}@")
            for pr in prs:
                if pr.merged:
                    subprocess.run(["git", "clone", repo_url, "tmp"], check=True)
                    subprocess.run(["git", "-C", "tmp", "checkout", pr.base.ref], check=True)
                    subprocess.run(["git", "-C", "tmp", "pull"], check=True)
                    subprocess.run(["git", "-C", "tmp", "revert", "-m", "1", pr.merge_commit_sha], check=True)
                    subprocess.run(["git", "-C", "tmp", "push", "origin", pr.base.ref], check=True)
                    subprocess.run(["rm", "-rf", "tmp"])
        elif action == "close":
            for pr in prs:
                pr.edit(state="closed")
        flash("Action completed")
    open_prs = list(repo.get_pulls(state="open", sort="created"))
    return render_template_string(
        """
        <h2>Repository: {{full_name}}</h2>
        <form method='post'>
        <table id='pr-table'>
          <thead>
            <tr>
              <th></th>
              <th>Title</th>
              <th id='date-header' data-order='asc'>Date</th>
              <th>PR</th>
            </tr>
          </thead>
          <tbody>
          {% for pr in open_prs %}
            <tr class='pr-row'>
              <td><input type='checkbox' class='pr-checkbox' name='pr' value='{{pr.number}}'></td>
              <td>{{ pr.title }}</td>
              <td data-sort='{{ pr.created_at.isoformat() }}'>{{ pr.created_at.strftime('%Y-%m-%d') }}</td>
              <td><a href='{{ pr.html_url }}' target='_blank'>#{{ pr.number }}</a></td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
        <button type='submit' name='action' value='merge'>Merge Selected</button>
        <button type='submit' name='action' value='revert'>Revert Selected</button>
        <button type='submit' name='action' value='close'>Close Selected</button>
        </form>
        <p><a href='{{ url_for("branches", full_name=full_name) }}'>Manage Branches</a></p>
        <script>
        document.addEventListener('DOMContentLoaded', function() {
          const rows = Array.from(document.querySelectorAll('.pr-row'));
          const boxes = rows.map(r => r.querySelector('.pr-checkbox'));
          let last = null;
          let dragging = false;
          let dragState = false;

          rows.forEach((row, idx) => {
            const box = boxes[idx];
            row.dataset.index = idx;
            row.addEventListener('mousedown', e => {
              if (e.target.tagName.toLowerCase() === 'a') return;
              dragging = true;
              dragState = !box.checked;
              box.checked = dragState;
              last = idx;
              e.preventDefault();
            });
            row.addEventListener('mouseover', e => {
              if (dragging && e.buttons) {
                box.checked = dragState;
              }
            });
            row.addEventListener('mouseup', () => { dragging = false; });
            row.addEventListener('click', e => {
              if (e.target.tagName.toLowerCase() === 'a') return;
              if (e.shiftKey && last !== null) {
                const start = Math.min(last, idx);
                const end = Math.max(last, idx);
                for (let i = start; i <= end; i++) {
                  boxes[i].checked = box.checked;
                }
              }
              if (!e.ctrlKey) {
                last = idx;
              }
            });
          });
          document.addEventListener('mouseup', () => { dragging = false; });

          const table = document.getElementById('pr-table');
          const dateHeader = document.getElementById('date-header');
          dateHeader.addEventListener('click', () => {
            const asc = dateHeader.dataset.order !== 'asc';
            const tbody = table.tBodies[0];
            const newRows = Array.from(tbody.querySelectorAll('tr')).sort((a, b) => {
              const da = a.children[2].dataset.sort;
              const db = b.children[2].dataset.sort;
              return asc ? new Date(da) - new Date(db) : new Date(db) - new Date(da);
            });
            newRows.forEach(r => tbody.appendChild(r));
            dateHeader.dataset.order = asc ? 'asc' : 'desc';
          });
        });
        </script>
        """,
        full_name=full_name,
        open_prs=open_prs,
    )


@app.route("/repo/<path:full_name>/branches", methods=["GET", "POST"])
def branches(full_name):
    token = session.get("token")
    if not token:
        return redirect(url_for("index"))
    g = Github(token, per_page=100)
    repo = g.get_repo(full_name)
    if request.method == "POST":
        names = request.form.getlist("branch")
        for name in names:
            try:
                ref = repo.get_git_ref(f"heads/{name}")
                ref.delete()
            except GithubException as e:
                flash(f"Failed to delete {name}: {e.data}")
        flash("Action completed")
    branches = list(repo.get_branches())
    return render_template_string(
        """
        <h2>Branches: {{full_name}}</h2>
        <form method='post'>
        <table id='branch-table'>
          <thead>
            <tr>
              <th></th>
              <th>Name</th>
              <th id='date-header' data-order='asc'>Date</th>
              <th>Branch</th>
            </tr>
          </thead>
          <tbody>
          {% for br in branches %}
            <tr class='branch-row'>
              <td><input type='checkbox' class='branch-checkbox' name='branch' value='{{ br.name }}'></td>
              <td>{{ br.name }}</td>
              <td data-sort='{{ br.commit.commit.author.date.isoformat() }}'>{{ br.commit.commit.author.date.strftime('%Y-%m-%d') }}</td>
              <td><a href='https://github.com/{{ full_name }}/tree/{{ br.name }}' target='_blank'>{{ br.name }}</a></td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
        <button type='submit'>Delete Selected</button>
        </form>
        <p><a href='{{ url_for("repo", full_name=full_name) }}'>Back</a></p>
        <script>
        document.addEventListener('DOMContentLoaded', function() {
          const rows = Array.from(document.querySelectorAll('.branch-row'));
          const boxes = rows.map(r => r.querySelector('.branch-checkbox'));
          let last = null;
          let dragging = false;
          let dragState = false;

          rows.forEach((row, idx) => {
            const box = boxes[idx];
            row.dataset.index = idx;
            row.addEventListener('mousedown', e => {
              if (e.target.tagName.toLowerCase() === 'a') return;
              dragging = true;
              dragState = !box.checked;
              box.checked = dragState;
              last = idx;
              e.preventDefault();
            });
            row.addEventListener('mouseover', e => {
              if (dragging && e.buttons) {
                box.checked = dragState;
              }
            });
            row.addEventListener('mouseup', () => { dragging = false; });
            row.addEventListener('click', e => {
              if (e.target.tagName.toLowerCase() === 'a') return;
              if (e.shiftKey && last !== null) {
                const start = Math.min(last, idx);
                const end = Math.max(last, idx);
                for (let i = start; i <= end; i++) {
                  boxes[i].checked = box.checked;
                }
              }
              if (!e.ctrlKey) {
                last = idx;
              }
            });
          });
          document.addEventListener('mouseup', () => { dragging = false; });

          const table = document.getElementById('branch-table');
          const dateHeader = document.getElementById('date-header');
          dateHeader.addEventListener('click', () => {
            const asc = dateHeader.dataset.order !== 'asc';
            const tbody = table.tBodies[0];
            const newRows = Array.from(tbody.querySelectorAll('tr')).sort((a, b) => {
              const da = a.children[2].dataset.sort;
              const db = b.children[2].dataset.sort;
              return asc ? new Date(da) - new Date(db) : new Date(db) - new Date(da);
            });
            newRows.forEach(r => tbody.appendChild(r));
            dateHeader.dataset.order = asc ? 'asc' : 'desc';
          });
        });
        </script>
        """,
        full_name=full_name,
        branches=branches,
    )


if __name__ == "__main__":
    app.run(debug=True)
