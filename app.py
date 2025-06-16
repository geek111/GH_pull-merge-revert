import os
import json
import tempfile
import subprocess
import webbrowser
from datetime import datetime
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
        frm.columnconfigure(3, weight=1)
        frm.columnconfigure(4, weight=1)

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
        btn_branches = ttk.Button(frm, text="Manage Branches", command=self.open_branch_manager)
        btn_branches.grid(row=3, column=4, pady=5, sticky=tk.E)

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
        self.text_output.grid(row=5, column=0, columnspan=5, sticky=tk.EW)

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

    def open_branch_manager(self):
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        if not token or not repo_name:
            messagebox.showerror("Error", "Load repositories first")
            return
        BranchManager(self, token, repo_name)


class BranchManager(tk.Toplevel):
    def __init__(self, master, token, repo_name):
        super().__init__(master)
        self.title("Branch Manager")
        self.geometry("500x400")
        self.token = token
        self.repo_name = repo_name
        self.branch_states = {}

        self.name_filter_var = tk.StringVar()
        self.after_var = tk.StringVar()

        control = ttk.Frame(self)
        control.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(control, text="Name contains:").pack(side=tk.LEFT)
        ttk.Entry(control, textvariable=self.name_filter_var, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(control, text="Date after YYYY-MM-DD:").pack(side=tk.LEFT)
        ttk.Entry(control, textvariable=self.after_var, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(control, text="Apply", command=self.apply_filter).pack(side=tk.LEFT)

        columns = ("name", "date")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("name", text="Branch")
        self.tree.heading("date", text="Date")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree.bind("<Button-3>", self._show_menu)

        self._menu = tk.Menu(self, tearoff=0)
        self._menu.add_command(label="Check Selected", command=self.check_selected)
        self._menu.add_command(label="Uncheck Selected", command=self.uncheck_selected)

        self.load_branches()

    def _show_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
        self._menu.tk_popup(event.x_root, event.y_root)

    def check_selected(self):
        for iid in self.tree.selection():
            self.branch_states[iid] = True
            self.tree.item(iid, values=("☑ " + self.tree.item(iid, "values")[0], self.tree.item(iid, "values")[1]))

    def uncheck_selected(self):
        for iid in self.tree.selection():
            self.branch_states[iid] = False
            name = self.tree.item(iid, "values")[0]
            if name.startswith("☑ "):
                name = name[2:]
            if not name.startswith("☐ "):
                name = "☐ " + name
            self.tree.item(iid, values=(name, self.tree.item(iid, "values")[1]))

    def load_branches(self):
        g = Github(self.token, per_page=100)
        repo = g.get_repo(self.repo_name)
        branches = list(repo.get_branches())
        self.all_branches = []
        for br in branches:
            try:
                dt = br.commit.commit.author.date
            except Exception:
                dt = None
            self.all_branches.append({"name": br.name, "date": dt})
        self.populate_tree(self.all_branches)

    def apply_filter(self):
        name_filter = self.name_filter_var.get().lower()
        after_text = self.after_var.get().strip()
        after_dt = None
        if after_text:
            try:
                after_dt = datetime.strptime(after_text, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Invalid date format, use YYYY-MM-DD")
                return
        filtered = []
        for br in self.all_branches:
            if name_filter and name_filter not in br["name"].lower():
                continue
            if after_dt and br["date"] and br["date"].replace(tzinfo=None) < after_dt:
                continue
            filtered.append(br)
        self.populate_tree(filtered)

    def populate_tree(self, branches):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for br in branches:
            label = f"☐ {br['name']}"
            date_str = br['date'].strftime("%Y-%m-%d") if br['date'] else ""
            iid = self.tree.insert("", "end", values=(label, date_str))
            self.branch_states[iid] = False


def main():
    app = BulkMerger()
    app.mainloop()


if __name__ == "__main__":
    main()
