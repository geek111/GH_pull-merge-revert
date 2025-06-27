import os
import subprocess
from flask import Flask, render_template, request, redirect, session
from github import Github, GithubException

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "secret")

CACHE_DIR = "repo_cache"


def get_github():
    token = session.get("token")
    if not token:
        return None
    return Github(token, per_page=100)


def get_local_repo(repo_url):
    os.makedirs(CACHE_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(repo_url))[0]
    path = os.path.join(CACHE_DIR, name)
    if not os.path.exists(path):
        subprocess.run(["git", "clone", repo_url, path], check=True)
    else:
        subprocess.run(["git", "-C", path, "remote", "set-url", "origin", repo_url], check=True)
        subprocess.run(["git", "-C", path, "fetch", "origin"], check=True)
    return path


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/repos", methods=["POST"])
def repos():
    session["token"] = request.form["token"]
    g = get_github()
    try:
        repos = [r.full_name for r in g.get_user().get_repos()]
    except GithubException as e:
        return f"Failed to load repositories: {e.data}", 400
    return render_template("repos.html", repos=repos)


@app.route("/prs", methods=["POST"])
def prs():
    repo_name = request.form["repo"]
    session["repo"] = repo_name
    g = get_github()
    repo = g.get_repo(repo_name)
    prs = [pr for pr in repo.get_pulls(state="open", sort="created")]
    return render_template("prs.html", prs=prs, repo_name=repo_name)


def attempt_conflict_resolution(repo_url, base_branch, pr_branch):
    repo_path = get_local_repo(repo_url)
    cwd = os.getcwd()
    os.chdir(repo_path)
    subprocess.run(["git", "checkout", base_branch], check=True)
    subprocess.run(["git", "pull", "origin", base_branch], check=True)
    subprocess.run(["git", "fetch", "origin", pr_branch], check=True)
    merge_proc = subprocess.run(["git", "merge", f"origin/{pr_branch}", "-X", "theirs"], capture_output=True)
    if merge_proc.returncode != 0:
        os.chdir(cwd)
        return False, merge_proc.stderr.decode()
    subprocess.run(["git", "commit", "-am", f"Auto-merge PR {pr_branch}"], check=True)
    subprocess.run(["git", "push", "origin", base_branch], check=True)
    os.chdir(cwd)
    return True, "Conflict resolved"


@app.route("/action", methods=["POST"])
def action():
    repo_name = request.form["repo"]
    operation = request.form["operation"]
    pr_numbers = request.form.getlist("pr")
    if not pr_numbers:
        return redirect("/")

    g = get_github()
    repo = g.get_repo(repo_name)

    for number in pr_numbers:
        pr = repo.get_pull(int(number))
        if operation == "merge":
            try:
                pr.merge()
            except GithubException as e:
                if "Merge conflict" in str(e.data):
                    repo_url = repo.clone_url.replace("https://", f"https://{session['token']}@")
                    attempt_conflict_resolution(repo_url, pr.base.ref, pr.head.ref)
        elif operation == "revert":
            repo_url = repo.clone_url.replace("https://", f"https://{session['token']}@")
            repo_path = get_local_repo(repo_url)
            cwd = os.getcwd()
            os.chdir(repo_path)
            subprocess.run(["git", "pull"], check=True)
            subprocess.run(["git", "checkout", pr.base.ref], check=True)
            subprocess.run(["git", "pull", "origin", pr.base.ref], check=True)
            revert_proc = subprocess.run(["git", "revert", "-m", "1", pr.merge_commit_sha], capture_output=True)
            if revert_proc.returncode == 0:
                subprocess.run(["git", "push", "origin", pr.base.ref], check=True)
            os.chdir(cwd)
        elif operation == "close":
            pr.edit(state="closed")
    return redirect("/prs")


if __name__ == "__main__":
    app.run(debug=True)
