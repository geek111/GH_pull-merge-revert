import os
import json
import tempfile
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, font

from github import Github
from github.GithubException import GithubException

CONFIG_FILE = "config.json"
CACHE_DIR = "repo_cache"


class BulkMerger(tk.Tk):
    def __init__(self):
        super().__init__()
        default_font = tk.font.nametofont("TkDefaultFont")
        default_font.configure(size=13)
        self.option_add("*Font", default_font)
        self.title("GitHub Bulk Merger")
        self.geometry("600x400")
        self.token_var = tk.StringVar()
        self.repo_var = tk.StringVar()
        self.pr_vars = []
        self.cached_repos = []
        self.config_token = ""
        self.load_config()
        self.create_widgets()
        self.prs = []
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        frm = ttk.Frame(self)
        frm.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="GitHub Token:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(frm, textvariable=self.token_var, show="*").grid(row=0, column=1, sticky=tk.EW)
        ttk.Button(frm, text="Load Repos", command=self.load_repos).grid(row=0, column=2, padx=5)

        ttk.Label(frm, text="Repository:").grid(row=1, column=0, sticky=tk.W)
        self.repo_combo = ttk.Combobox(frm, textvariable=self.repo_var, state="readonly")
        self.repo_combo.grid(row=1, column=1, columnspan=2, sticky=tk.EW)
        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(2, weight=1)

        btn_load = ttk.Button(frm, text="Load PRs", command=self.load_prs)
        btn_load.grid(row=2, column=0, pady=5)
        btn_load_closed = ttk.Button(frm, text="Load Merged PRs", command=lambda: self.load_prs(state="closed"))
        btn_load_closed.grid(row=2, column=1, pady=5, sticky=tk.E)

        btn_merge = ttk.Button(frm, text="Merge Selected", command=self.merge_selected)
        btn_merge.grid(row=3, column=0, pady=5)
        btn_revert = ttk.Button(frm, text="Revert Selected", command=self.revert_selected)
        btn_revert.grid(row=3, column=1, pady=5, sticky=tk.E)
        btn_open = ttk.Button(frm, text="Open Selected", command=self.open_selected)
        btn_open.grid(row=3, column=2, pady=5, sticky=tk.E)
        btn_close = ttk.Button(frm, text="Close Selected", command=self.close_selected)
        btn_close.grid(row=3, column=3, pady=5, sticky=tk.E)

        self.pr_canvas = tk.Canvas(frm)
        self.pr_canvas.grid(row=4, column=0, columnspan=3, sticky=tk.NSEW)
        self.pr_scrollbar = ttk.Scrollbar(frm, orient="vertical", command=self.pr_canvas.yview)
        self.pr_scrollbar.grid(row=4, column=3, sticky=tk.NS)
        self.pr_canvas.configure(yscrollcommand=self.pr_scrollbar.set)
        self.pr_frame = ttk.Frame(self.pr_canvas)
        self.pr_canvas.create_window((0, 0), window=self.pr_frame, anchor="nw")
        self.pr_frame.bind("<Configure>", lambda e: self.pr_canvas.configure(scrollregion=self.pr_canvas.bbox("all")))

        frm.rowconfigure(4, weight=1)
        frm.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(2, weight=1)

        self.text_output = tk.Text(frm, height=10)
        self.text_output.grid(row=5, column=0, columnspan=4, sticky=tk.EW)

    def log(self, message):
        self.text_output.insert(tk.END, message + "\n")
        self.text_output.see(tk.END)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.token_var.set(cfg.get("token", ""))
                self.cached_repos = cfg.get("repos", [])
                self.config_token = cfg.get("token", "")
            except Exception:
                self.cached_repos = []
                self.config_token = ""

    def save_config(self):
        cfg = {"token": self.token_var.get(), "repos": self.cached_repos}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f)

    def on_close(self):
        self.save_config()
        self.destroy()

    def get_local_repo(self, repo_url):
        os.makedirs(CACHE_DIR, exist_ok=True)
        name = os.path.splitext(os.path.basename(repo_url))[0]
        path = os.path.join(CACHE_DIR, name)
        if not os.path.exists(path):
            subprocess.run(["git", "clone", repo_url, path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            subprocess.run(["git", "-C", path, "remote", "set-url", "origin", repo_url], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "-C", path, "fetch", "origin"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return path

    def load_repos(self):
        token = self.token_var.get()
        if not token:
            messagebox.showerror("Error", "Please enter a GitHub token")
            return
        repo_names = []
        if token == self.config_token and self.cached_repos:
            repo_names = self.cached_repos
        else:
            g = Github(token, per_page=100)
            try:
                repos = list(g.get_user().get_repos())
            except GithubException as e:
                messagebox.showerror("Error", f"Failed to load repositories: {e.data}")
                return
            repo_names = [r.full_name for r in repos]
            if not self.cached_repos:
                self.cached_repos = repo_names
            else:
                known = set(self.cached_repos)
                for name in repo_names:
                    if name not in known:
                        self.cached_repos.append(name)
            self.config_token = token
            self.save_config()
        self.repo_combo['values'] = repo_names
        if repo_names:
            self.repo_combo.current(0)
            self.repo_var.set(repo_names[0])

    def load_prs(self, state="open"):
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        g = Github(token, per_page=100)
        repo = g.get_repo(repo_name)
        self.prs = [pr for pr in repo.get_pulls(state=state, sort="created") if state != "closed" or pr.merged]
        for widget in self.pr_frame.winfo_children():
            widget.destroy()
        self.pr_vars.clear()
        for i, pr in enumerate(self.prs):
            var = tk.BooleanVar()
            ttk.Checkbutton(self.pr_frame, text=f"#{pr.number}: {pr.title}", variable=var).grid(row=i, column=0, sticky=tk.W)
            self.pr_vars.append(var)
        self.log(f"Loaded {len(self.prs)} pull requests.")

    def attempt_conflict_resolution(self, repo_url, base_branch, pr_branch):
        repo_path = self.get_local_repo(repo_url)
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

    def merge_selected(self):
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        g = Github(token, per_page=100)
        repo = g.get_repo(repo_name)
        for var, pr in zip(self.pr_vars, self.prs):
            if var.get():
                try:
                    pr.merge()
                    self.log(f"Merged PR #{pr.number}")
                except GithubException as e:
                    if "Merge conflict" in str(e.data):
                        self.log(f"Conflict in PR #{pr.number}, attempting auto resolution...")
                        status, detail = self.attempt_conflict_resolution(
                            repo.clone_url.replace("https://", f"https://{token}@"),
                            pr.base.ref,
                            pr.head.ref,
                        )
                        if status:
                            self.log(f"Resolved conflicts for PR #{pr.number}")
                        else:
                            self.log(f"Failed to resolve conflicts for PR #{pr.number}: {detail}")
                    else:
                        self.log(f"Failed to merge PR #{pr.number}: {e.data}")

    def revert_selected(self):
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        g = Github(token, per_page=100)
        repo = g.get_repo(repo_name)
        repo_url = repo.clone_url.replace("https://", f"https://{token}@")
        repo_path = self.get_local_repo(repo_url)
        cwd = os.getcwd()
        os.chdir(repo_path)
        subprocess.run(["git", "pull"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for var, pr in zip(self.pr_vars, self.prs):
            if var.get():
                if not pr.merged:
                    self.log(f"PR #{pr.number} not merged; skipping")
                    continue
                subprocess.run(["git", "checkout", pr.base.ref], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(["git", "pull", "origin", pr.base.ref], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                revert_proc = subprocess.run([
                    "git",
                    "revert",
                    "-m",
                    "1",
                    pr.merge_commit_sha,
                ], capture_output=True)
                if revert_proc.returncode == 0:
                    subprocess.run(["git", "push", "origin", pr.base.ref], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self.log(f"Reverted PR #{pr.number}")
                else:
                    self.log(
                        f"Failed to revert PR #{pr.number}: {revert_proc.stderr.decode()}"
                    )
        os.chdir(cwd)

    def open_selected(self):
        count = 0
        for var, pr in zip(self.pr_vars, self.prs):
            if var.get():
                webbrowser.open_new(pr.html_url)
                count += 1
        if count:
            self.log(f"Opened {count} pull request{'s' if count > 1 else ''} in browser.")

    def close_selected(self):
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        g = Github(token, per_page=100)
        repo = g.get_repo(repo_name)
        for var, pr in zip(self.pr_vars, self.prs):
            if var.get() and pr.state != "closed":
                try:
                    pr.edit(state="closed")
                    self.log(f"Closed PR #{pr.number}")
                except GithubException as e:
                    self.log(f"Failed to close PR #{pr.number}: {e.data}")


def main():
    app = BulkMerger()
    app.mainloop()


if __name__ == "__main__":
    main()
