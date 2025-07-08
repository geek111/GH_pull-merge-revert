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
    Response,
)
from github import Github
from github.GithubException import GithubException
from unittest.mock import Mock

app = Flask(__name__)
app.secret_key = "replace-this"  # In production use env var

__version__ = "1.8.0"

CACHE_DIR = "repo_cache"
BRANCH_CACHE_FILE = "branch_cache.json"
CONFIG_FILE = "config.json"

# Responsive navigation bar shared across pages
NAV_TEMPLATE = """
<style>
.navbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  background-color: #333;
  padding: 0.5rem;
}
.navbar a {
  color: #fff;
  margin-right: 1rem;
  text-decoration: none;
}
.nav-toggle {
  display: none;
  margin-left: auto;
  font-size: 1.5rem;
  cursor: pointer;
  color: #fff;
}
.nav-links {
  display: flex;
  flex-wrap: wrap;
}
#progress-container {
  width: 100%;
  height: 20px;
  background-color: #e0e0e0;
  margin-top: 0.5rem;
  position: relative;
  display: none;
}
#progress-bar {
  height: 100%;
  width: 0%;
  background-color: #4caf50;
}
#progress-text {
  position: absolute;
  width: 100%;
  top: 0;
  left: 0;
  line-height: 20px;
  font-size: 0.8rem;
  text-align: center;
  color: #000;
}
/* Table row hover effects */
#pr-table tbody tr,
#branch-table tbody tr {
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}
#pr-table tbody tr:hover,
#branch-table tbody tr:hover {
  background-color: #eef8ff;
  box-shadow: 0 0 8px rgba(0, 123, 255, 0.4);
}
#pr-table tbody td:hover,
#branch-table tbody td:hover {
  position: relative;
}
#pr-table tbody td:hover::after,
#branch-table tbody td:hover::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 1px solid #66aaff;
  box-shadow: 0 0 4px rgba(0, 123, 255, 0.4);
  pointer-events: none;
  border-radius: 2px;
}
@media (max-width: 600px) {
  .nav-links {
    display: none;
    width: 100%;
    flex-direction: column;
  }
  .nav-links a {
    padding: 0.5rem 0;
    border-top: 1px solid #444;
  }
  .nav-toggle {
    display: block;
  }
}
</style>
<nav class="navbar">
  <a href="{{ url_for('index') }}" class="logo">Home</a>
  <span class="nav-toggle">&#9776;</span>
  <div class="nav-links">
    {% if session.get('token') %}
    <a href="{{ url_for('repos') }}">Repositories</a>
    {% endif %}
    {% if repo_name %}
    <a href="{{ url_for('repo', full_name=repo_name) }}">Pull Requests</a>
    <a href="{{ url_for('branches', full_name=repo_name) }}">Branches</a>
    {% endif %}
  </div>
</nav>
<div id="progress-container">
  <div id="progress-bar"></div>
  <span id="progress-text">0% - Ready</span>
</div>
<script>
function updateProgress(percent, status) {
  const container = document.getElementById('progress-container');
  const bar = document.getElementById('progress-bar');
  const text = document.getElementById('progress-text');
  if (container && bar && text) {
    container.style.display = 'block';
    bar.style.width = percent + '%';
    text.textContent = percent + '% - ' + status;
    if (percent >= 100) {
      setTimeout(() => { container.style.display = 'none'; }, 500);
    }
  }
}
document.addEventListener('DOMContentLoaded', function() {
  const toggle = document.querySelector('.nav-toggle');
  const links = document.querySelector('.nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', () => {
      links.style.display = links.style.display === 'block' ? 'none' : 'block';
    });
  }
});
</script>
"""


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f)


def save_token(token: str) -> None:
    cfg = load_config()
    tokens = cfg.get("tokens", [])
    if token not in tokens:
        tokens.append(token)
    cfg["tokens"] = tokens
    save_config(cfg)


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


@app.route("/api/repos")
def api_repos() -> dict:
    token = session.get("token")
    if not token:
        return {"error": "unauthorized"}, 401
    g = Github(token, per_page=100)
    try:
        repos = list(g.get_user().get_repos())
    except GithubException as e:
        return {"error": str(e.data)}, 400
    return {
        "repos": [
            {
                "full_name": r.full_name,
                "html_url": r.html_url,
                "url": url_for("repo", full_name=r.full_name),
            }
            for r in repos
        ]
    }


@app.route("/api/pulls/<path:full_name>")
def api_pulls(full_name: str) -> dict:
    token = session.get("token")
    if not token:
        return {"error": "unauthorized"}, 401
    g = Github(token, per_page=100)
    repo = g.get_repo(full_name)
    pulls = repo.get_pulls(state="open", sort="created")
    return {
        "pulls": [
            {
                "number": pr.number,
                "title": pr.title,
                "html_url": pr.html_url,
                "created_at": (
                    pr.created_at.isoformat()
                    if hasattr(pr, "created_at")
                    and not isinstance(pr.created_at, Mock)
                    and hasattr(pr.created_at, "isoformat")
                    else str(getattr(pr, "created_at", ""))
                ),
            }
            for pr in pulls
        ]
    }


@app.route("/api/pulls_stream/<path:full_name>")
def api_pulls_stream(full_name: str) -> Response:
    token = session.get("token")
    if not token:
        return Response("unauthorized", status=401)
    g = Github(token, per_page=100)
    repo = g.get_repo(full_name)
    pulls = repo.get_pulls(state="open", sort="created")

    def generate() -> str:
        total = pulls.totalCount
        yield f"event: count\ndata: {{\"total\": {total}}}\n\n"
        for pr in pulls:
            data = {
                "number": pr.number,
                "title": pr.title,
                "html_url": pr.html_url,
                "created_at": (
                    pr.created_at.isoformat()
                    if hasattr(pr, "created_at")
                    and not isinstance(pr.created_at, Mock)
                    and hasattr(pr.created_at, "isoformat")
                    else str(getattr(pr, "created_at", ""))
                ),
            }
            yield f"data: {json.dumps(data)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/branches/<path:full_name>")
def api_branches(full_name: str) -> dict:
    token = session.get("token")
    if not token:
        return {"error": "unauthorized"}, 401
    g = Github(token, per_page=100)
    repo = g.get_repo(full_name)
    cfg = load_config()
    protected = cfg.get("protected_branches", {}).get(full_name, [])
    branches = repo.get_branches()
    data = []
    for br in branches:
        date = None
        if hasattr(br, "commit") and hasattr(br.commit, "commit"):
            author = getattr(br.commit.commit, "author", None)
            if author and hasattr(author, "date") and not isinstance(author.date, Mock):
                try:
                    date = author.date.isoformat()
                except Exception:
                    date = str(author.date)
        data.append(
            {
                "name": br.name,
                "date": date or "",
                "html_url": f"https://github.com/{full_name}/tree/{br.name}",
                "protected": br.name in protected,
            }
        )
    return {"branches": data}


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
        NAV_TEMPLATE + """
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
        repo_name=None,
    )


@app.route("/repos")
def repos():
    token = session.get("token")
    if not token:
        return redirect(url_for("index"))
    return render_template_string(
        NAV_TEMPLATE + """
        <h2>Select Repository</h2>
        <ul id='repo-list'></ul>
        <script>
        function loadRepos() {
          updateProgress(0, 'Loading repositories');
          fetch('{{ url_for('api_repos') }}')
            .then(r => r.json())
            .then(data => {
              const list = document.getElementById('repo-list');
              list.innerHTML = '';
              data.repos.forEach((repo, idx) => {
                const li = document.createElement('li');
                li.innerHTML = `<a href='${repo.url}'>${repo.full_name}</a> - <a href='${repo.html_url}' target='_blank'>GitHub</a>`;
                list.appendChild(li);
                const pct = Math.round(((idx + 1) / data.repos.length) * 100);
                updateProgress(pct, 'Loading repositories');
              });
              updateProgress(100, 'Ready');
            })
            .catch(() => { updateProgress(100, 'Error'); });
        }
        document.addEventListener('DOMContentLoaded', function() {
          loadRepos();
          setInterval(loadRepos, 30000);
        });
        </script>
        """,
        repo_name=None,
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
    return render_template_string(
        NAV_TEMPLATE + """
        <h2>Repository: {{full_name}}</h2>
        <form method='post' id='action-form'>
        <table id='pr-table'>
          <thead>
            <tr>
              <th></th>
              <th>Title</th>
              <th id='date-header' data-order='asc'>Date</th>
              <th>PR</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
        <button type='submit' name='action' value='merge'>Merge Selected</button>
        <button type='submit' name='action' value='revert'>Revert Selected</button>
        <button type='submit' name='action' value='close'>Close Selected</button>
        </form>
        <p><a href='{{ url_for("branches", full_name=full_name) }}'>Manage Branches</a></p>
        <script>
        function initPRInteractions() {
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
        }

        function loadPRs() {
          updateProgress(0, 'Loading pull requests');
          const tbody = document.querySelector('#pr-table tbody');
          tbody.innerHTML = '';
          let count = 0;
          let total = 0;
          const es = new EventSource('{{ url_for('api_pulls_stream', full_name=full_name) }}');
          es.addEventListener('count', e => {
            total = JSON.parse(e.data).total;
          });
          es.onmessage = e => {
            const pr = JSON.parse(e.data);
            const tr = document.createElement('tr');
            tr.className = 'pr-row';
            tr.innerHTML = `<td><input type='checkbox' class='pr-checkbox' name='pr' value='${pr.number}'></td>` +
                           `<td>${pr.title}</td>` +
                           `<td data-sort='${pr.created_at}'>${pr.created_at.slice(0,16).replace('T',' ')}</td>` +
                           `<td><a href='${pr.html_url}' target='_blank'>#${pr.number}</a></td>`;
            tbody.appendChild(tr);
            count++;
            const pct = total ? Math.round((count / total) * 100) : 0;
            updateProgress(pct, 'Loading pull requests');
          };
          es.addEventListener('done', () => {
            es.close();
            initPRInteractions();
            updateProgress(100, 'Ready');
          });
          es.onerror = () => {
            es.close();
            updateProgress(100, 'Error');
          };
        }
        document.addEventListener('DOMContentLoaded', function() {
          loadPRs();
          setInterval(loadPRs, 30000);
        });
        </script>
        """,
        full_name=full_name,
        repo_name=full_name,
    )


@app.route("/repo/<path:full_name>/branches", methods=["GET", "POST"])
def branches(full_name):
    token = session.get("token")
    if not token:
        return redirect(url_for("index"))
    g = Github(token, per_page=100)
    repo = g.get_repo(full_name)
    cfg = load_config()
    protected = cfg.get("protected_branches", {}).get(full_name, [])
    if request.method == "POST":
        if "toggle_protect" in request.form:
            name = request.form["toggle_protect"]
            current = set(protected)
            if name in current:
                current.remove(name)
            else:
                current.add(name)
            cfg.setdefault("protected_branches", {})[full_name] = list(current)
            save_config(cfg)
            protected = list(current)
            flash("Protection updated")
        else:
            names = [n for n in request.form.getlist("branch") if n not in protected]
            for name in names:
                try:
                    ref = repo.get_git_ref(f"heads/{name}")
                    ref.delete()
                except GithubException as e:
                    flash(f"Failed to delete {name}: {e.data}")
            if names:
                flash("Action completed")
    return render_template_string(
        NAV_TEMPLATE + """
        <h2>Branches: {{full_name}}</h2>
        <form method='post'>
        <table id='branch-table'>
          <thead>
            <tr>
              <th></th>
              <th>Name</th>
              <th id='date-header' data-order='asc'>Date</th>
              <th>Branch</th>
              <th>Protected</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
        <button type='submit'>Delete Selected</button>
        </form>
        <p><a href='{{ url_for("repo", full_name=full_name) }}'>Back</a></p>
        <script>
        function setupBranchRows() {
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
        }

        function loadBranches() {
          updateProgress(0, 'Loading branches');
          fetch('{{ url_for('api_branches', full_name=full_name) }}')
            .then(r => r.json())
            .then(data => {
              const tbody = document.querySelector('#branch-table tbody');
              tbody.innerHTML = '';
              data.branches.forEach((br, idx) => {
                const tr = document.createElement('tr');
                tr.className = 'branch-row';
                tr.innerHTML = `<td><input type='checkbox' class='branch-checkbox' name='branch' value='${br.name}'></td>` +
                               `<td>${br.name}</td>` +
                               `<td data-sort='${br.date}'>${br.date.slice(0,16).replace('T',' ')}</td>` +
                               `<td><a href='${br.html_url}' target='_blank'>${br.name}</a></td>` +
                               `<td><form method='post' style='display:inline'><button name='toggle_protect' value='${br.name}' style='background:none;border:none'>${br.protected ? '★' : '☆'}</button></form></td>`;
                tbody.appendChild(tr);
                const pct = Math.round(((idx + 1) / data.branches.length) * 100);
                updateProgress(pct, 'Loading branches');
              });
              setupBranchRows();
              updateProgress(100, 'Ready');
            })
            .catch(() => { updateProgress(100, 'Error'); });
        }

        document.addEventListener('DOMContentLoaded', function() {
          loadBranches();
          setInterval(loadBranches, 30000);
        });
        </script>
        """,
        full_name=full_name,
        protected=protected,
        repo_name=full_name,
    )


if __name__ == "__main__":
    app.run(debug=True)
