"""
GitPilot: Git Command Execution Utilities.

This module provides the GitExecutor class, which uses QProcess to run
Git commands asynchronously and emits signals with their results.
"""
from PyQt5.QtCore import QObject, QProcess, pyqtSignal, QTimer, QProcessEnvironment

class GitExecutor(QObject):
    """
    Executes Git commands asynchronously using QProcess.

    Signals:
        command_finished (str, str, int): Emitted when a command has finished.
                                          Passes stdout, stderr, and exit code.
    """
    command_finished = pyqtSignal(str, str, int)

    def __init__(self):
        """Initializes the GitExecutor."""
        super().__init__()
        self.process = None # Holds the current QProcess instance
        self.stdout_acc = "" # Accumulator for standard output
        self.stderr_acc = "" # Accumulator for standard error

    def execute_command(self, repository_path, command_parts, env_vars: dict = None):
        """
        Executes a Git command in the specified repository.

        Args:
            repository_path (str): The absolute path to the Git repository.
            command_parts (list): A list of strings representing the command
                                  and its arguments (e.g., ["status"]).
        """
        if self.process and self.process.state() == QProcess.Running:
            # Notify user that a command is already running.
            # Use QTimer.singleShot to ensure signal is emitted from the event loop.
            QTimer.singleShot(0, lambda: self.command_finished.emit("", "A command is already running. Please wait.", -1))
            return

        self.process = QProcess()
        self.process.setWorkingDirectory(repository_path)

        if env_vars:
            environment = QProcessEnvironment.systemEnvironment()
            for key, value in env_vars.items():
                environment.insert(key, value)
            self.process.setProcessEnvironment(environment)

        self.stdout_acc = "" # Reset accumulators for the new command
        self.stderr_acc = ""

        # Connect QProcess signals to internal handler methods
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.handle_finished) # Catches process completion

        # Start the Git command
        self.process.start("git", command_parts)
        # The process runs asynchronously; results are emitted via command_finished signal.

    def handle_stdout(self):
        """Reads and accumulates data from the process's standard output."""
        if not self.process: return # Should not happen if signals are connected right
        data = self.process.readAllStandardOutput().data().decode()
        self.stdout_acc += data

    def handle_stderr(self):
        """Reads and accumulates data from the process's standard error."""
        if not self.process: return
        data = self.process.readAllStandardError().data().decode()
        self.stderr_acc += data

    def handle_finished(self, exit_code, exit_status):
        """
        Handles the QProcess.finished signal.

        Emits the command_finished signal with the accumulated stdout, stderr,
        and the command's exit code. Cleans up the QProcess instance.

        Args:
            exit_code (int): The exit code of the process.
            exit_status (QProcess.ExitStatus): The exit status of the process.
        """
        final_stdout = self.stdout_acc.strip()
        final_stderr = self.stderr_acc.strip()

        self.command_finished.emit(final_stdout, final_stderr, exit_code)

        if self.process:
          self.process.deleteLater() # Ensure QProcess is cleaned up properly
          self.process = None
        self.stdout_acc = "" # Clear accumulators for the next command
        self.stderr_acc = ""

if __name__ == '__main__':
    # This section is primarily for module-level information or basic tests (if any).
    # Full testing of GitExecutor typically requires a QApplication instance for signals.
    print("GitPilot git_utils.py: GitExecutor class defined with comments.")
    print("To test effectively, integrate with a QApplication and trigger execute_command.")
