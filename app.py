import os
import tempfile
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

from github import Github
from github.GithubException import GithubException


class BulkMerger(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GitHub Bulk Merger")
        self.geometry("600x400")
        self.token_var = tk.StringVar()
        self.repo_var = tk.StringVar()
        self.pr_vars = []
        self.create_widgets()
        self.prs = []

    def create_widgets(self):
        frm = ttk.Frame(self)
        frm.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="GitHub Token:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(frm, textvariable=self.token_var, show="*").grid(row=0, column=1, sticky=tk.EW)
        ttk.Label(frm, text="Repository (owner/repo):").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(frm, textvariable=self.repo_var).grid(row=1, column=1, sticky=tk.EW)
        frm.columnconfigure(1, weight=1)

        btn_load = ttk.Button(frm, text="Load PRs", command=self.load_prs)
        btn_load.grid(row=2, column=0, pady=5)
        btn_load_closed = ttk.Button(frm, text="Load Merged PRs", command=lambda: self.load_prs(state="closed"))
        btn_load_closed.grid(row=2, column=1, pady=5, sticky=tk.E)

        btn_merge = ttk.Button(frm, text="Merge Selected", command=self.merge_selected)
        btn_merge.grid(row=3, column=0, pady=5)
        btn_revert = ttk.Button(frm, text="Revert Selected", command=self.revert_selected)
        btn_revert.grid(row=3, column=1, pady=5, sticky=tk.E)

        self.pr_frame = ttk.Frame(frm)
        self.pr_frame.grid(row=4, column=0, columnspan=2, sticky=tk.NSEW)
        frm.rowconfigure(4, weight=1)
        frm.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)

        self.text_output = tk.Text(frm, height=10)
        self.text_output.grid(row=5, column=0, columnspan=2, sticky=tk.EW)

    def log(self, message):
        self.text_output.insert(tk.END, message + "\n")
        self.text_output.see(tk.END)

    def load_prs(self, state="open"):
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        g = Github(token)
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
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "clone", repo_url, tmpdir], check=True)
            cwd = os.getcwd()
            os.chdir(tmpdir)
            subprocess.run(["git", "checkout", base_branch], check=True)
            subprocess.run(["git", "pull"], check=True)
            subprocess.run(["git", "fetch", "origin", pr_branch], check=True)
            merge_proc = subprocess.run(["git", "merge", f"origin/{pr_branch}", "-X", "theirs"], capture_output=True)
            if merge_proc.returncode != 0:
                os.chdir(cwd)
                return False, merge_proc.stderr.decode()
            subprocess.run(["git", "commit", "-am", f"Auto-merge PR {pr_branch}"], check=True)
            subprocess.run(["git", "push", "origin", base_branch], check=True)
            os.chdir(cwd)
        return True, "Conflict resolved"

    def merge_selected(self):
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        g = Github(token)
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
        g = Github(token)
        repo = g.get_repo(repo_name)
        repo_url = repo.clone_url.replace("https://", f"https://{token}@")
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "clone", repo_url, tmpdir], check=True)
            cwd = os.getcwd()
            os.chdir(tmpdir)
            subprocess.run(["git", "pull"], check=True)
            for var, pr in zip(self.pr_vars, self.prs):
                if var.get():
                    if not pr.merged:
                        self.log(f"PR #{pr.number} not merged; skipping")
                        continue
                    subprocess.run(["git", "checkout", pr.base.ref], check=True)
                    subprocess.run(["git", "pull", "origin", pr.base.ref], check=True)
                    revert_proc = subprocess.run([
                        "git",
                        "revert",
                        "-m",
                        "1",
                        pr.merge_commit_sha,
                    ], capture_output=True)
                    if revert_proc.returncode == 0:
                        subprocess.run(["git", "push", "origin", pr.base.ref], check=True)
                        self.log(f"Reverted PR #{pr.number}")
                    else:
                        self.log(
                            f"Failed to revert PR #{pr.number}: {revert_proc.stderr.decode()}"
                        )
            os.chdir(cwd)


def main():
    app = BulkMerger()
    app.mainloop()


if __name__ == "__main__":
    main()
