"""GitPilot: PyQt5 UI Implementation.

This module defines the MainWindow class, which sets up the graphical user
interface for the GitPilot application, including layouts, widgets, and signal connections.
"""
import sys
from PyQt5.QtWidgets import (QMainWindow, QApplication, QWidget,
                             QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox, # Added QMessageBox
                             QPushButton, QLineEdit, QFileDialog, QLabel, QInputDialog, QDialog,
                             QScrollArea, QComboBox) # Added QScrollArea, QComboBox (QWidget is base for QDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QTextCharFormat, QFont # Added for future use
import re
import html # For escaping HTML characters in diff output
import tempfile
import os
import stat # For chmod
from functools import partial # For connecting signals with arguments
from git_utils import GitExecutor


class BranchFromCommitDialog(QDialog):
    """Dialog to gather branch prefix and commit hash."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Versioned Branch")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Branch Prefix:"))
        self.prefix_edit = QLineEdit()
        layout.addWidget(self.prefix_edit)
        layout.addWidget(QLabel("Commit Hash:"))
        self.hash_edit = QLineEdit()
        layout.addWidget(self.hash_edit)
        create_btn = QPushButton("Utwórz gałąź")
        create_btn.clicked.connect(self.accept)
        layout.addWidget(create_btn)

    def get_values(self):
        return self.prefix_edit.text().strip(), self.hash_edit.text().strip()

class MainWindow(QMainWindow):
    """Main application window for GitPilot.

    Manages UI elements, user interactions, and communication with GitExecutor.
    """
    def __init__(self):
        """Initializes MainWindow, sets up UI elements and connections."""
        super().__init__()
        self.setWindowTitle("GitPilot")
        self.setGeometry(100, 100, 900, 700) # x, y, width, height

        self.current_repo_path = None
        self.git_executor = GitExecutor()
        self.git_executor.command_finished.connect(self._process_git_command_results) # RENAMED
        self._current_diff_staged = False
        self._is_fetching_rebase_log = False
        self._current_rebase_base_commit = None
        self._temp_rebase_files = []

        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Repository selection display
        self.repo_label = QLabel("No repository selected.")
        self.repo_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.repo_label)

        # Output terminal
        self.output_terminal = QTextEdit()
        self.output_terminal.setReadOnly(True)
        main_layout.addWidget(self.output_terminal, 1)

        # Diff view area
        self.diff_view_text_edit = QTextEdit()
        self.diff_view_text_edit.setReadOnly(True)
        self.diff_view_text_edit.setPlaceholderText("Diff output will appear here...")
        self.diff_view_text_edit.setFont(QFont("monospace"))
        main_layout.addWidget(self.diff_view_text_edit, 1)

        # Commit message area
        commit_layout = QHBoxLayout()
        self.commit_message_input = QLineEdit()
        self.commit_message_input.setPlaceholderText("Enter commit message...")
        commit_layout.addWidget(self.commit_message_input)

        self.commit_button = QPushButton("Commit")
        commit_layout.addWidget(self.commit_button)
        main_layout.addLayout(commit_layout)

        # Diff buttons layout
        diff_buttons_layout = QHBoxLayout()
        self.show_unstaged_diff_button = QPushButton("Show Unstaged Diff")
        diff_buttons_layout.addWidget(self.show_unstaged_diff_button)

        self.show_staged_diff_button = QPushButton("Show Staged Diff")
        diff_buttons_layout.addWidget(self.show_staged_diff_button)
        main_layout.addLayout(diff_buttons_layout)

        # Buttons layout (using multiple QHBoxLayouts for grouping)
        buttons_group1_layout = QHBoxLayout()
        self.select_repo_button = QPushButton("Select Repository")
        self.select_repo_button.clicked.connect(self.select_repository)
        buttons_group1_layout.addWidget(self.select_repo_button)

        self.status_button = QPushButton("Status")
        buttons_group1_layout.addWidget(self.status_button)

        self.pull_button = QPushButton("Pull")
        buttons_group1_layout.addWidget(self.pull_button)

        self.push_button = QPushButton("Push")
        buttons_group1_layout.addWidget(self.push_button)
        main_layout.addLayout(buttons_group1_layout)

        buttons_group2_layout = QHBoxLayout()
        self.add_all_button = QPushButton("Add All (git add .)")
        buttons_group2_layout.addWidget(self.add_all_button)

        self.log_button = QPushButton("Log Graph")
        buttons_group2_layout.addWidget(self.log_button)
        main_layout.addLayout(buttons_group2_layout)

        buttons_group3_layout = QHBoxLayout()
        self.branch_button = QPushButton("Branch Operations")
        buttons_group3_layout.addWidget(self.branch_button)

        self.checkout_button = QPushButton("Checkout Branch")
        buttons_group3_layout.addWidget(self.checkout_button)

        self.merge_button = QPushButton("Merge Branch")
        buttons_group3_layout.addWidget(self.merge_button)
        main_layout.addLayout(buttons_group3_layout)

        buttons_group4_layout = QHBoxLayout()
        self.versioned_branch_button = QPushButton("New Branch From Commit")
        buttons_group4_layout.addWidget(self.versioned_branch_button)

        self.interactive_rebase_button = QPushButton("Interactive Rebase")
        buttons_group4_layout.addWidget(self.interactive_rebase_button)
        main_layout.addLayout(buttons_group4_layout)

        # Remote Operations Buttons
        remote_ops_layout = QHBoxLayout()
        self.list_remotes_button = QPushButton("List Remotes")
        self.list_remotes_button.clicked.connect(self.on_list_remotes_click)

        self.add_remote_button = QPushButton("Add Remote")
        self.add_remote_button.clicked.connect(self.on_add_remote_click)

        self.remove_remote_button = QPushButton("Remove Remote")
        self.remove_remote_button.clicked.connect(self.on_remove_remote_click)

        remote_ops_layout.addWidget(self.list_remotes_button)
        remote_ops_layout.addWidget(self.add_remote_button)
        remote_ops_layout.addWidget(self.remove_remote_button)
        main_layout.addLayout(remote_ops_layout)

        # Git Flow Operations Buttons
        git_flow_layout1 = QHBoxLayout()
        self.start_feature_button = QPushButton("Start Feature")
        self.start_feature_button.clicked.connect(self.on_start_feature_click)
        self.finish_feature_button = QPushButton("Finish Feature")
        self.finish_feature_button.clicked.connect(self.on_finish_feature_click)
        self.start_release_button = QPushButton("Start Release")
        self.start_release_button.clicked.connect(self.on_start_release_click)

        git_flow_layout1.addWidget(self.start_feature_button)
        git_flow_layout1.addWidget(self.finish_feature_button)
        git_flow_layout1.addWidget(self.start_release_button)
        main_layout.addLayout(git_flow_layout1)

        git_flow_layout2 = QHBoxLayout()
        self.finish_release_button = QPushButton("Finish Release")
        self.finish_release_button.clicked.connect(self.on_finish_release_click)
        self.start_hotfix_button = QPushButton("Start Hotfix")
        # self.start_hotfix_button.clicked.connect(self.on_start_hotfix_click) # Connection later
        self.finish_hotfix_button = QPushButton("Finish Hotfix")
        # self.finish_hotfix_button.clicked.connect(self.on_finish_hotfix_click) # Connection later

        git_flow_layout2.addWidget(self.finish_release_button)
        git_flow_layout2.addWidget(self.start_hotfix_button)
        git_flow_layout2.addWidget(self.finish_hotfix_button)
        main_layout.addLayout(git_flow_layout2)

        self.resolve_conflict_button = QPushButton("Zatwierdź konflikt")
        self.resolve_conflict_button.setVisible(False)
        main_layout.addWidget(self.resolve_conflict_button)

        # Connect button signals to handler methods
        self.commit_button.clicked.connect(self.on_commit_click)
        self.status_button.clicked.connect(self.on_status_click)
        self.pull_button.clicked.connect(self.on_pull_click)
        self.push_button.clicked.connect(self.on_push_click)
        self.add_all_button.clicked.connect(self.on_add_all_click)
        self.log_button.clicked.connect(self.on_log_click)
        self.branch_button.clicked.connect(self.on_branch_click)
        self.checkout_button.clicked.connect(self.on_checkout_click)
        self.merge_button.clicked.connect(self.on_merge_click)
        self.versioned_branch_button.clicked.connect(self.create_versioned_branch_from_commit)
        self.resolve_conflict_button.clicked.connect(self.confirm_conflict_commit)

        self.show_unstaged_diff_button.clicked.connect(self.on_show_unstaged_diff_click)
        self.show_staged_diff_button.clicked.connect(self.on_show_staged_diff_click)
        self.interactive_rebase_button.clicked.connect(self.on_interactive_rebase_start_clicked)
        # Connect remote ops buttons


        self.append_output("GitPilot UI Initialized. Select a repository to begin.")

    def on_list_remotes_click(self):
        if self._check_repo_selected():
            self.append_output("\n>>> git remote -v")
            self.git_executor.execute_command(self.current_repo_path, ["remote", "-v"])

    def on_add_remote_click(self):
        if not self._check_repo_selected():
            return

        dialog = AddRemoteDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            name, url = dialog.get_values()
            if name and url:
                self.append_output(f"\n>>> git remote add {name} {url}")
                self.git_executor.execute_command(self.current_repo_path, ["remote", "add", name, url])
            else:
                self.append_output("ERROR: Remote name and URL cannot be empty.")
        else:
            self.append_output("Add remote operation cancelled.")

    def on_remove_remote_click(self):
        if not self._check_repo_selected():
            return

        self.append_output("\n>>> git remote")
        # Temporarily disconnect the generic handler and connect a specific one for listing remotes
        try:
            self.git_executor.command_finished.disconnect(self._process_git_command_results)
        except TypeError:
            self.append_output("DEBUG: _process_git_command_results was not connected or already disconnected for remove remote.")
            pass # Was not connected
        self.git_executor.command_finished.connect(self._handle_list_remotes_for_removal)
        self.git_executor.execute_command(self.current_repo_path, ["remote"])

    def _handle_list_remotes_for_removal(self, stdout_str, stderr_str, exit_code):
        # Reconnect the generic handler and disconnect this specific one
        try:
            self.git_executor.command_finished.disconnect(self._handle_list_remotes_for_removal)
        except TypeError:
            self.append_output("DEBUG: _handle_list_remotes_for_removal was not connected for remove remote result.")
        self.git_executor.command_finished.connect(self._process_git_command_results)

        if exit_code != 0 or not stdout_str.strip(): # also check for empty stdout_str
            self.append_output(f"ERROR: Could not list remotes. {stderr_str if stderr_str else 'No remotes found or error.'}")
            # If there was an error, the _process_git_command_results will log it as it's reconnected.
            # We should also ensure the original command's output (even if error) is processed once.
            # Calling it directly here might lead to double processing if an error occurred.
            # The generic handler is connected, so it will be called by the executor.
            return

        remotes = stdout_str.strip().split('\n')
        # Filter out empty lines just in case
        remotes = [r for r in remotes if r.strip()]

        if not remotes:
            self.append_output("No remotes found to remove.")
            # The generic handler will process the (empty) stdout from 'git remote'
            return

        remote_name, ok = QInputDialog.getItem(self, "Remove Remote", "Select remote to remove:", remotes, 0, False)

        if ok and remote_name:
            self.append_output(f"\n>>> git remote remove {remote_name}")
            # The _process_git_command_results is already connected to handle the output of this new command.
            self.git_executor.execute_command(self.current_repo_path, ["remote", "remove", remote_name])
        elif ok:
            self.append_output("Remove remote operation cancelled: No remote selected.")
        else:
            self.append_output("Remove remote operation cancelled.")
        # If we didn't issue a new command, the original 'git remote' output has been handled by
        # the reconnected _process_git_command_results.
        # If we did issue 'git remote remove', its output will be handled.

    def on_start_feature_click(self):
        if not self._check_repo_selected():
            return

        feature_name, ok = QInputDialog.getText(self, "Start New Feature", "Enter feature name (e.g., my-new-feature):")
        if ok and feature_name.strip():
            actual_feature_name = feature_name.strip()
            branch_name = f"feature/{actual_feature_name}"

            # Assuming 'develop' is the base branch for features.
            # Consider making this configurable in a future step.
            develop_branch = "develop"

            self.append_output(f"\nAttempting to start new feature: {branch_name} from {develop_branch}")

            commands = [
                ["checkout", develop_branch],
                ["pull"], # Pull latest changes on develop
                ["checkout", "-b", branch_name, develop_branch]
            ]

            self.run_command_sequence(
                commands,
                success_cb=lambda: self.append_output(f"Successfully created and checked out feature branch: {branch_name}"),
                failure_cb=lambda stderr, exit_code: self.append_output(f"ERROR starting feature {branch_name}: {stderr} (Code: {exit_code})")
            )
        elif ok:
            self.append_output("Feature name cannot be empty. Operation cancelled.")
        else:
            self.append_output("Start new feature operation cancelled.")

    def on_finish_feature_click(self):
        if not self._check_repo_selected():
            return

        feature_branch_name, ok = QInputDialog.getText(self, "Finish Feature", "Enter full feature branch name to finish (e.g., feature/my-new-feature):")

        if ok and feature_branch_name.strip():
            actual_feature_branch = feature_branch_name.strip()

            if not actual_feature_branch.startswith("feature/"):
                self.append_output("ERROR: Feature branch name should start with 'feature/'. Operation cancelled.")
                return

            # Assuming 'develop' is the target branch and 'origin' for push.
            develop_branch = "develop"
            remote_name = "origin"

            self.append_output(f"\nAttempting to finish feature: {actual_feature_branch} into {develop_branch}")

            commands = [
                ["checkout", develop_branch],
                ["pull", remote_name, develop_branch], # Pull latest changes on develop
                ["merge", "--no-ff", actual_feature_branch],
                ["branch", "-d", actual_feature_branch],
                ["push", remote_name, develop_branch] # Push develop branch after merge
            ]

            self.run_command_sequence(
                commands,
                success_cb=lambda: self.append_output(f"Successfully finished feature {actual_feature_branch} and merged into {develop_branch}."),
                failure_cb=lambda stderr, exit_code: self.append_output(f"ERROR finishing feature {actual_feature_branch}: {stderr} (Code: {exit_code})\n"
                                                                      "This could be due to merge conflicts or other issues. Please check Git status and resolve manually if needed.")
            )
        elif ok:
            self.append_output("Feature branch name cannot be empty. Operation cancelled.")
        else:
            self.append_output("Finish feature operation cancelled.")

    def on_start_release_click(self):
        if not self._check_repo_selected():
            return

        release_version, ok = QInputDialog.getText(self, "Start New Release", "Enter release version (e.g., 1.0.0):")
        if ok and release_version.strip():
            actual_release_version = release_version.strip()
            branch_name = f"release/{actual_release_version}"

            # Assuming 'develop' is the base branch for releases.
            develop_branch = "develop"

            self.append_output(f"\nAttempting to start new release: {branch_name} from {develop_branch}")

            commands = [
                ["checkout", develop_branch],
                ["pull"], # Pull latest changes on develop
                ["checkout", "-b", branch_name, develop_branch]
            ]

            self.run_command_sequence(
                commands,
                success_cb=lambda: self.append_output(f"Successfully created and checked out release branch: {branch_name}"),
                failure_cb=lambda stderr, exit_code: self.append_output(f"ERROR starting release {branch_name}: {stderr} (Code: {exit_code})")
            )
        elif ok:
            self.append_output("Release version cannot be empty. Operation cancelled.")
        else:
            self.append_output("Start new release operation cancelled.")

    def on_finish_release_click(self):
        if not self._check_repo_selected():
            return

        release_version, ok = QInputDialog.getText(self, "Finish Release", "Enter release version to finish (e.g., 1.0.0):")

        if ok and release_version.strip():
            actual_release_version = release_version.strip()
            release_branch_name = f"release/{actual_release_version}"
            tag_name = f"v{actual_release_version}" # Tag with a 'v' prefix

            # Assumptions for branch names and remote
            master_branch = "master" # Or "main" # TODO: Make configurable or detect
            develop_branch = "develop"
            remote_name = "origin"

            self.append_output(f"\nAttempting to finish release: {release_branch_name}")

            commands = [
                ["checkout", master_branch],
                ["pull", remote_name, master_branch],
                ["merge", "--no-ff", release_branch_name],
                ["tag", "-a", tag_name, "-m", f"Tagging version {actual_release_version}"],
                ["checkout", develop_branch],
                ["pull", remote_name, develop_branch],
                ["merge", "--no-ff", release_branch_name],
                ["branch", "-d", release_branch_name],
                # Consolidated push command:
                ["push", remote_name, master_branch, develop_branch, tag_name] # Pushing specific tag
            ]

            self.run_command_sequence(
                commands,
                success_cb=lambda: self.append_output(f"Successfully finished release {release_branch_name}.\n"
                                                      f"- Merged into {master_branch} and {develop_branch}.\n"
                                                      f"- Tagged as {tag_name}.\n"
                                                      f"- Deleted local release branch.\n"
                                                      f"- Pushed {master_branch}, {develop_branch}, and tag {tag_name} to {remote_name}."),
                failure_cb=lambda stderr, exit_code: self.append_output(
                    f"ERROR finishing release {release_branch_name}: {stderr} (Code: {exit_code})\n"
                    "This could be due to merge conflicts, tagging issues, or other problems. "
                    "Please check Git status and resolve manually if needed. "
                    "The release process might be partially complete.")
            )
        elif ok:
            self.append_output("Release version cannot be empty. Operation cancelled.")
        else:
            self.append_output("Finish release operation cancelled.")

    # RENAMED METHOD
    def _process_git_command_results(self, stdout_str: str, stderr_str: str, exit_code: int):
        """Handles the command_finished signal from GitExecutor."""
        if exit_code == 0:
            self.append_output(f"SUCCESS: Command finished with exit code {exit_code}.")
        else:
            self.append_output(f"FAILED: Command finished with exit code {exit_code}.")

        if stdout_str:
            self.append_output("--- Standard Output ---")
            self.append_output(stdout_str)
        if stderr_str:
            if exit_code == 0 and stderr_str:
                 self.append_output("--- Standard Error (Warnings/Info) ---")
            elif exit_code != 0 and stderr_str:
                 self.append_output("--- Standard Error (Primary Error Info) ---")
            elif stderr_str:
                 self.append_output("--- Standard Error ---")

            if stderr_str:
                self.append_output(stderr_str)
        self.append_output("-------------------------")

    def on_interactive_rebase_start_clicked(self):
        self.append_output("Interactive Rebase button clicked.")
        if not self._check_repo_selected():
            return

        dialog = InteractiveRebaseOptionsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            base_commit = dialog.get_base_commit()
            if base_commit:
                self._fetch_rebase_commits(base_commit)
            else:
                self.append_output("ERROR: Rebase base commit cannot be empty.")
        else:
            self.append_output("Interactive rebase cancelled.")

    def on_show_unstaged_diff_click(self):
        self._request_diff(staged=False)

    def on_show_staged_diff_click(self):
        self._request_diff(staged=True)

    def _request_diff(self, staged: bool):
        if not self._check_repo_selected():
            return
        try:
            self.git_executor.command_finished.disconnect(self._process_git_command_results) # RENAMED
        except TypeError:
            self.append_output("DEBUG: _process_git_command_results was not connected or already disconnected.")
            pass
        self.git_executor.command_finished.connect(self._handle_diff_output)
        self._current_diff_staged = staged
        cmd = ["diff"]
        if staged:
            cmd.append("--staged")
        else:
            cmd.append("HEAD")
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        self.git_executor.execute_command(self.current_repo_path, cmd)

    @staticmethod
    def _format_diff_line_to_html(line_text: str) -> str:
        escaped_line = html.escape(line_text)
        if line_text.startswith('+++') or line_text.startswith('---'):
            return escaped_line
        elif line_text.startswith('+'):
            return f'<font color="green">{escaped_line}</font>'
        elif line_text.startswith('-'):
            return f'<font color="red">{escaped_line}</font>'
        elif line_text.startswith('@@'):
            return f'<font color="cyan">{escaped_line}</font>'
        elif line_text.startswith('diff --git'):
            return f'<font color="yellow">{escaped_line}</font>'
        return escaped_line

    def _handle_diff_output(self, stdout_str, stderr_str, exit_code):
        self.append_output(f"DEBUG: _handle_diff_output called with exit code {exit_code}.")
        self.diff_view_text_edit.clear()
        if exit_code == 0:
            if stdout_str:
                for line in stdout_str.splitlines():
                    formatted_line = MainWindow._format_diff_line_to_html(line)
                    self.diff_view_text_edit.append(formatted_line)
            else:
                self.diff_view_text_edit.setPlainText("No changes detected.")
        else:
            self.diff_view_text_edit.setPlainText(f"Error generating diff (exit code: {exit_code}). Check terminal output for details.")
        if stderr_str:
            self.append_output(f"--- Diff Command Error Output ---")
            self.append_output(stderr_str)
            self.append_output(f"-----------------------------")
        try:
            self.git_executor.command_finished.disconnect(self._handle_diff_output)
        except TypeError:
            self.append_output("DEBUG: _handle_diff_output was not connected or already disconnected.")
            pass
        self.git_executor.command_finished.connect(self._process_git_command_results) # RENAMED
        self.append_output("DEBUG: Switched back to _process_git_command_results.")

    def _fetch_rebase_commits(self, base_commit: str):
        self.append_output(f"Fetching commits for rebase onto {base_commit}...")
        self._current_rebase_base_commit = base_commit
        try:
            self.git_executor.command_finished.disconnect(self._process_git_command_results) # RENAMED
        except TypeError:
            self.append_output("DEBUG: _process_git_command_results was not connected for fetching rebase commits.")
        self.git_executor.command_finished.connect(self._handle_rebase_log_output)
        self._is_fetching_rebase_log = True
        cmd = ["log", "--reverse", "--pretty=format:pick %h %s", f"{base_commit}..HEAD"]
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        self.git_executor.execute_command(self.current_repo_path, cmd)

    def _handle_rebase_log_output(self, stdout_str: str, stderr_str: str, exit_code: int):
        self.append_output("DEBUG: _handle_rebase_log_output called.")
        try:
            self.git_executor.command_finished.disconnect(self._handle_rebase_log_output)
        except TypeError:
            self.append_output("DEBUG: _handle_rebase_log_output was not connected.")
        self.git_executor.command_finished.connect(self._process_git_command_results) # RENAMED
        self._is_fetching_rebase_log = False
        if exit_code != 0 or (stderr_str and "fatal:" in stderr_str.lower()):
            error_message = f"Failed to fetch commits for rebase: {stderr_str}"
            self.append_output(f"ERROR: {error_message}")
            QMessageBox.critical(self, "Rebase Error", error_message)
            return
        if not stdout_str.strip():
            self.append_output("No commits found between the specified base and HEAD.")
            QMessageBox.information(self, "Rebase Info", "No commits to rebase.")
            return
        commits_data = []
        lines = stdout_str.strip().splitlines()
        for line_num, line in enumerate(lines):
            parts = line.split(" ", 2)
            if len(parts) == 3 and parts[0] == "pick" and parts[1] and parts[2]:
                commits_data.append({'action': parts[0], 'hash': parts[1], 'subject': parts[2]})
            else:
                self.append_output(f"WARNING: Could not parse rebase log line {line_num + 1}: '{line}'")
        if not commits_data:
            self.append_output("No valid rebase actions parsed, though log output was present.")
            QMessageBox.warning(self, "Rebase Warning", "Could not parse any valid commits for rebase.")
            return
        self.append_output(f"Successfully fetched {len(commits_data)} commits for rebase.")
        editor_dialog = RebaseTodoEditorDialog(commits_data, self)
        if editor_dialog.exec_() == QDialog.Accepted:
            modified_todo_list = editor_dialog.get_modified_todo_list()
            if self._current_rebase_base_commit:
                self._initiate_actual_rebase(modified_todo_list, self._current_rebase_base_commit)
            else:
                self.append_output("ERROR: Base commit for rebase was not set. Aborting rebase.")
                QMessageBox.critical(self, "Rebase Error", "Internal error: Base commit not found.")
        else:
            self.append_output("Interactive rebase editing cancelled.")

    def _initiate_actual_rebase(self, modified_todo_list: list, base_commit: str):
        self.append_output(f"Initiating rebase onto {base_commit} with modified TODO list.")
        todo_lines = []
        for item in modified_todo_list:
            todo_lines.append(f"{item['action']} {item['hash']} {item['subject']}")
        todo_content = "\n".join(todo_lines) + "\n"
        self._temp_rebase_files = []
        temp_todo_file_path = None
        temp_script_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix="_rebase_todo.txt", encoding='utf-8') as todo_file:
                todo_file.write(todo_content)
                temp_todo_file_path = todo_file.name
            self._temp_rebase_files.append(temp_todo_file_path)
            self.append_output(f"DEBUG: Created temp TODO file: {temp_todo_file_path}")
            editor_content = f#!/bin/sh\ncat "{temp_todo_file_path}" > "$1"\n
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix="_editor.sh", encoding='utf-8') as script_file:
                script_file.write(editor_content)
                temp_script_path = script_file.name
            self._temp_rebase_files.append(temp_script_path)
            self.append_output(f"DEBUG: Created temp editor script: {temp_script_path}")
            current_stat = os.stat(temp_script_path)
            os.chmod(temp_script_path, current_stat.st_mode | stat.S_IEXEC)
            self.append_output(f"DEBUG: Made script executable: {temp_script_path}")
            custom_env = {"GIT_SEQUENCE_EDITOR": temp_script_path}
            try:
                self.git_executor.command_finished.disconnect(self._process_git_command_results) # RENAMED
            except TypeError:
                self.append_output("DEBUG: _process_git_command_results was not connected for rebase execution.")
            self.git_executor.command_finished.connect(self._handle_interactive_rebase_result)
            cmd = ["rebase", "-i", base_commit]
            self.append_output(f"\n>>> env GIT_SEQUENCE_EDITOR='{temp_script_path}' git {' '.join(cmd)}")
            self.git_executor.execute_command(self.current_repo_path, cmd, env_vars=custom_env)
        except Exception as e:
            self.append_output(f"ERROR: Failed to set up or start interactive rebase: {e}")
            QMessageBox.critical(self, "Rebase Setup Error", f"Could not prepare for rebase: {e}")
            for f_path in self._temp_rebase_files:
                try: os.remove(f_path)
                except OSError: self.append_output(f"DEBUG: Error removing temp file {f_path} during setup error.")
            self._temp_rebase_files = []
            try:
                self.git_executor.command_finished.disconnect(self._handle_interactive_rebase_result)
            except TypeError: pass
            self.git_executor.command_finished.connect(self._process_git_command_results) # RENAMED

    def _handle_interactive_rebase_result(self, stdout_str: str, stderr_str: str, exit_code: int):
        self.append_output("DEBUG: _handle_interactive_rebase_result called.")
        if hasattr(self, '_temp_rebase_files') and self._temp_rebase_files:
            self.append_output(f"DEBUG: Cleaning up temp rebase files: {self._temp_rebase_files}")
            for f_path in self._temp_rebase_files:
                try:
                    os.remove(f_path)
                    self.append_output(f"DEBUG: Removed temp file: {f_path}")
                except OSError as e:
                    self.append_output(f"WARNING: Could not remove temporary rebase file {f_path}: {e}")
            self._temp_rebase_files = []
        try:
            self.git_executor.command_finished.disconnect(self._handle_interactive_rebase_result)
        except TypeError:
            self.append_output("DEBUG: _handle_interactive_rebase_result was not connected.")
        self.git_executor.command_finished.connect(self._process_git_command_results) # RENAMED
        self.append_output("--- Interactive Rebase Output ---")
        if stdout_str:
            self.append_output("Stdout:\n" + stdout_str)
        if stderr_str:
            self.append_output("Stderr:\n" + stderr_str)
        self.append_output(f"Exit Code: {exit_code}")
        self.append_output("---------------------------------")
        if exit_code == 0:
            QMessageBox.information(self, "Rebase Successful", "Interactive rebase completed successfully.")
        else:
            QMessageBox.warning(self, "Rebase Finished",
                                f"Rebase finished with exit code {exit_code}. Check terminal for details.\n"
                                "This might indicate conflicts, an aborted rebase, or other issues.")
        self._current_rebase_base_commit = None

# --- Dialog for Interactive Rebase Options ---
# ... (rest of the dialog classes and helper methods like select_repository, append_output, _check_repo_selected, on_status_click etc. remain unchanged from the previous full listing) ...
# ... This includes:
# InteractiveRebaseOptionsDialog
# RebaseTodoEditorDialog (and its REBASE_ACTIONS constant, _initialize_editors, _populate_commit_list_ui, _clear_scroll_layout, _redraw_commit_list, _move_commit_up, _move_commit_down methods)
# select_repository, append_output, _check_repo_selected
# on_status_click, on_pull_click, on_add_all_click, on_commit_click, on_push_click, on_log_click, on_branch_click, on_checkout_click, on_merge_click
# create_versioned_branch_from_commit, _on_list_branches_finished, _on_branch_success, _on_branch_failure, confirm_conflict_commit
# run_command_sequence, _run_next_command, _handle_seq_finished
# And the original handle_command_output which is now _process_git_command_results

    def select_repository(self):
        """Opens a dialog for the user to select a Git repository folder."""
        path = QFileDialog.getExistingDirectory(self, "Select Git Repository")
        if path:
            self.current_repo_path = path
            self.repo_label.setText(f"Current Repository: {self.current_repo_path}")
            self.append_output(f"Selected repository: {self.current_repo_path}")
        else:
            self.append_output("Repository selection cancelled.")

    def append_output(self, text):
        """Appends text to the output terminal and ensures visibility."""
        self.output_terminal.append(text)
        self.output_terminal.ensureCursorVisible()

    def _check_repo_selected(self):
        if not self.current_repo_path:
            self.append_output("ERROR: No repository selected. Please select a repository first.")
            return False
        self.append_output(f"--- Repository: {self.current_repo_path} ---")
        return True

    def on_status_click(self):
        if self._check_repo_selected():
            self.append_output("\n>>> git status")
            self.git_executor.execute_command(self.current_repo_path, ["status"])

    def on_pull_click(self):
        if self._check_repo_selected():
            self.append_output("\n>>> git pull")
            self.git_executor.execute_command(self.current_repo_path, ["pull"])

    def on_add_all_click(self):
        if self._check_repo_selected():
            self.append_output("\n>>> git add .")
            self.git_executor.execute_command(self.current_repo_path, ["add", "."])

    def on_commit_click(self):
        if self._check_repo_selected():
            commit_message = self.commit_message_input.text().strip()
            if not commit_message:
                self.append_output("ERROR: Commit message cannot be empty.")
                return
            self.append_output(f"\n>>> git commit -m \"{commit_message}\"")
            self.git_executor.execute_command(self.current_repo_path, ["commit", "-m", commit_message])
            self.commit_message_input.clear()

    def on_push_click(self):
        if self._check_repo_selected():
            self.append_output("\n>>> git push")
            self.git_executor.execute_command(self.current_repo_path, ["push"])

    def on_log_click(self):
        if self._check_repo_selected():
            self.append_output("\n>>> git log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit --all")
            self.git_executor.execute_command(self.current_repo_path, ["log", "--graph", "--pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset'", "--abbrev-commit", "--all"])

    def on_branch_click(self):
        if self._check_repo_selected():
            self.append_output("\n>>> git branch -vv")
            self.git_executor.execute_command(self.current_repo_path, ["branch", "-vv"])

    def on_checkout_click(self):
        if self._check_repo_selected():
            branch_name, ok = QInputDialog.getText(self, "Checkout Branch", "Enter branch name to checkout:")
            if ok and branch_name.strip():
                actual_branch_name = branch_name.strip()
                self.append_output(f"\n>>> git checkout {actual_branch_name}")
                self.git_executor.execute_command(self.current_repo_path, ["checkout", actual_branch_name])
            elif ok:
                 self.append_output("Checkout operation cancelled: No branch name entered.")

    def on_merge_click(self):
        if self._check_repo_selected():
            branch_name, ok = QInputDialog.getText(self, "Merge Branch", "Enter branch name to merge into current branch:")
            if ok and branch_name.strip():
                actual_branch_name = branch_name.strip()
                self.append_output(f"\n>>> git merge {actual_branch_name}")
                self.git_executor.execute_command(self.current_repo_path, ["merge", actual_branch_name])
            elif ok:
                self.append_output("Merge operation cancelled: No branch name entered.")

    def create_versioned_branch_from_commit(self):
        if not self._check_repo_selected():
            return
        dlg = BranchFromCommitDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            self.append_output("Branch creation cancelled.")
            return
        prefix, commit_hash = dlg.get_values()
        if not prefix or not commit_hash:
            self.append_output("ERROR: Both prefix and commit hash are required.")
            return
        self._pending_prefix = prefix
        self._pending_hash = commit_hash
        self.git_executor.command_finished.disconnect(self._process_git_command_results) # RENAMED
        self.git_executor.command_finished.connect(self._on_list_branches_finished)
        self.append_output(f"\n>>> git branch --list {prefix}-v*")
        self.git_executor.execute_command(self.current_repo_path, ["branch", "--list", f"{prefix}-v*"])

    def _on_list_branches_finished(self, stdout_str, stderr_str, exit_code):
        self.git_executor.command_finished.disconnect(self._on_list_branches_finished)
        self.git_executor.command_finished.connect(self._process_git_command_results) # RENAMED
        versions = []
        for line in stdout_str.splitlines():
            branch = line.strip().lstrip('*').strip()
            m = re.match(rf"{re.escape(self._pending_prefix)}-v(\d+)", branch)
            if m:
                try:
                    versions.append(int(m.group(1)))
                except ValueError:
                    pass
        next_ver = max(versions) + 1 if versions else 1
        self._new_branch_name = f"{self._pending_prefix}-v{next_ver}"
        self.append_output(f"Proposed branch name: {self._new_branch_name}")
        cmds = [
            ["checkout", "main"],
            ["pull"],
            ["checkout", "-b", self._new_branch_name],
            ["cherry-pick", self._pending_hash, "-X", "theirs"],
        ]
        self.run_command_sequence(cmds, self._on_branch_success, self._on_branch_failure)

    def _on_branch_success(self):
        self.append_output(f"Branch {self._new_branch_name} created and commit applied.")

    def _on_branch_failure(self, stderr_str, exit_code):
        self.append_output(f"Failed during branch creation: {stderr_str}")
        self.resolve_conflict_button.setVisible(True)

    def confirm_conflict_commit(self):
        if not self._check_repo_selected():
            return
        cmds = [["add", "."], ["commit", "-m", "Manual conflict resolution"]]
        self.run_command_sequence(cmds, lambda: self.resolve_conflict_button.setVisible(False))

    def run_command_sequence(self, commands, success_cb=None, failure_cb=None):
        self._command_queue = list(commands)
        self._seq_success_cb = success_cb
        self._seq_failure_cb = failure_cb
        self._run_next_command()

    def _run_next_command(self):
        if not self._command_queue:
            if self._seq_success_cb:
                self._seq_success_cb()
            return
        cmd = self._command_queue.pop(0)
        self._current_seq_cmd = cmd
        # Temporarily disconnect the main handler for sequential commands
        try:
            self.git_executor.command_finished.disconnect(self._process_git_command_results) # RENAMED
        except TypeError: # Might not be connected if previous command was also part of sequence
            pass
        self.git_executor.command_finished.connect(self._handle_seq_finished)
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        self.git_executor.execute_command(self.current_repo_path, cmd)

    def _handle_seq_finished(self, stdout_str, stderr_str, exit_code):
        # Disconnect self first
        self.git_executor.command_finished.disconnect(self._handle_seq_finished)
        # Call the main handler to display output for this specific command in sequence
        self._process_git_command_results(stdout_str, stderr_str, exit_code) # RENAMED

        if exit_code != 0:
            if self._seq_failure_cb:
                self._seq_failure_cb(stderr_str, exit_code)
            self._command_queue = [] # Clear queue on failure
             # Reconnect the main handler after sequence failure or completion
            self.git_executor.command_finished.connect(self._process_git_command_results) # RENAMED
            return

        if not self._command_queue: # If that was the last command
             # Reconnect the main handler
            self.git_executor.command_finished.connect(self._process_git_command_results) # RENAMED

        self._run_next_command() # Run next command or call success_cb


# --- Dialog for Interactive Rebase Options ---
# (Content of InteractiveRebaseOptionsDialog remains here)
# ...
# --- Dialog for Editing Rebase TODO List ---
# (Content of RebaseTodoEditorDialog remains here, including REBASE_ACTIONS)
# ...

# (The actual dialog class definitions are here in the real file)
# I'm omitting them for brevity in this overwrite block, assuming they are correct from previous steps.
# If they also need restoration, they'd be included in full.

class AddRemoteDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Remote")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Remote Name:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Remote URL:"))
        self.url_edit = QLineEdit()
        layout.addWidget(self.url_edit)

        buttons_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addStretch()
        buttons_layout.addWidget(ok_button)
        buttons_layout.addWidget(cancel_button)
        layout.addLayout(buttons_layout)

    def get_values(self):
        return self.name_edit.text().strip(), self.url_edit.text().strip()

class InteractiveRebaseOptionsDialog(QDialog):
    """Dialog to get the base for an interactive rebase."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Interactive Rebase Options")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        label = QLabel("Rebase onto (e.g., HEAD~N, commit hash, branch name):")
        layout.addWidget(label)

        self.base_commit_input = QLineEdit()
        self.base_commit_input.setPlaceholderText("Enter base commit/branch")
        layout.addWidget(self.base_commit_input)

        button_layout = QHBoxLayout()
        start_button = QPushButton("Start")
        start_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(start_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def get_base_commit(self) -> str:
        return self.base_commit_input.text().strip()

REBASE_ACTIONS = ["pick", "reword", "edit", "squash", "fixup", "drop"]
class RebaseTodoEditorDialog(QDialog):
    def __init__(self, commits_data: list, parent=None):
        super().__init__(parent)
        self.original_commits_data = list(commits_data)
        self._initialize_editors()
        self.setWindowTitle("Edit Rebase TODO List")
        self.setMinimumSize(700, 450)
        main_layout = QVBoxLayout(self)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_content_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_content_layout.setSpacing(6)
        self._populate_commit_list_ui()
        self.scroll_widget.setLayout(self.scroll_content_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        main_layout.addWidget(self.scroll_area)
        button_layout = QHBoxLayout()
        proceed_button = QPushButton("Proceed")
        proceed_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(proceed_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def get_modified_todo_list(self) -> list:
        modified_list = []
        for i, editor_widgets in enumerate(self.commit_editors):
            original_commit_hash = self.original_commits_data[i]['hash']
            new_action = editor_widgets['action_combo'].currentText()
            new_subject = editor_widgets['subject_edit'].text()
            modified_list.append({
                'action': new_action,
                'hash': original_commit_hash,
                'subject': new_subject
            })
        return modified_list

    def _clear_scroll_layout(self):
        while self.scroll_content_layout.count():
            child = self.scroll_content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                while child.layout().count():
                    sub_child = child.layout().takeAt(0)
                    if sub_child.widget():
                        sub_child.widget().deleteLater()
                child.layout().deleteLater()

    def _populate_commit_list_ui(self):
        for i, editor_group in enumerate(self.commit_editors):
            row_layout = QHBoxLayout()
            move_buttons_layout = QVBoxLayout()
            up_button = QPushButton("↑")
            up_button.setFixedWidth(30)
            up_button.clicked.connect(partial(self._move_commit_up, i))
            down_button = QPushButton("↓")
            down_button.setFixedWidth(30)
            down_button.clicked.connect(partial(self._move_commit_down, i))
            move_buttons_layout.addWidget(up_button)
            move_buttons_layout.addWidget(down_button)
            row_layout.addLayout(move_buttons_layout)
            row_layout.addWidget(editor_group['action_combo'], 1)
            row_layout.addWidget(editor_group['hash_label'], 1)
            row_layout.addWidget(editor_group['subject_edit'], 7)
            self.scroll_content_layout.addLayout(row_layout)
            up_button.setEnabled(i > 0)
            down_button.setEnabled(i < len(self.commit_editors) - 1)
        self.scroll_content_layout.addStretch()

    def _redraw_commit_list(self):
        self._clear_scroll_layout()
        if self.scroll_content_layout.count() > 0 and self.scroll_content_layout.itemAt(self.scroll_content_layout.count() -1).spacerItem():
             self.scroll_content_layout.takeAt(self.scroll_content_layout.count() -1)
        self._populate_commit_list_ui()

    def _initialize_editors(self):
        self.commit_editors = []
        for commit_info in self.original_commits_data:
            action = commit_info['action']
            commit_hash = commit_info['hash']
            subject = commit_info['subject']
            action_combo = QComboBox()
            action_combo.addItems(REBASE_ACTIONS)
            if action in REBASE_ACTIONS:
                action_combo.setCurrentText(action)
            else:
                action_combo.setCurrentText("pick")
            action_combo.setMinimumWidth(80)
            hash_label = QLabel(commit_hash)
            hash_label.setMinimumWidth(70)
            hash_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            subject_edit = QLineEdit(subject)
            self.commit_editors.append({
                'action_combo': action_combo,
                'hash_label': hash_label,
                'subject_edit': subject_edit
            })

    def _move_commit_up(self, index: int):
        if index == 0: return
        self.original_commits_data.insert(index - 1, self.original_commits_data.pop(index))
        self.commit_editors.insert(index - 1, self.commit_editors.pop(index))
        self._redraw_commit_list()

    def _move_commit_down(self, index: int):
        if index >= len(self.original_commits_data) - 1: return
        self.original_commits_data.insert(index + 1, self.original_commits_data.pop(index))
        self.commit_editors.insert(index + 1, self.commit_editors.pop(index))
        self._redraw_commit_list()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
