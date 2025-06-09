"""GitPilot: PyQt5 UI Implementation.

This module defines the MainWindow class, which sets up the graphical user
interface for the GitPilot application, including layouts, widgets, and signal connections.
"""
import sys
from PyQt5.QtWidgets import (QMainWindow, QApplication, QWidget,
                             QVBoxLayout, QHBoxLayout, QTextEdit,
                             QPushButton, QLineEdit, QFileDialog, QLabel, QInputDialog)
from PyQt5.QtCore import Qt
from git_utils import GitExecutor

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
        self.git_executor.command_finished.connect(self.handle_command_output)

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
        main_layout.addWidget(self.output_terminal, 1) # Add stretch factor

        # Commit message area
        commit_layout = QHBoxLayout()
        self.commit_message_input = QLineEdit()
        self.commit_message_input.setPlaceholderText("Enter commit message...")
        commit_layout.addWidget(self.commit_message_input)

        self.commit_button = QPushButton("Commit")
        commit_layout.addWidget(self.commit_button)
        main_layout.addLayout(commit_layout)

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
        self.branch_button = QPushButton("Branch Operations") # Placeholder for more complex branch UI
        buttons_group3_layout.addWidget(self.branch_button)

        self.checkout_button = QPushButton("Checkout Branch") # Placeholder for input
        buttons_group3_layout.addWidget(self.checkout_button)

        self.merge_button = QPushButton("Merge Branch") # Placeholder for input
        buttons_group3_layout.addWidget(self.merge_button)
        main_layout.addLayout(buttons_group3_layout)

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
        # self.select_repo_button is already connected in __init__
        self.append_output("GitPilot UI Initialized. Select a repository to begin.")

    def select_repository(self):
        """Opens a dialog for the user to select a Git repository folder."""
        path = QFileDialog.getExistingDirectory(self, "Select Git Repository")
        if path:
            # Basic check for .git folder (can be improved)
            # For now, just assume it's a git repo if user selects it.
            # A more robust check would be to see if `git rev-parse --is-inside-work-tree` runs successfully
            self.current_repo_path = path
            self.repo_label.setText(f"Current Repository: {self.current_repo_path}")
            self.append_output(f"Selected repository: {self.current_repo_path}")
        else:
            self.append_output("Repository selection cancelled.")

    def append_output(self, text):
        """Appends text to the output terminal and ensures visibility."""
        self.output_terminal.append(text)
        self.output_terminal.ensureCursorVisible() # Scroll to the bottom

    # Placeholder methods for button clicks (to be implemented in Step 4)
    # def on_status_click(self): self.append_output("Status button clicked (not implemented)")
    # def on_pull_click(self): self.append_output("Pull button clicked (not implemented)")
    # def on_add_all_click(self): self.append_output("Add All button clicked (not implemented)")
    # def on_commit_click(self): self.append_output("Commit button clicked (not implemented)")
    # def on_push_click(self): self.append_output("Push button clicked (not implemented)")
    # def on_branch_click(self): self.append_output("Branch button clicked (not implemented)")
    # def on_checkout_click(self): self.append_output("Checkout button clicked (not implemented)")
    # def on_merge_click(self): self.append_output("Merge button clicked (not implemented)")
    # def on_log_click(self): self.append_output("Log button clicked (not implemented)")

    def _check_repo_selected(self):
        """Checks if a repository path is selected, appends error if not.

        Returns:
            bool: True if a repository is selected, False otherwise.
        """
        if not self.current_repo_path:
            self.append_output("ERROR: No repository selected. Please select a repository first.")
            return False
        self.append_output(f"--- Repository: {self.current_repo_path} ---") # Add context for command
        return True

    def on_status_click(self):
        """Handles the 'Status' button click. Executes 'git status'."""
        if self._check_repo_selected():
            # Conceptual: Disable buttons here before running command
            # self.set_buttons_enabled(False)
            # self.append_output("DEBUG: Disabling buttons (conceptual)")
            self.append_output("\n>>> git status")
            self.git_executor.execute_command(self.current_repo_path, ["status"])

    def on_pull_click(self):
        """Handles the 'Pull' button click. Executes 'git pull'."""
        if self._check_repo_selected():
            # Conceptual: Disable buttons here before running command
            # self.set_buttons_enabled(False)
            # self.append_output("DEBUG: Disabling buttons (conceptual)")
            self.append_output("\n>>> git pull")
            self.git_executor.execute_command(self.current_repo_path, ["pull"])

    def on_add_all_click(self):
        """Handles the 'Add All' button click. Executes 'git add .'."""
        if self._check_repo_selected():
            # Conceptual: Disable buttons here before running command
            # self.set_buttons_enabled(False)
            # self.append_output("DEBUG: Disabling buttons (conceptual)")
            self.append_output("\n>>> git add .")
            self.git_executor.execute_command(self.current_repo_path, ["add", "."])

    def on_commit_click(self):
        """Handles the 'Commit' button click. Gets message and executes 'git commit'."""
        if self._check_repo_selected():
            # Conceptual: Disable buttons here before running command
            # self.set_buttons_enabled(False)
            # self.append_output("DEBUG: Disabling buttons (conceptual)")
            commit_message = self.commit_message_input.text().strip()
            if not commit_message:
                self.append_output("ERROR: Commit message cannot be empty.")
                return
            self.append_output(f"\n>>> git commit -m \"{commit_message}\"")
            self.git_executor.execute_command(self.current_repo_path, ["commit", "-m", commit_message])
            self.commit_message_input.clear()

    def on_push_click(self):
        """Handles the 'Push' button click. Executes 'git push'."""
        if self._check_repo_selected():
            # Conceptual: Disable buttons here before running command
            # self.set_buttons_enabled(False)
            # self.append_output("DEBUG: Disabling buttons (conceptual)")
            self.append_output("\n>>> git push")
            self.git_executor.execute_command(self.current_repo_path, ["push"])

    def on_log_click(self):
        """Handles the 'Log' button click. Executes 'git log --graph ...'."""
        if self._check_repo_selected():
            # Conceptual: Disable buttons here before running command
            # self.set_buttons_enabled(False)
            # self.append_output("DEBUG: Disabling buttons (conceptual)")
            self.append_output("\n>>> git log --graph --pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset' --abbrev-commit --all")
            self.git_executor.execute_command(self.current_repo_path, ["log", "--graph", "--pretty=format:'%Cred%h%Creset -%C(yellow)%d%Creset %s %Cgreen(%cr) %C(bold blue)<%an>%Creset'", "--abbrev-commit", "--all"])

    def on_branch_click(self):
        """Handles the 'Branch' button click. Executes 'git branch -vv'."""
        if self._check_repo_selected():
            # Conceptual: Disable buttons here before running command
            # self.set_buttons_enabled(False)
            # self.append_output("DEBUG: Disabling buttons (conceptual)")
            self.append_output("\n>>> git branch -vv")
            self.git_executor.execute_command(self.current_repo_path, ["branch", "-vv"])

    def on_checkout_click(self):
        """Handles the 'Checkout' button click. Prompts for branch and executes 'git checkout'."""
        if self._check_repo_selected():
            branch_name, ok = QInputDialog.getText(self, "Checkout Branch", "Enter branch name to checkout:")
            if ok and branch_name.strip():
                # Conceptual: Disable buttons here before running command
                # self.set_buttons_enabled(False)
                # self.append_output("DEBUG: Disabling buttons (conceptual)")
                actual_branch_name = branch_name.strip()
                self.append_output(f"\n>>> git checkout {actual_branch_name}")
                self.git_executor.execute_command(self.current_repo_path, ["checkout", actual_branch_name])
            elif ok:
                 self.append_output("Checkout operation cancelled: No branch name entered.")
            # else: user pressed Cancel, QInputDialog handles it, no message needed unless desired

    def on_merge_click(self):
        """Handles the 'Merge' button click. Prompts for branch and executes 'git merge'."""
        if self._check_repo_selected():
            branch_name, ok = QInputDialog.getText(self, "Merge Branch", "Enter branch name to merge into current branch:")
            if ok and branch_name.strip():
                # Conceptual: Disable buttons here before running command
                # self.set_buttons_enabled(False)
                # self.append_output("DEBUG: Disabling buttons (conceptual)")
                actual_branch_name = branch_name.strip()
                self.append_output(f"\n>>> git merge {actual_branch_name}")
                self.git_executor.execute_command(self.current_repo_path, ["merge", actual_branch_name])
            elif ok:
                 self.append_output("Merge operation cancelled: No branch name entered.")
            # else: user pressed Cancel

    # Conceptual method to enable/disable buttons during command execution
    # def set_buttons_enabled(self, enabled_status):
    #     self.status_button.setEnabled(enabled_status)
    #     self.pull_button.setEnabled(enabled_status)
    #     self.add_all_button.setEnabled(enabled_status)
    #     self.commit_button.setEnabled(enabled_status)
    #     self.push_button.setEnabled(enabled_status)
    #     self.log_button.setEnabled(enabled_status)
    #     self.branch_button.setEnabled(enabled_status)
    #     self.checkout_button.setEnabled(enabled_status)
    #     self.merge_button.setEnabled(enabled_status)
    #     # self.select_repo_button.setEnabled(enabled_status) # Maybe keep this one enabled

    def handle_command_output(self, stdout_str, stderr_str, exit_code):
        """Handles the command_finished signal from GitExecutor.

        Displays the command output (stdout, stderr, exit code) in the UI.
        Also conceptually re-enables UI buttons.

        Args:
            stdout_str (str): Standard output from the command.
            stderr_str (str): Standard error from the command.
            exit_code (int): Exit code of the command.
        """
        # Conceptual: Re-enable buttons here if they were disabled
        # self.set_buttons_enabled(True)
        # self.append_output("DEBUG: Re-enabling buttons (conceptual)")


        if exit_code == 0:
            self.append_output(f"SUCCESS: Command finished with exit code {exit_code}.")
        else:
            self.append_output(f"FAILED: Command finished with exit code {exit_code}.")

        if stdout_str:
            self.append_output("--- Standard Output ---")
            self.append_output(stdout_str)
        if stderr_str:
            # If exit code was 0, stderr might just be warnings or informational
            # If exit code non-zero, stderr is likely the primary error info
            if exit_code == 0 and stderr_str:
                 self.append_output("--- Standard Error (Warnings/Info) ---")
            elif exit_code != 0 and stderr_str:
                 self.append_output("--- Standard Error (Primary Error Info) ---")
            elif stderr_str: # Should not happen if stdout_str or stderr_str logic is fine
                 self.append_output("--- Standard Error ---")

            if stderr_str: # only append if there is actually stderr
                self.append_output(stderr_str)

        self.append_output("-------------------------")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
