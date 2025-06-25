import os
import subprocess
from flask import Flask, render_template, request, redirect, url_for, session, flash
from github import Github, GithubException

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change_me")

CACHE_DIR = "repo_cache"


def get_local_repo(repo_url: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(repo_url))[0]
    path = os.path.join(CACHE_DIR, name)
    if not os.path.exists(path):
        subprocess.run(["git", "clone", repo_url, path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        subprocess.run(["git", "-C", path, "remote", "set-url", "origin", repo_url], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "-C", path, "fetch", "origin"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return path


def attempt_conflict_resolution(repo_url: str, base_branch: str, pr_branch: str):
    repo_path = get_local_repo(repo_url)
    cwd = os.getcwd()
    os.chdir(repo_path)
    subprocess.run(["git", "checkout", base_branch], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "pull", "origin", base_branch], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "fetch", "origin", pr_branch], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    merge_proc = subprocess.run(["git", "merge", f"origin/{pr_branch}", "-X", "theirs"], capture_output=True)
    if merge_proc.returncode != 0:
        os.chdir(cwd)
        return False, merge_proc.stderr.decode()
    subprocess.run(["git", "commit", "-am", f"Auto-merge PR {pr_branch}"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "push", "origin", base_branch], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.chdir(cwd)
    return True, "Conflict resolved"


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/load_repos", methods=["POST"])
def load_repos():
    token = request.form["token"].strip()
    session["token"] = token
    g = Github(token, per_page=100)
    try:
        repos = [r.full_name for r in g.get_user().get_repos()]
    except GithubException as e:
        flash(f"Failed to load repositories: {e.data}")
        repos = []
    session["repos"] = repos
    return redirect(url_for("index"))


@app.route("/load_prs", methods=["POST"])
def load_prs():
    repo_name = request.form["repo"]
    state = request.form.get("state", "open")
    session["repo_name"] = repo_name
    session["state"] = state
    token = session.get("token")
    g = Github(token, per_page=100)
    repo = g.get_repo(repo_name)
    prs = [pr for pr in repo.get_pulls(state=state, sort="created") if state != "closed" or pr.merged]
    session["prs"] = [
        {
            "number": pr.number,
            "title": pr.title,
            "html_url": pr.html_url,
            "base": pr.base.ref,
            "head": pr.head.ref,
            "merged": pr.merged,
            "merge_commit_sha": pr.merge_commit_sha,
        }
        for pr in prs
    ]
    flash(f"Loaded {len(prs)} pull requests")
    return redirect(url_for("index"))


@app.route("/operate", methods=["POST"])
def operate():
    action = request.form["action"]
    selected = request.form.getlist("selected")
    if not selected:
        flash("No pull requests selected")
        return redirect(url_for("index"))
    token = session.get("token")
    repo_name = session.get("repo_name")
    g = Github(token, per_page=100)
    repo = g.get_repo(repo_name)
    for num in selected:
        pr = repo.get_pull(int(num))
        if action == "merge":
            try:
                pr.merge()
                flash(f"Merged PR #{num}")
            except GithubException as e:
                if "Merge conflict" in str(e.data):
                    status, detail = attempt_conflict_resolution(
                        repo.clone_url.replace("https://", f"https://{token}@"),
                        pr.base.ref,
                        pr.head.ref,
                    )
                    if status:
                        flash(f"Resolved conflicts for PR #{num}")
                    else:
                        flash(f"Failed to resolve conflicts for PR #{num}: {detail}")
                else:
                    flash(f"Failed to merge PR #{num}: {e.data}")
        elif action == "revert":
            if not pr.merged:
                flash(f"PR #{num} not merged; skipping")
                continue
            repo_url = repo.clone_url.replace("https://", f"https://{token}@")
            repo_path = get_local_repo(repo_url)
            cwd = os.getcwd()
            os.chdir(repo_path)
            subprocess.run(["git", "pull"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "checkout", pr.base.ref], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "pull", "origin", pr.base.ref], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            revert_proc = subprocess.run(["git", "revert", "-m", "1", pr.merge_commit_sha], capture_output=True)
            if revert_proc.returncode == 0:
                subprocess.run(["git", "push", "origin", pr.base.ref], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                flash(f"Reverted PR #{num}")
            else:
                flash(f"Failed to revert PR #{num}: {revert_proc.stderr.decode()}")
            os.chdir(cwd)
        elif action == "close":
            if pr.state != "closed":
                try:
                    pr.edit(state="closed")
                    flash(f"Closed PR #{num}")
                except GithubException as e:
                    flash(f"Failed to close PR #{num}: {e.data}")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
