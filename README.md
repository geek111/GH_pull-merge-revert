# GitHub Bulk Merger

This repository contains a small GUI tool written in Python that allows you to
select multiple pull requests from a repository and merge them in bulk or revert
previous merges.
If a merge conflict occurs, the tool attempts a naive resolution by preferring
changes from the pull request branch.

## Requirements

- Python 3.8+
- Packages listed in `requirements.txt`

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Running

```bash
python app.py
```

After providing your GitHub token click **Load Repos** to fetch repositories
available to the token. Choose one from the drop-down and use **Load PRs** to
fetch open pull requests. You can load previously merged pull requests with
**Load Merged PRs**. Select the ones you want
to merge or revert, then click **Merge Selected** or **Revert Selected**.

### Branch Manager

Use **Manage Branches** to open a window listing repository branches. You can
filter by name or date and toggle check marks for the highlighted branches using
the right mouse button.

The script attempts to merge using the GitHub API and falls back to a local
`git` merge with a simple conflict strategy if necessary.

## Building an executable

To create a Windows `.exe`, you can use [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile app.py
```

The resulting executable will be placed in the `dist` folder.
