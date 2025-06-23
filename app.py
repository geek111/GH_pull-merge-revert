import os
import json
import tempfile
import subprocess
import webbrowser
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

from github import Github
from github.GithubException import GithubException
import threading


def blend_colors(widget, fg, bg, alpha=0.5):
    """Return blended color between fg and bg with given alpha."""
    fg_rgb = widget.winfo_rgb(fg)
    bg_rgb = widget.winfo_rgb(bg)
    r = int(fg_rgb[0] * alpha + bg_rgb[0] * (1 - alpha)) // 256
    g = int(fg_rgb[1] * alpha + bg_rgb[1] * (1 - alpha)) // 256
    b = int(fg_rgb[2] * alpha + bg_rgb[2] * (1 - alpha)) // 256
    return f"#{r:02x}{g:02x}{b:02x}"

CONFIG_FILE = "config.json"
CACHE_DIR = "repo_cache"
BRANCH_CACHE_FILE = "branch_cache.json"
__version__ = "1.2.0"


def load_branch_cache():
    if os.path.exists(BRANCH_CACHE_FILE):
        try:
            with open(BRANCH_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_branch_cache(cache):
    with open(BRANCH_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)


branch_cache = load_branch_cache()


class BulkMerger(tk.Tk):
    def __init__(self):
        super().__init__()
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=13)
        self.option_add("*Font", default_font)
        self.title("GitHub Bulk Merger")
        self.geometry("600x400")
        # style for widgets will be configured after frames are created
        self.token_var = tk.StringVar()
        self.repo_var = tk.StringVar()
        self.pr_vars = []
        self.cached_repos = []
        self.config_token = ""
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)
        self.load_config()
        self.create_widgets()
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")
        self.minsize(self.winfo_width(), self.winfo_height())
        self.prs = []
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        frm = ttk.Frame(self)
        frm.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # get window background to mimic transparency
        status_bg = self.cget("bg")

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
        btn_branches = ttk.Button(frm, text="Manage Branches", command=self.manage_branches)
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
        frm.rowconfigure(6, weight=0)
        frm.rowconfigure(7, weight=0)
        frm.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(2, weight=1)

        self.text_output = tk.Text(frm, height=10)
        self.text_output.grid(row=5, column=0, columnspan=4, sticky=tk.EW)
        self.status_label = tk.Label(
            frm,
            textvariable=self.status_var,
            bg=status_bg,
            borderwidth=0,
        )
        self.status_label.grid(row=6, column=0, columnspan=4, sticky=tk.W)
        progress_frame = ttk.Frame(frm)
        progress_frame.grid(row=7, column=0, columnspan=4, sticky=tk.EW, pady=5)
        progress_frame.columnconfigure(0, weight=1)
        self.progress_text = tk.StringVar(value="0%")
        self.progress_label = tk.Label(
            progress_frame,
            textvariable=self.progress_text,
            bg=status_bg,
            borderwidth=0,
            anchor="center",
        )
        self.progress_label.grid(row=0, column=0, sticky="ew")
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress.grid(row=1, column=0, sticky="ew")
        faded = blend_colors(self.progress_label, self.progress_label.cget("fg"), status_bg, 0.5)
        self.progress_label.configure(fg=faded)

    def log(self, message):
        self.text_output.insert(tk.END, message + "\n")
        self.text_output.see(tk.END)

    def set_status(self, message):
        self.status_var.set(message)
        self.update_progress_text()
        self.update_idletasks()

    def set_progress(self, value):
        self.progress_var.set(value)
        self.update_progress_text()
        self.update_idletasks()

    def reset_progress(self):
        self.set_progress(0)

    def update_progress_text(self):
        self.progress_text.set(f"{int(self.progress_var.get())}%")

    def run_async(self, func):
        threading.Thread(target=func, daemon=True).start()

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
        def worker():
            token = self.token_var.get()
            if not token:
                self.after(0, lambda: messagebox.showerror("Error", "Please enter a GitHub token"))
                return
            self.after(0, lambda: (self.set_status("Loading repositories..."), self.reset_progress()))
            repo_names = []
            if token == self.config_token and self.cached_repos:
                repo_names = self.cached_repos
            else:
                g = Github(token, per_page=100)
                try:
                    repos = list(g.get_user().get_repos())
                except GithubException as e:
                    self.after(0, lambda: messagebox.showerror("Error", f"Failed to load repositories: {e.data}"))
                    self.after(0, lambda: self.set_status("Ready"))
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
            def update_combo():
                self.repo_combo['values'] = repo_names
                if repo_names:
                    self.repo_combo.current(0)
                    self.repo_var.set(repo_names[0])
                self.set_progress(100)
                self.set_status("Ready")
            self.after(0, update_combo)
        self.run_async(worker)

    def load_prs(self, state="open"):
        def worker():
            token = self.token_var.get()
            repo_name = self.repo_var.get()
            self.after(0, lambda: (self.set_status("Loading pull requests..."), self.reset_progress()))
            g = Github(token, per_page=100)
            repo = g.get_repo(repo_name)
            prs = [pr for pr in repo.get_pulls(state=state, sort="created") if state != "closed" or pr.merged]
            def update_ui():
                self.prs = prs
                for widget in self.pr_frame.winfo_children():
                    widget.destroy()
                self.pr_vars.clear()
                for i, pr in enumerate(self.prs):
                    var = tk.BooleanVar()
                    ttk.Checkbutton(
                        self.pr_frame,
                        text=f"#{pr.number}: {pr.title}",
                        variable=var,
                    ).grid(row=i, column=0, sticky=tk.W)
                    self.pr_vars.append(var)
                self.log(f"Loaded {len(self.prs)} pull requests.")
                self.set_progress(100)
                self.set_status("Ready")
                PullRequestList(self, token, repo_name)
            self.after(0, update_ui)
        self.run_async(worker)

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
        self.set_status("Ready")
        return True, "Conflict resolved"

    def merge_selected(self):
        self.set_status("Merging...")
        self.reset_progress()
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        g = Github(token, per_page=100)
        repo = g.get_repo(repo_name)
        selected = [(var, pr) for var, pr in zip(self.pr_vars, self.prs) if var.get()]
        total = len(selected)
        for idx, (_, pr) in enumerate(selected):
            try:
                pr.merge()
                self.log(f"Merged PR #{pr.number}")
            except GithubException as e:
                if "Merge conflict" in str(e.data):
                    self.log(f"Conflict in PR #{pr.number}, attempting autoresolution...")
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
            progress = ((idx + 1) / total) * 100 if total else 100
            self.set_progress(progress)
        self.set_status("Ready")

    def revert_selected(self):
        self.set_status("Reverting...")
        self.reset_progress()
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        g = Github(token, per_page=100)
        repo = g.get_repo(repo_name)
        repo_url = repo.clone_url.replace("https://", f"https://{token}@")
        repo_path = self.get_local_repo(repo_url)
        cwd = os.getcwd()
        os.chdir(repo_path)
        subprocess.run(["git", "pull"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        selected = [pr for var, pr in zip(self.pr_vars, self.prs) if var.get()]
        total = len(selected)
        for idx, pr in enumerate(selected):
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
            progress = ((idx + 1) / total) * 100 if total else 100
            self.set_progress(progress)
        os.chdir(cwd)
        self.set_status("Ready")

    def open_selected(self):
        self.set_status("Opening...")
        self.reset_progress()
        selected = [pr for var, pr in zip(self.pr_vars, self.prs) if var.get()]
        count = 0
        total = len(selected)
        for idx, pr in enumerate(selected):
            webbrowser.open_new(pr.html_url)
            count += 1
            progress = ((idx + 1) / total) * 100 if total else 100
            self.set_progress(progress)
        if count:
            self.log(f"Opened {count} pull request{'s' if count > 1 else ''} in browser.")
        self.set_status("Ready")

    def close_selected(self):
        self.set_status("Closing PRs...")
        self.reset_progress()
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        g = Github(token, per_page=100)
        repo = g.get_repo(repo_name)
        selected = [pr for var, pr in zip(self.pr_vars, self.prs) if var.get() and pr.state != "closed"]
        total = len(selected)
        for idx, pr in enumerate(selected):
            try:
                pr.edit(state="closed")
                self.log(f"Closed PR #{pr.number}")
            except GithubException as e:
                self.log(f"Failed to close PR #{pr.number}: {e.data}")
            progress = ((idx + 1) / total) * 100 if total else 100
            self.set_progress(progress)
        self.set_status("Ready")

    def manage_branches(self):
        token = self.token_var.get()
        repo_name = self.repo_var.get()
        if not token or not repo_name:
            messagebox.showerror("Error", "Load repository first")
            return
        self.set_status("Opening branch manager...")
        BranchManager(self, token, repo_name)


class BranchManager(tk.Toplevel):
    def __init__(self, master, token, repo_name):
        super().__init__(master)
        self.title("Branch Manager")
        self.geometry("500x400")
        self.token = token
        self.repo_name = repo_name
        self.status_var = tk.StringVar(value="Ready")
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_text = tk.StringVar(value="0%")
        self.branch_vars = {}
        self.branches = []
        self.branch_statuses = {}
        self.create_widgets()
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")
        self.minsize(self.winfo_width(), self.winfo_height())
        self.load_branches()

    def set_status(self, message):
        self.status_var.set(message)
        self.update_progress_text()
        self.update_idletasks()
        self.master.set_status(message)

    def set_progress(self, value):
        self.progress_var.set(value)
        self.update_progress_text()
        self.update_idletasks()

    def reset_progress(self):
        self.set_progress(0)

    def update_progress_text(self):
        self.progress_text.set(f"{int(self.progress_var.get())}%")

    def create_widgets(self):
        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        filter_frame = ttk.Frame(frm)
        filter_frame.pack(fill=tk.X, pady=5)
        ttk.Label(filter_frame, text="Name filter:").pack(side=tk.LEFT)
        self.name_filter = ttk.Entry(filter_frame)
        self.name_filter.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.name_filter.bind("<KeyRelease>", lambda e: self.apply_filters())
        ttk.Label(filter_frame, text="Date after (YYYY-MM-DD):").pack(side=tk.LEFT)
        self.date_filter = ttk.Entry(filter_frame, width=12)
        self.date_filter.pack(side=tk.LEFT)
        self.date_filter.bind("<KeyRelease>", lambda e: self.apply_filters())

        self.tree = ttk.Treeview(
            frm,
            columns=("selected", "branch", "date", "status"),
            show="headings",
            selectmode="extended",
        )
        self.tree.heading("selected", text="")
        self.tree.heading("branch", text="Branch")
        self.tree.heading("date", text="Date")
        self.tree.heading("status", text="Status")
        self.tree.column("selected", width=30, anchor="center")
        self.tree.column("branch", width=250)
        self.tree.column("date", width=150)
        self.tree.column("status", width=80, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scroll = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.bind("<Button-3>", self.show_context_menu)

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Check highlighted", command=self.check_selected)
        self.menu.add_command(label="Uncheck highlighted", command=self.uncheck_selected)

        btn_frame = ttk.Frame(frm)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_branches).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Delete Checked", command=self.delete_checked).pack(side=tk.RIGHT)
        ttk.Label(frm, textvariable=self.status_var).pack(anchor=tk.W)
        progress_frame = ttk.Frame(frm)
        progress_frame.pack(fill=tk.X, pady=5)
        progress_frame.columnconfigure(0, weight=1)
        status_bg = self.master.cget("bg")
        self.progress_label = tk.Label(
            progress_frame,
            textvariable=self.progress_text,
            bg=status_bg,
            borderwidth=0,
            anchor="center",
        )
        self.progress_label.grid(row=0, column=0, sticky="ew")
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress.grid(row=1, column=0, sticky="ew")
        faded = blend_colors(self.progress_label, self.progress_label.cget("fg"), status_bg, 0.5)
        self.progress_label.configure(fg=faded)

    def show_context_menu(self, event):
        self.tree.focus_set()
        self.menu.tk_popup(event.x_root, event.y_root)

    def refresh_branches(self):
        self.set_status("Refreshing branches...")
        branch_cache.pop(self.repo_name, None)
        save_branch_cache(branch_cache)
        self.load_branches(force=True)

    def load_branches(self, force=False):
        def worker():
            cached = None if force else branch_cache.get(self.repo_name)
            if cached:
                branch_list = [
                    (name, datetime.datetime.fromisoformat(dt)) for name, dt in cached
                ]
            else:
                self.master.after(0, lambda: (self.set_status("Loading branches..."), self.reset_progress()))
                g = Github(self.token, per_page=100)
                repo = g.get_repo(self.repo_name)
                branch_objs = list(repo.get_branches())
                branch_list = []
                for idx, br in enumerate(branch_objs):
                    dt = br.commit.commit.author.date
                    branch_list.append((br.name, dt))
                    progress = ((idx + 1) / (len(branch_objs) * 2)) * 100 if branch_objs else 0
                    self.after(0, lambda p=progress: self.set_progress(p))
                branch_cache[self.repo_name] = [(b, d.isoformat()) for b, d in branch_list]
                save_branch_cache(branch_cache)

            self.branches = []
            self.branch_statuses = {}
            self.branch_vars = {}
            self.after(0, lambda: self.tree.delete(*self.tree.get_children()))

            g = Github(self.token, per_page=100)
            repo = g.get_repo(self.repo_name)
            owner = self.repo_name.split("/")[0]
            total = len(branch_list)
            for idx, (name, dt) in enumerate(branch_list):
                try:
                    prs = repo.get_pulls(state="all", head=f"{owner}:{name}")
                    status = "no PR"
                    for pr in prs:
                        if pr.state == "open":
                            status = "open"
                            break
                        if pr.merged:
                            status = "merged"
                            break
                        status = "closed"
                        break
                except GithubException:
                    status = "error"
                progress = ((idx + 1) / total) * 100 if total else 100

                def add(p=progress, n=name, d=dt, s=status):
                    self.add_branch(n, d, s)
                    self.set_progress(p)

                self.after(0, add)

            self.after(0, lambda: (self.set_progress(100), self.set_status("Ready")))

        self.master.run_async(worker)

    def add_branch(self, name, dt, status):
        self.branches.append((name, dt))
        self.branch_statuses[name] = status
        self.branches.sort(key=lambda x: x[1], reverse=True)
        self.apply_filters()

    def apply_filters(self):
        name_f = self.name_filter.get().lower()
        date_f = self.date_filter.get().strip()
        try:
            date_after = (
                datetime.datetime.fromisoformat(date_f) if date_f else None
            )
        except ValueError:
            date_after = None
        self.tree.delete(*self.tree.get_children())
        for name, dt in self.branches:
            if name_f and name_f not in name.lower():
                continue
            if date_after and dt < date_after:
                continue
            var = self.branch_vars.get(name)
            if var is None:
                var = tk.BooleanVar()
                self.branch_vars[name] = var
            symbol = "☑" if var.get() else "☐"
            date_str = dt.strftime("%Y-%m-%d")
            status = self.branch_statuses.get(name, "")
            self.tree.insert("", "end", iid=name, values=(symbol, name, date_str, status))

    def check_selected(self):
        for iid in self.tree.selection():
            var = self.branch_vars.get(iid)
            if var:
                var.set(True)
                self.tree.set(iid, "selected", "☑")

    def uncheck_selected(self):
        for iid in self.tree.selection():
            var = self.branch_vars.get(iid)
            if var:
                var.set(False)
                self.tree.set(iid, "selected", "☐")

    def delete_checked(self):
        confirm = messagebox.askyesno("Confirm", "Delete checked branches?")
        if not confirm:
            return
        self.set_status("Deleting branches...")
        g = Github(self.token, per_page=100)
        repo = g.get_repo(self.repo_name)
        to_delete = [name for name, var in self.branch_vars.items() if var.get()]
        for name in to_delete:
            try:
                ref = repo.get_git_ref(f"heads/{name}")
                ref.delete()
                self.branch_vars.pop(name, None)
                cached = branch_cache.get(self.repo_name)
                if cached:
                    branch_cache[self.repo_name] = [
                        item for item in cached if item[0] != name
                    ]
            except GithubException as e:
                messagebox.showerror("Error", f"Failed to delete {name}: {e.data}")
        save_branch_cache(branch_cache)
        self.load_branches()
        self.set_status("Ready")


class PullRequestList(tk.Toplevel):
    def __init__(self, master, token, repo_name):
        super().__init__(master)
        self.title("Pull Request List")
        self.geometry("500x400")
        self.token = token
        self.repo_name = repo_name
        self.create_widgets()
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")
        self.minsize(self.winfo_width(), self.winfo_height())
        self.load_prs()

    def create_widgets(self):
        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(
            frm,
            columns=("number", "title", "state"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("number", text="Number")
        self.tree.heading("title", text="Title")
        self.tree.heading("state", text="State")
        self.tree.column("number", width=80, anchor="center")
        self.tree.column("title", width=280)
        self.tree.column("state", width=100, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scroll = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scroll.set)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Refresh", command=self.load_prs).pack(side=tk.LEFT)

    def load_prs(self):
        def worker():
            self.master.set_status("Loading PR list...")
            g = Github(self.token, per_page=100)
            repo = g.get_repo(self.repo_name)
            prs = list(repo.get_pulls(state="all", sort="created"))

            def update():
                self.tree.delete(*self.tree.get_children())
                for pr in prs:
                    self.tree.insert("", "end", values=(pr.number, pr.title, pr.state))
                self.master.set_status("Ready")

            self.master.after(0, update)

        self.master.run_async(worker)


def main():
    app = BulkMerger()
    app.mainloop()


if __name__ == "__main__":
    main()
