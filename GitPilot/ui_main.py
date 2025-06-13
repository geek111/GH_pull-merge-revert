"""GitPilot: PyQt5 UI Implementation.

This module defines the MainWindow class, which sets up the graphical user
interface for the GitPilot application, including layouts, widgets, and signal connections.
"""
import sys
from PyQt5.QtWidgets import (QMainWindow, QApplication, QWidget,
                             QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox, # Added QMessageBox
                             QPushButton, QLineEdit, QFileDialog, QLabel, QInputDialog, QDialog,
                             QScrollArea, QComboBox, QCheckBox, QListWidget, QListWidgetItem, QFormLayout,
                             QGroupBox, QRadioButton) # Added QGroupBox, QRadioButton
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
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self._current_diff_staged = False
        self._is_fetching_rebase_log = False
        self._current_rebase_base_commit = None
        self._temp_rebase_files = []
        self._stash_action_context = None
        self._is_processing_stash_list = False
        self._tag_action_context = None
        self._is_processing_tag_list = False

        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.repo_label = QLabel("No repository selected.")
        self.repo_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.repo_label)

        self.output_terminal = QTextEdit()
        self.output_terminal.setReadOnly(True)
        main_layout.addWidget(self.output_terminal, 1)

        self.diff_view_text_edit = QTextEdit()
        self.diff_view_text_edit.setReadOnly(True)
        self.diff_view_text_edit.setPlaceholderText("Diff output will appear here...")
        self.diff_view_text_edit.setFont(QFont("monospace"))
        main_layout.addWidget(self.diff_view_text_edit, 1)

        commit_layout = QHBoxLayout()
        self.commit_message_input = QLineEdit()
        self.commit_message_input.setPlaceholderText("Enter commit message...")
        commit_layout.addWidget(self.commit_message_input)
        self.commit_button = QPushButton("Commit")
        commit_layout.addWidget(self.commit_button)
        main_layout.addLayout(commit_layout)

        diff_buttons_layout = QHBoxLayout()
        self.show_unstaged_diff_button = QPushButton("Show Unstaged Diff")
        diff_buttons_layout.addWidget(self.show_unstaged_diff_button)
        self.show_staged_diff_button = QPushButton("Show Staged Diff")
        diff_buttons_layout.addWidget(self.show_staged_diff_button)
        main_layout.addLayout(diff_buttons_layout)

        stash_buttons_layout = QHBoxLayout()
        self.stash_changes_button = QPushButton("Stash Changes")
        stash_buttons_layout.addWidget(self.stash_changes_button)
        self.apply_stash_button = QPushButton("Apply Stash")
        stash_buttons_layout.addWidget(self.apply_stash_button)
        self.list_stashes_button = QPushButton("List Stashes")
        stash_buttons_layout.addWidget(self.list_stashes_button)
        self.drop_stash_button = QPushButton("Drop Stash")
        stash_buttons_layout.addWidget(self.drop_stash_button)
        main_layout.addLayout(stash_buttons_layout)

        tag_buttons_layout = QHBoxLayout()
        self.create_tag_button = QPushButton("Create Tag")
        tag_buttons_layout.addWidget(self.create_tag_button)
        self.list_tags_button = QPushButton("List Tags")
        tag_buttons_layout.addWidget(self.list_tags_button)
        self.push_tags_button = QPushButton("Push Tag(s)")
        tag_buttons_layout.addWidget(self.push_tags_button)
        self.delete_tag_button = QPushButton("Delete Tag")
        tag_buttons_layout.addWidget(self.delete_tag_button)
        main_layout.addLayout(tag_buttons_layout)

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

        self.resolve_conflict_button = QPushButton("Zatwierdź konflikt")
        self.resolve_conflict_button.setVisible(False)
        main_layout.addWidget(self.resolve_conflict_button)

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
        self.stash_changes_button.clicked.connect(self.on_stash_changes_clicked)
        self.apply_stash_button.clicked.connect(self.on_apply_stash_clicked)
        self.list_stashes_button.clicked.connect(self.on_list_stashes_clicked)
        self.drop_stash_button.clicked.connect(self.on_drop_stash_clicked)
        self.create_tag_button.clicked.connect(self.on_create_tag_clicked)
        self.list_tags_button.clicked.connect(self.on_list_tags_clicked)
        self.push_tags_button.clicked.connect(self.on_push_tags_clicked)
        self.delete_tag_button.clicked.connect(self.on_delete_tag_clicked)

        self.append_output("GitPilot UI Initialized. Select a repository to begin.")

    def _process_git_command_results(self, stdout_str: str, stderr_str: str, exit_code: int):
        if exit_code == 0: self.append_output(f"SUCCESS: Command finished with exit code {exit_code}.")
        else: self.append_output(f"FAILED: Command finished with exit code {exit_code}.")
        if stdout_str: self.append_output("--- Standard Output ---\n" + stdout_str)
        if stderr_str:
            if exit_code == 0: self.append_output("--- Standard Error (Warnings/Info) ---\n" + stderr_str)
            else: self.append_output("--- Standard Error (Primary Error Info) ---\n" + stderr_str)
        self.append_output("-------------------------")

    def on_interactive_rebase_start_clicked(self):
        self.append_output("Interactive Rebase button clicked.")
        if not self._check_repo_selected(): return
        dialog = InteractiveRebaseOptionsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            base_commit = dialog.get_base_commit()
            if base_commit: self._fetch_rebase_commits(base_commit)
            else: self.append_output("ERROR: Rebase base commit cannot be empty.")
        else: self.append_output("Interactive rebase cancelled.")

    def on_show_unstaged_diff_click(self): self._request_diff(staged=False)
    def on_show_staged_diff_click(self): self._request_diff(staged=True)

    def _request_diff(self, staged: bool):
        if not self._check_repo_selected(): return
        try: self.git_executor.command_finished.disconnect(self._process_git_command_results)
        except TypeError: self.append_output("DEBUG: _process_git_command_results was not connected or already disconnected for diff.")
        self.git_executor.command_finished.connect(self._handle_diff_output)
        self._current_diff_staged = staged
        cmd = ["diff"]
        if staged: cmd.append("--staged")
        else: cmd.append("HEAD")
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        self.git_executor.execute_command(self.current_repo_path, cmd)

    @staticmethod
    def _format_diff_line_to_html(line_text: str) -> str:
        escaped_line = html.escape(line_text)
        if line_text.startswith('+++') or line_text.startswith('---'): return escaped_line
        elif line_text.startswith('+'): return f'<font color="green">{escaped_line}</font>'
        elif line_text.startswith('-'): return f'<font color="red">{escaped_line}</font>'
        elif line_text.startswith('@@'): return f'<font color="cyan">{escaped_line}</font>'
        elif line_text.startswith('diff --git'): return f'<font color="yellow">{escaped_line}</font>'
        return escaped_line

    def _handle_diff_output(self, stdout_str, stderr_str, exit_code):
        self.append_output(f"DEBUG: _handle_diff_output called with exit code {exit_code}.")
        self.diff_view_text_edit.clear()
        if exit_code == 0:
            if stdout_str:
                for line in stdout_str.splitlines(): self.diff_view_text_edit.append(MainWindow._format_diff_line_to_html(line))
            else: self.diff_view_text_edit.setPlainText("No changes detected.")
        else: self.diff_view_text_edit.setPlainText(f"Error generating diff (exit code: {exit_code}). Check terminal output for details.")
        if stderr_str:
            self.append_output(f"--- Diff Command Error Output ---\n{stderr_str}\n-----------------------------")
        try: self.git_executor.command_finished.disconnect(self._handle_diff_output)
        except TypeError: self.append_output("DEBUG: _handle_diff_output was not connected or already disconnected.")
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self.append_output("DEBUG: Switched back to _process_git_command_results from diff.")

    def _fetch_rebase_commits(self, base_commit: str):
        self.append_output(f"Fetching commits for rebase onto {base_commit}...")
        self._current_rebase_base_commit = base_commit
        try: self.git_executor.command_finished.disconnect(self._process_git_command_results)
        except TypeError: self.append_output("DEBUG: _process_git_command_results was not connected for fetching rebase commits.")
        self.git_executor.command_finished.connect(self._handle_rebase_log_output)
        self._is_fetching_rebase_log = True
        cmd = ["log", "--reverse", "--pretty=format:pick %h %s", f"{base_commit}..HEAD"]
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        self.git_executor.execute_command(self.current_repo_path, cmd)

    def _handle_rebase_log_output(self, stdout_str: str, stderr_str: str, exit_code: int):
        self.append_output("DEBUG: _handle_rebase_log_output called.")
        try: self.git_executor.command_finished.disconnect(self._handle_rebase_log_output)
        except TypeError: self.append_output("DEBUG: _handle_rebase_log_output was not connected.")
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self._is_fetching_rebase_log = False
        if exit_code != 0 or (stderr_str and "fatal:" in stderr_str.lower()):
            error_message = f"Failed to fetch commits for rebase: {stderr_str}"
            self.append_output(f"ERROR: {error_message}")
            QMessageBox.critical(self, "Rebase Error", error_message)
            self._stash_action_context = None
            return
        if not stdout_str.strip():
            self.append_output("No commits found between the specified base and HEAD.")
            QMessageBox.information(self, "Rebase Info", "No commits to rebase.")
            self._stash_action_context = None
            return
        commits_data = []
        for line_num, line in enumerate(stdout_str.strip().splitlines()):
            parts = line.split(" ", 2)
            if len(parts) == 3 and parts[0] == "pick" and parts[1] and parts[2]:
                commits_data.append({'action': parts[0], 'hash': parts[1], 'subject': parts[2]})
            else: self.append_output(f"WARNING: Could not parse rebase log line {line_num + 1}: '{line}'")
        if not commits_data:
            self.append_output("No valid rebase actions parsed, though log output was present.")
            QMessageBox.warning(self, "Rebase Warning", "Could not parse any valid commits for rebase.")
            self._stash_action_context = None
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
        else: self.append_output("Interactive rebase editing cancelled.")
        self._stash_action_context = None

    def _initiate_actual_rebase(self, modified_todo_list: list, base_commit: str):
        self.append_output(f"Initiating rebase onto {base_commit} with modified TODO list.")
        todo_content = "\n".join([f"{item['action']} {item['hash']} {item['subject']}" for item in modified_todo_list]) + "\n"
        self._temp_rebase_files = []
        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix="_rebase_todo.txt", encoding='utf-8') as todo_file:
                todo_file.write(todo_content)
                temp_todo_file_path = todo_file.name
            self._temp_rebase_files.append(temp_todo_file_path)
            editor_content = f#!/bin/sh\ncat "{temp_todo_file_path}" > "$1"\n
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix="_editor.sh", encoding='utf-8') as script_file:
                script_file.write(editor_content)
                temp_script_path = script_file.name
            self._temp_rebase_files.append(temp_script_path)
            os.chmod(temp_script_path, os.stat(temp_script_path).st_mode | stat.S_IEXEC)
            custom_env = {"GIT_SEQUENCE_EDITOR": temp_script_path}
            try: self.git_executor.command_finished.disconnect(self._process_git_command_results)
            except TypeError: self.append_output("DEBUG: _process_git_command_results was not connected for rebase execution.")
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
            try: self.git_executor.command_finished.disconnect(self._handle_interactive_rebase_result)
            except TypeError: pass
            self.git_executor.command_finished.connect(self._process_git_command_results)

    def _handle_interactive_rebase_result(self, stdout_str: str, stderr_str: str, exit_code: int):
        self.append_output("DEBUG: _handle_interactive_rebase_result called.")
        if hasattr(self, '_temp_rebase_files') and self._temp_rebase_files:
            for f_path in self._temp_rebase_files:
                try: os.remove(f_path)
                except OSError as e: self.append_output(f"WARNING: Could not remove temporary rebase file {f_path}: {e}")
            self._temp_rebase_files = []
        try: self.git_executor.command_finished.disconnect(self._handle_interactive_rebase_result)
        except TypeError: self.append_output("DEBUG: _handle_interactive_rebase_result was not connected.")
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self.append_output(f"--- Interactive Rebase Output ---\nStdout:\n{stdout_str}\nStderr:\n{stderr_str}\nExit Code: {exit_code}\n---------------------------------")
        if exit_code == 0: QMessageBox.information(self, "Rebase Successful", "Interactive rebase completed successfully.")
        else: QMessageBox.warning(self, "Rebase Finished", f"Rebase finished with exit code {exit_code}. Check terminal for details.\nThis might indicate conflicts, an aborted rebase, or other issues.")
        self._current_rebase_base_commit = None

    def on_stash_changes_clicked(self):
        self.append_output("Stash Changes button clicked.")
        if not self._check_repo_selected(): return
        dialog = StashCreateDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            options = dialog.get_stash_options()
            self._execute_stash_create(options['message'], options['keep_index'], options['include_untracked'])
        else: self.append_output("Stash creation cancelled.")

    def on_apply_stash_clicked(self):
        self.append_output("Apply Stash button clicked.")
        if not self._check_repo_selected(): return
        self._fetch_stash_list_data("apply")

    def on_list_stashes_clicked(self):
        self.append_output("List Stashes button clicked.")
        if not self._check_repo_selected(): return
        self._fetch_stash_list_data("list_only")

    def on_drop_stash_clicked(self):
        self.append_output("Drop Stash button clicked.")
        if not self._check_repo_selected(): return
        self._fetch_stash_list_data("drop")

    def _execute_stash_create(self, message: str, keep_index: bool, include_untracked: bool):
        self.append_output(f"DEBUG: Preparing to execute stash create: msg='{message}', keep_index={keep_index}, untracked={include_untracked}")
        cmd = ["stash", "push"]
        if keep_index: cmd.append("--keep-index")
        if include_untracked: cmd.append("--include-untracked")
        if message: cmd.extend(["-m", message])
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        try: self.git_executor.command_finished.disconnect(self._handle_diff_output)
        except TypeError: pass
        try: self.git_executor.command_finished.disconnect(self._handle_rebase_log_output)
        except TypeError: pass
        try: self.git_executor.command_finished.disconnect(self._handle_interactive_rebase_result)
        except TypeError: pass
        try: self.git_executor.command_finished.disconnect(self._handle_seq_finished)
        except TypeError: pass
        try: self.git_executor.command_finished.disconnect(self._handle_stash_list_result)
        except TypeError: pass
        try: self.git_executor.command_finished.disconnect(self._process_git_command_results)
        except TypeError: pass
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self.git_executor.execute_command(self.current_repo_path, cmd)
        self.append_output("Stash command executed. See output above for results.")

    def _fetch_stash_list_data(self, action_context: str):
        self.append_output(f"Fetching stash list for context: {action_context}...")
        if not self._check_repo_selected(): return
        self._stash_action_context = action_context
        self._is_processing_stash_list = True
        try: self.git_executor.command_finished.disconnect(self._process_git_command_results)
        except TypeError: pass
        try: self.git_executor.command_finished.disconnect(self._handle_diff_output)
        except TypeError: pass
        try: self.git_executor.command_finished.disconnect(self._handle_rebase_log_output)
        except TypeError: pass
        try: self.git_executor.command_finished.disconnect(self._handle_interactive_rebase_result)
        except TypeError: pass
        try: self.git_executor.command_finished.disconnect(self._handle_seq_finished)
        except TypeError: pass
        try: self.git_executor.command_finished.disconnect(self._handle_stash_list_result)
        except TypeError: pass
        self.git_executor.command_finished.connect(self._handle_stash_list_result)
        cmd = ["stash", "list"]
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        self.git_executor.execute_command(self.current_repo_path, cmd)

    def _handle_stash_list_result(self, stdout_str: str, stderr_str: str, exit_code: int):
        self.append_output("DEBUG: _handle_stash_list_result called.")
        try: self.git_executor.command_finished.disconnect(self._handle_stash_list_result)
        except TypeError: self.append_output("DEBUG: _handle_stash_list_result was not connected.")
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self._is_processing_stash_list = False
        if exit_code != 0:
            err_msg = f"Error listing stashes: {stderr_str}"
            self.append_output(err_msg)
            QMessageBox.critical(self, "Error", f"Failed to list stashes:\n{stderr_str}")
            self._stash_action_context = None
            return
        if not stdout_str.strip():
            self.append_output("No stashes found.")
            QMessageBox.information(self, "No Stashes", "No stashes found in the repository.")
            self._stash_action_context = None
            return
        parsed_stashes = []
        lines = stdout_str.strip().splitlines()
        for line in lines:
            match = re.match(r'(stash@\{\d+\}):\s*(.*)', line)
            if match: parsed_stashes.append({'id': match.group(1), 'description': match.group(2)})
            else: self.append_output(f"WARNING: Could not parse stash line: '{line}'")
        if not parsed_stashes:
            self.append_output("Could not parse stash list output, though output was present.")
            QMessageBox.warning(self, "Parsing Error", "Could not parse stash list output.")
            self._stash_action_context = None
            return
        dialog = StashListDialog(parsed_stashes, self._stash_action_context, self)
        if dialog.exec_() == QDialog.Accepted:
            selected_id = dialog.get_selected_stash_id()
            if selected_id:
                if self._stash_action_context == "apply":
                    apply_options = dialog.get_apply_options()
                    self._execute_stash_apply(selected_id, apply_options['pop'], apply_options['reinstate_index'])
                elif self._stash_action_context == "drop":
                    self._execute_stash_drop(selected_id)
                elif self._stash_action_context == "list_only":
                    self.append_output(f"Stash selected for viewing: {selected_id}")
            else: self.append_output("No stash selected from dialog.")
        else: self.append_output(f"Stash {self._stash_action_context} dialog cancelled.")
        self._stash_action_context = None

    def _execute_stash_apply(self, stash_id: str, pop_stash: bool, reinstate_index: bool):
        cmd = ["stash"]
        if pop_stash: cmd.append("pop")
        else: cmd.append("apply")
        if reinstate_index: cmd.append("--index")
        cmd.append(stash_id)
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        try: self.git_executor.command_finished.disconnect(self._process_git_command_results)
        except TypeError: pass
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self.git_executor.execute_command(self.current_repo_path, cmd)
        self.append_output(f"Stash {'pop' if pop_stash else 'apply'} command executed for {stash_id}.")

    def _execute_stash_drop(self, stash_id: str):
        cmd = ["stash", "drop", stash_id]
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        try: self.git_executor.command_finished.disconnect(self._process_git_command_results)
        except TypeError: pass
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self.git_executor.execute_command(self.current_repo_path, cmd)
        self.append_output(f"Drop stash command executed for {stash_id}. See output above for results.")

    def on_create_tag_clicked(self):
        self.append_output("Create Tag button clicked.")
        if not self._check_repo_selected(): return
        dialog = TagCreateDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            options = dialog.get_tag_options()
            if not options['name']:
                QMessageBox.warning(self, "Input Error", "Tag name cannot be empty.")
                return
            self._execute_tag_create(options)
        else:
            self.append_output("Tag creation cancelled.")

    def on_list_tags_clicked(self):
        self.append_output("List Tags button clicked.")
        if not self._check_repo_selected(): return
        self._fetch_tag_list_data("list_only")

    def on_push_tags_clicked(self):
        self.append_output("Push Tag(s) button clicked.")
        if not self._check_repo_selected(): return
        dialog = TagPushDialog(self) # NEW DIALOG
        if dialog.exec_() == QDialog.Accepted:
            options = dialog.get_push_options()
            if not options['remote_name']:
                QMessageBox.warning(self, "Input Error", "Remote name cannot be empty.")
                return
            if not options['push_all'] and not options['specific_tag_name']:
                QMessageBox.warning(self, "Input Error", "Please specify a tag name to push, or select 'Push all tags'.")
                return
            self._execute_tag_push(options)
        else:
            self.append_output("Push tags dialog cancelled.")

    def on_delete_tag_clicked(self):
        self.append_output("Delete Tag button clicked.")
        if not self._check_repo_selected(): return
        self._fetch_tag_list_data("delete")

    def _execute_tag_create(self, options: dict):
        tag_name = options['name']
        is_annotated = options['annotated']
        message = options['message']
        commit_hash = options['commit_hash']
        force_create = options['force']
        cmd = ["tag"]
        if is_annotated:
            cmd.append("-a")
            cmd.extend(["-m", message if message else ""])
        if force_create:
            cmd.append("-f")
        cmd.append(tag_name)
        if commit_hash:
            cmd.append(commit_hash)
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        try: self.git_executor.command_finished.disconnect()
        except TypeError: pass
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self.git_executor.execute_command(self.current_repo_path, cmd)
        self.append_output("Create tag command executed. See output above for results.")

    def _fetch_tag_list_data(self, action_context: str):
        self.append_output(f"Fetching tag list for context: {action_context}...")
        if not self._check_repo_selected(): return
        self._tag_action_context = action_context
        self._is_processing_tag_list = True
        try: self.git_executor.command_finished.disconnect()
        except TypeError: pass
        self.git_executor.command_finished.connect(self._handle_tag_list_result)
        cmd = ["tag", "-l"]
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        self.git_executor.execute_command(self.current_repo_path, cmd)

    def _handle_tag_list_result(self, stdout_str: str, stderr_str: str, exit_code: int):
        self.append_output("DEBUG: _handle_tag_list_result called.")
        try: self.git_executor.command_finished.disconnect(self._handle_tag_list_result)
        except TypeError: self.append_output("DEBUG: _handle_tag_list_result was not connected.")
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self._is_processing_tag_list = False
        if exit_code != 0:
            err_msg = f"Error listing tags: {stderr_str}"
            self.append_output(err_msg)
            QMessageBox.critical(self, "Error", f"Failed to list tags:\n{stderr_str}")
            self._tag_action_context = None
            return
        if not stdout_str.strip():
            self.append_output("No tags found.")
            QMessageBox.information(self, "No Tags", "No tags found in the repository.")
            self._tag_action_context = None
            return
        tag_names = stdout_str.strip().splitlines()
        parsed_tags = [{'name': name} for name in tag_names if name]
        if not parsed_tags:
            self.append_output("Could not parse tag list output, though output was present.")
            QMessageBox.warning(self, "Parsing Error", "Could not parse tag list output.")
            self._tag_action_context = None
            return
        dialog = TagListDialog(parsed_tags, self._tag_action_context, self)
        if dialog.exec_() == QDialog.Accepted:
            selected_tag_name = dialog.get_selected_tag_name()
            if selected_tag_name:
                if self._tag_action_context == "list_only":
                    self.append_output(f"Tag selected for viewing: {selected_tag_name}. (Further action not yet implemented here).")
                elif self._tag_action_context == "delete":
                    self._prompt_for_delete_options(selected_tag_name)
                # Add other contexts like "push_single" later
            else: self.append_output("No tag selected from dialog.")
        else: self.append_output(f"Tag {self._tag_action_context} dialog cancelled.")
        self._tag_action_context = None

    def _prompt_for_delete_options(self, tag_name: str):
        dialog = TagDeleteOptionsDialog(tag_name, self)
        if dialog.exec_() == QDialog.Accepted:
            options = dialog.get_delete_options()
            if options['delete_remote'] and not options['remote_name']:
                QMessageBox.warning(self, "Input Error", "Remote name cannot be empty if deleting from remote.")
                return
            self._execute_tag_delete(tag_name, options['delete_remote'], options['remote_name'])
        else:
            self.append_output(f"Deletion of tag '{tag_name}' cancelled.")

    def _execute_tag_delete(self, tag_name: str, delete_remote: bool, remote_name: str):
        cmd_local = ["tag", "-d", tag_name]
        self.append_output(f"\n>>> git {' '.join(cmd_local)}")
        try: self.git_executor.command_finished.disconnect()
        except TypeError: pass
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self.git_executor.execute_command(self.current_repo_path, cmd_local)
        self.append_output(f"Local delete command for tag '{tag_name}' executed. Check output above.")

        if delete_remote:
            cmd_remote = ["push", remote_name, "--delete", tag_name]
            self.append_output(f"\n>>> git {' '.join(cmd_remote)}")
            # Assuming _process_git_command_results is still connected for the second command.
            # For more robust sequential execution, a sequence runner or chained callbacks would be better.
            self.git_executor.execute_command(self.current_repo_path, cmd_remote)
            self.append_output(f"Remote delete command for tag '{tag_name}' on remote '{remote_name}' executed. Check output above.")

    def _execute_tag_push(self, options: dict):
        remote_name = options['remote_name']
        push_all = options['push_all']
        specific_tag = options['specific_tag_name']
        cmd = ["push", remote_name]
        if push_all:
            cmd.append("--tags")
        elif specific_tag:
            cmd.append(specific_tag)
        else: # Should be caught by dialog validation
            self.append_output("Error: Invalid options for push tags.")
            return
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        try: self.git_executor.command_finished.disconnect()
        except TypeError: pass
        self.git_executor.command_finished.connect(self._process_git_command_results)
        self.git_executor.execute_command(self.current_repo_path, cmd)
        self.append_output("Push tag(s) command executed. See output above for results.")

    def select_repository(self):
        path = QFileDialog.getExistingDirectory(self, "Select Git Repository")
        if path:
            self.current_repo_path = path
            self.repo_label.setText(f"Current Repository: {self.current_repo_path}")
            self.append_output(f"Selected repository: {self.current_repo_path}")
        else: self.append_output("Repository selection cancelled.")

    def append_output(self, text):
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
            elif ok: self.append_output("Checkout operation cancelled: No branch name entered.")

    def on_merge_click(self):
        if self._check_repo_selected():
            branch_name, ok = QInputDialog.getText(self, "Merge Branch", "Enter branch name to merge into current branch:")
            if ok and branch_name.strip():
                actual_branch_name = branch_name.strip()
                self.append_output(f"\n>>> git merge {actual_branch_name}")
                self.git_executor.execute_command(self.current_repo_path, ["merge", actual_branch_name])
            elif ok: self.append_output("Merge operation cancelled: No branch name entered.")

    def create_versioned_branch_from_commit(self):
        if not self._check_repo_selected(): return
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
        self.git_executor.command_finished.disconnect(self._process_git_command_results)
        self.git_executor.command_finished.connect(self._on_list_branches_finished)
        self.append_output(f"\n>>> git branch --list {prefix}-v*")
        self.git_executor.execute_command(self.current_repo_path, ["branch", "--list", f"{prefix}-v*"])

    def _on_list_branches_finished(self, stdout_str, stderr_str, exit_code):
        self.git_executor.command_finished.disconnect(self._on_list_branches_finished)
        self.git_executor.command_finished.connect(self._process_git_command_results)
        versions = []
        for line in stdout_str.splitlines():
            branch = line.strip().lstrip('*').strip()
            m = re.match(rf"{re.escape(self._pending_prefix)}-v(\d+)", branch)
            if m:
                try: versions.append(int(m.group(1)))
                except ValueError: pass
        next_ver = max(versions) + 1 if versions else 1
        self._new_branch_name = f"{self._pending_prefix}-v{next_ver}"
        self.append_output(f"Proposed branch name: {self._new_branch_name}")
        cmds = [
            ["checkout", "main"], ["pull"],
            ["checkout", "-b", self._new_branch_name],
            ["cherry-pick", self._pending_hash, "-X", "theirs"],
        ]
        self.run_command_sequence(cmds, self._on_branch_success, self._on_branch_failure)

    def _on_branch_success(self): self.append_output(f"Branch {self._new_branch_name} created and commit applied.")
    def _on_branch_failure(self, stderr_str, exit_code):
        self.append_output(f"Failed during branch creation: {stderr_str}")
        self.resolve_conflict_button.setVisible(True)

    def confirm_conflict_commit(self):
        if not self._check_repo_selected(): return
        cmds = [["add", "."], ["commit", "-m", "Manual conflict resolution"]]
        self.run_command_sequence(cmds, lambda: self.resolve_conflict_button.setVisible(False))

    def run_command_sequence(self, commands, success_cb=None, failure_cb=None):
        self._command_queue = list(commands)
        self._seq_success_cb = success_cb
        self._seq_failure_cb = failure_cb
        self._run_next_command()

    def _run_next_command(self):
        if not self._command_queue:
            if self._seq_success_cb: self._seq_success_cb()
            return
        cmd = self._command_queue.pop(0)
        self._current_seq_cmd = cmd
        try: self.git_executor.command_finished.disconnect(self._process_git_command_results)
        except TypeError: pass
        self.git_executor.command_finished.connect(self._handle_seq_finished)
        self.append_output(f"\n>>> git {' '.join(cmd)}")
        self.git_executor.execute_command(self.current_repo_path, cmd)

    def _handle_seq_finished(self, stdout_str, stderr_str, exit_code):
        self.git_executor.command_finished.disconnect(self._handle_seq_finished)
        self._process_git_command_results(stdout_str, stderr_str, exit_code)
        if exit_code != 0:
            if self._seq_failure_cb: self._seq_failure_cb(stderr_str, exit_code)
            self._command_queue = []
            self.git_executor.command_finished.connect(self._process_git_command_results)
            return
        if not self._command_queue:
            self.git_executor.command_finished.connect(self._process_git_command_results)
        self._run_next_command()

class InteractiveRebaseOptionsDialog(QDialog):
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
    def get_base_commit(self) -> str: return self.base_commit_input.text().strip()

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
            modified_list.append({'action': new_action, 'hash': original_commit_hash, 'subject': new_subject})
        return modified_list
    def _clear_scroll_layout(self):
        while self.scroll_content_layout.count():
            child = self.scroll_content_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            elif child.layout():
                while child.layout().count():
                    sub_child = child.layout().takeAt(0)
                    if sub_child.widget(): sub_child.widget().deleteLater()
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
            action, chash, subject = commit_info['action'], commit_info['hash'], commit_info['subject']
            action_combo = QComboBox(); action_combo.addItems(REBASE_ACTIONS)
            if action in REBASE_ACTIONS: action_combo.setCurrentText(action)
            else: action_combo.setCurrentText("pick")
            action_combo.setMinimumWidth(80)
            hash_label = QLabel(chash); hash_label.setMinimumWidth(70)
            hash_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            subject_edit = QLineEdit(subject)
            self.commit_editors.append({'action_combo': action_combo, 'hash_label': hash_label, 'subject_edit': subject_edit})
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

class StashCreateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stash Changes")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Stash message (optional):"))
        self.message_input = QLineEdit()
        layout.addWidget(self.message_input)
        self.keep_index_checkbox = QCheckBox("Keep staged changes (--keep-index)")
        layout.addWidget(self.keep_index_checkbox)
        self.include_untracked_checkbox = QCheckBox("Include untracked files (-u / --include-untracked)")
        layout.addWidget(self.include_untracked_checkbox)
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def get_stash_options(self) -> dict:
        return {
            'message': self.message_input.text().strip(),
            'keep_index': self.keep_index_checkbox.isChecked(),
            'include_untracked': self.include_untracked_checkbox.isChecked()
        }

class StashListDialog(QDialog):
    def __init__(self, stashes: list, action_context: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Available Stashes")
        self.setMinimumSize(500, 300)
        self._stashes = stashes
        self._selected_stash_id = None
        self._action_context = action_context

        main_layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for stash_item in self._stashes:
            display_text = f"{stash_item['id']}: {stash_item['description']}"
            lw_item = QListWidgetItem(display_text)
            lw_item.setData(Qt.UserRole, stash_item['id'])
            self.list_widget.addItem(lw_item)

        self.list_widget.itemSelectionChanged.connect(self._update_selection_status)
        main_layout.addWidget(self.list_widget)

        if self._action_context == "apply":
            self.pop_checkbox = QCheckBox("Pop stash (delete after applying)")
            main_layout.addWidget(self.pop_checkbox)
            self.reinstate_index_checkbox = QCheckBox("Reinstate index (--index)")
            main_layout.addWidget(self.reinstate_index_checkbox)

        button_layout = QHBoxLayout()
        self.select_button = QPushButton("Select")
        self.cancel_button = QPushButton("Cancel")

        self.select_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.select_button.setEnabled(False)

        if self._action_context == "apply":
            self.select_button.setText("Apply")
        elif self._action_context == "drop":
            self.select_button.setText("Drop")

        button_layout.addStretch()
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def _update_selection_status(self):
        selected_items = self.list_widget.selectedItems()
        self.select_button.setEnabled(bool(selected_items))
        if selected_items:
            self._selected_stash_id = selected_items[0].data(Qt.UserRole)
        else:
            self._selected_stash_id = None

    def get_selected_stash_id(self) -> str | None:
        return self._selected_stash_id

    def get_apply_options(self) -> dict:
        if self._action_context == "apply":
            return {
                'pop': self.pop_checkbox.isChecked(),
                'reinstate_index': self.reinstate_index_checkbox.isChecked()
            }
        return {'pop': False, 'reinstate_index': False}

class TagCreateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Git Tag")

        main_layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.tag_name_input = QLineEdit()
        form_layout.addRow("Tag Name (e.g., v1.0.0):", self.tag_name_input)

        self.annotated_checkbox = QCheckBox("Create Annotated Tag")
        form_layout.addRow(self.annotated_checkbox)

        self.message_label = QLabel("Annotation Message:")
        self.message_input = QTextEdit()
        self.message_input.setFixedHeight(self.fontMetrics().lineSpacing() * 4)
        form_layout.addRow(self.message_label, self.message_input)

        self.commit_hash_input = QLineEdit()
        form_layout.addRow("Commit to Tag (optional, default: HEAD):", self.commit_hash_input)

        self.force_checkbox = QCheckBox("Force Create/Update Tag (-f)")
        form_layout.addRow(self.force_checkbox)

        main_layout.addLayout(form_layout)

        self.message_label.setVisible(False)
        self.message_input.setVisible(False)
        self.annotated_checkbox.stateChanged.connect(self._toggle_message_input)

        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def _toggle_message_input(self, state):
        is_checked = (state == Qt.Checked)
        self.message_label.setVisible(is_checked)
        self.message_input.setVisible(is_checked)

    def get_tag_options(self) -> dict:
        message = ""
        if self.annotated_checkbox.isChecked():
            message = self.message_input.toPlainText().strip()

        return {
            'name': self.tag_name_input.text().strip(),
            'annotated': self.annotated_checkbox.isChecked(),
            'message': message,
            'commit_hash': self.commit_hash_input.text().strip(),
            'force': self.force_checkbox.isChecked()
        }

class TagListDialog(QDialog):
    def __init__(self, tags: list, action_context: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Available Tags")
        self.setMinimumSize(400, 300)
        self._tags = tags
        self._selected_tag_name = None
        self._action_context = action_context

        main_layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for tag_item_data in self._tags:
            display_text = tag_item_data['name']
            lw_item = QListWidgetItem(display_text)
            lw_item.setData(Qt.UserRole, tag_item_data['name'])
            self.list_widget.addItem(lw_item)

        self.list_widget.itemSelectionChanged.connect(self._update_selection_status)
        main_layout.addWidget(self.list_widget)

        button_layout = QHBoxLayout()
        self.action_button = QPushButton("Select")
        if self._action_context == "push_single":
            self.action_button.setText("Push Selected Tag")
        elif self._action_context == "delete_local":
             self.action_button.setText("Delete Local Tag")
        elif self._action_context == "delete": # Context for delete tag overall
             self.action_button.setText("Delete")


        self.cancel_button = QPushButton("Cancel")

        self.action_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.action_button.setEnabled(False)

        button_layout.addStretch()
        button_layout.addWidget(self.action_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def _update_selection_status(self):
        selected_items = self.list_widget.selectedItems()
        self.action_button.setEnabled(bool(selected_items))
        if selected_items:
            self._selected_tag_name = selected_items[0].data(Qt.UserRole)
        else:
            self._selected_tag_name = None

    def get_selected_tag_name(self) -> str | None:
        return self._selected_tag_name

# --- Tag Push Dialog --- NEW
class TagPushDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Push Tags to Remote")
        main_layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.remote_name_input = QLineEdit("origin")
        form_layout.addRow("Remote Name:", self.remote_name_input)
        main_layout.addLayout(form_layout)

        options_group = QGroupBox("Push Options")
        group_layout = QVBoxLayout()
        self.push_all_radio = QRadioButton("Push all tags (--tags)")
        self.push_specific_radio = QRadioButton("Push specific tag:")
        self.specific_tag_input = QLineEdit()

        group_layout.addWidget(self.push_all_radio)
        group_layout.addWidget(self.push_specific_radio)

        # Indent specific_tag_input under its radio button
        specific_tag_layout = QHBoxLayout()
        specific_tag_layout.addSpacing(20) # Indentation
        specific_tag_layout.addWidget(self.specific_tag_input)
        group_layout.addLayout(specific_tag_layout)

        options_group.setLayout(group_layout)
        main_layout.addWidget(options_group)

        self.push_all_radio.setChecked(True)
        self.specific_tag_input.setEnabled(False) # Initially disabled
        self.push_all_radio.toggled.connect(self._toggle_specific_tag_input)
        self.push_specific_radio.toggled.connect(self._toggle_specific_tag_input)


        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def _toggle_specific_tag_input(self):
        # Radio buttons are auto-exclusive. Enable input if "specific" is checked.
        self.specific_tag_input.setEnabled(self.push_specific_radio.isChecked())

    def get_push_options(self) -> dict:
        specific_tag_name = ""
        if self.push_specific_radio.isChecked():
            specific_tag_name = self.specific_tag_input.text().strip()
        return {
            'remote_name': self.remote_name_input.text().strip(),
            'push_all': self.push_all_radio.isChecked(),
            'specific_tag_name': specific_tag_name
        }

# --- Tag Delete Options Dialog --- NEW
class TagDeleteOptionsDialog(QDialog):
    def __init__(self, tag_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Delete Tag '{tag_name}'")
        self.tag_name_to_delete = tag_name

        main_layout = QVBoxLayout(self)

        self.delete_remote_checkbox = QCheckBox("Also delete from remote repository")
        main_layout.addWidget(self.delete_remote_checkbox)

        remote_form_layout = QFormLayout()
        self.remote_label = QLabel("Remote Name:")
        self.remote_name_input = QLineEdit("origin")
        remote_form_layout.addRow(self.remote_label, self.remote_name_input)
        main_layout.addLayout(remote_form_layout)

        self.remote_label.setVisible(False)
        self.remote_name_input.setVisible(False)
        self.delete_remote_checkbox.stateChanged.connect(self._toggle_remote_input)

        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def _toggle_remote_input(self, state):
        is_checked = (state == Qt.Checked)
        self.remote_label.setVisible(is_checked)
        self.remote_name_input.setVisible(is_checked)

    def get_delete_options(self) -> dict:
        remote_name = ""
        if self.delete_remote_checkbox.isChecked():
            remote_name = self.remote_name_input.text().strip()
        return {
            'delete_remote': self.delete_remote_checkbox.isChecked(),
            'remote_name': remote_name
        }

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
