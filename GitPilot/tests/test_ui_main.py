import sys
import os
import unittest
import html

# Add the parent directory of 'GitPilot' (project root) to sys.path
# This assumes 'test_ui_main.py' is in 'GitPilot/tests/'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

# Add the 'GitPilot' directory itself to sys.path as well, for internal imports within ui_main
git_pilot_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, git_pilot_dir)


from GitPilot.ui_main import (
    MainWindow,
    InteractiveRebaseOptionsDialog,
    RebaseTodoEditorDialog,
    BranchManagerDialog,
)
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont # QFont might be implicitly available if MainWindow imports it, but explicit is safer

class TestFormatDiffLineToHtml(unittest.TestCase):
    def test_added_line(self):
        line = "+added line"
        expected = f'<font color="green">{html.escape(line)}</font>'
        self.assertEqual(MainWindow._format_diff_line_to_html(line), expected)

    def test_removed_line(self):
        line = "-removed line"
        expected = f'<font color="red">{html.escape(line)}</font>'
        self.assertEqual(MainWindow._format_diff_line_to_html(line), expected)

    def test_hunk_header_line(self):
        line = "@@ -1,2 +3,4 @@"
        expected = f'<font color="cyan">{html.escape(line)}</font>'
        self.assertEqual(MainWindow._format_diff_line_to_html(line), expected)

    def test_diff_git_line(self):
        line = "diff --git a/file b/file"
        expected = f'<font color="yellow">{html.escape(line)}</font>'
        self.assertEqual(MainWindow._format_diff_line_to_html(line), expected)

    def test_file_header_plus_line(self):
        line = "+++ b/file.py"
        expected = html.escape(line) # Should only be escaped
        self.assertEqual(MainWindow._format_diff_line_to_html(line), expected)

    def test_file_header_minus_line(self):
        line = "--- a/file.py"
        expected = html.escape(line) # Should only be escaped
        self.assertEqual(MainWindow._format_diff_line_to_html(line), expected)

    def test_context_line(self):
        line = " context line" # Starts with a space
        expected = html.escape(line)
        self.assertEqual(MainWindow._format_diff_line_to_html(line), expected)

        line_no_space = "context line" # No specific prefix
        expected_no_space = html.escape(line_no_space)
        self.assertEqual(MainWindow._format_diff_line_to_html(line_no_space), expected_no_space)

    def test_line_with_html_chars(self):
        line = "+<tag> & value"
        expected = f'<font color="green">{html.escape(line)}</font>'
        # Manually construct what html.escape(line) would be inside the font tag
        # expected_manual = '<font color="green">+&lt;tag&gt; &amp; value</font>'
        self.assertEqual(MainWindow._format_diff_line_to_html(line), expected)

    def test_empty_line(self):
        line = ""
        expected = "" # html.escape('') is ''
        self.assertEqual(MainWindow._format_diff_line_to_html(line), expected)

# Moved the main execution block to the end of the file
# so all test classes are discovered.

class TestDiffViewerIntegration(unittest.TestCase):
    app = None # Class attribute to hold QApplication instance

    @classmethod
    def setUpClass(cls):
        # Create QApplication instance once for the test class
        import GitPilot.ui_main # Import the module to check its path
        print(f"DEBUG: MainWindow is being imported from module: {GitPilot.ui_main.__file__}")
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        """Set up for each test method."""
        self.window = MainWindow()
        # Mock essential attributes or setup to bypass complex UI interactions
        self.window.current_repo_path = "dummy_repo_path" # To pass _check_repo_selected()
        # self.window.show() # Not strictly necessary for these tests if widgets are created
        # self.window.hide()

    def tearDown(self):
        """Clean up after each test method."""
        # Ensures the window is closed and resources are potentially freed
        # Important if .show() was called. For non-shown windows, may not be critical.
        self.window.close()
        del self.window


    def test_handle_diff_output_populates_view(self):
        sample_diff = (
            "diff --git a/file.txt b/file.txt\n"
            "--- a/file.txt\n"
            "+++ b/file.txt\n"
            "@@ -1,1 +1,2 @@\n"
            "-old line\n"
            "+new line\n"
            "+another new line\n"
            " context line"
        )

        # Clear previous terminal output before testing stderr logging
        self.window.output_terminal.clear()
        self.window._handle_diff_output(sample_diff, "", 0)
        actual_html = self.window.diff_view_text_edit.toHtml()

        # Check for key formatted parts by looking for content and style
        self.assertIn(html.escape("diff --git a/file.txt b/file.txt"), actual_html)
        self.assertIn("color:#ffff00", actual_html) # Yellow for diff --git

        self.assertIn(html.escape("-old line"), actual_html)
        self.assertIn("color:#ff0000", actual_html) # Red for removed lines

        self.assertIn(html.escape("+new line"), actual_html)
        self.assertIn("color:#008000", actual_html) # Green for added lines

        self.assertIn(html.escape("@@ -1,1 +1,2 @@"), actual_html)
        self.assertIn("color:#00ffff", actual_html) # Cyan for hunk headers

        self.assertIn(html.escape(" context line"), actual_html) # Context lines have no specific color span from our func
        self.assertIn(html.escape("--- a/file.txt"), actual_html) # File header lines also no specific color span
        self.assertIn(html.escape("+++ b/file.txt"), actual_html)


        # Test "no changes" case
        self.window.output_terminal.clear()
        self.window._handle_diff_output("", "", 0) # stdout_str is empty, exit_code 0
        actual_html_no_changes = self.window.diff_view_text_edit.toHtml()
        # QTextEdit.toHtml() will produce a full HTML document.
        # If setPlainText was used, it might be wrapped in <p>...</p>.
        # Let's check for the content within typical HTML structure.
        self.assertIn(">No changes detected.<", actual_html_no_changes)

        # Test error case for diff command itself (e.g., git diff failed)
        self.window.output_terminal.clear()
        # In ui_main.py, _handle_diff_output sets a specific message if exit_code !=0
        # "Error generating diff (exit code: {exit_code}). Check terminal output for details."
        self.window._handle_diff_output("", "Simulated git error string", 1)
        actual_html_error = self.window.diff_view_text_edit.toHtml()
        # Check for the specific error message set by _handle_diff_output
        self.assertIn(">Error generating diff (exit code: 1). Check terminal output for details.<", actual_html_error)

        # Check if the stderr_str ("Simulated git error string") was logged to the main output_terminal
        main_terminal_content = self.window.output_terminal.toPlainText()
        self.assertIn("--- Diff Command Error Output ---", main_terminal_content)
        self.assertIn("Simulated git error string", main_terminal_content)


class TestInteractiveRebaseOptionsDialog(unittest.TestCase):
    app = None
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def test_get_base_commit(self):
        dialog = InteractiveRebaseOptionsDialog()
        test_base = "HEAD~3"
        dialog.base_commit_input.setText(test_base)
        self.assertEqual(dialog.get_base_commit(), test_base)

        dialog.base_commit_input.setText("  main_branch  ")
        self.assertEqual(dialog.get_base_commit(), "main_branch")

        dialog.base_commit_input.setText("")
        self.assertEqual(dialog.get_base_commit(), "")
        dialog.close()


class TestRebaseTodoEditorDialog(unittest.TestCase):
    app = None
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

        cls.sample_commits = [
            {'action': 'pick', 'hash': 'h1', 'subject': 'Commit 1 subject'},
            {'action': 'pick', 'hash': 'h2', 'subject': 'Commit 2 subject with <html_chars> & stuff'},
            {'action': 'pick', 'hash': 'h3', 'subject': 'Commit 3 subject'},
        ]

    def setUp(self):
        # Make a deep copy for each test to ensure independence
        self.current_sample_commits = [commit.copy() for commit in self.sample_commits]
        self.dialog = RebaseTodoEditorDialog(self.current_sample_commits)

    def tearDown(self):
        self.dialog.close() # Ensure dialog is closed
        del self.dialog

    def test_initial_get_modified_todo_list(self):
        self.assertEqual(self.dialog.get_modified_todo_list(), self.current_sample_commits)

    def test_modify_action(self):
        self.dialog.commit_editors[0]['action_combo'].setCurrentText("squash")
        modified_list = self.dialog.get_modified_todo_list()

        expected_list = [commit.copy() for commit in self.current_sample_commits]
        expected_list[0]['action'] = "squash"

        self.assertEqual(modified_list, expected_list)

    def test_modify_subject(self):
        new_subject_text = "Completely New Subject for Commit 2"
        self.dialog.commit_editors[1]['subject_edit'].setText(new_subject_text)
        modified_list = self.dialog.get_modified_todo_list()

        expected_list = [commit.copy() for commit in self.current_sample_commits]
        expected_list[1]['subject'] = new_subject_text

        self.assertEqual(modified_list, expected_list)
        # Also check that the hash remains unchanged
        self.assertEqual(modified_list[1]['hash'], self.current_sample_commits[1]['hash'])


    def test_reorder_commits_move_down(self):
        # Initial: h1, h2, h3
        self.dialog._move_commit_down(0) # Move h1 down -> h2, h1, h3
        modified_list = self.dialog.get_modified_todo_list()

        self.assertEqual(len(modified_list), 3)
        self.assertEqual(modified_list[0]['hash'], 'h2') # h2 is now first
        self.assertEqual(modified_list[1]['hash'], 'h1') # h1 is now second
        self.assertEqual(modified_list[2]['hash'], 'h3') # h3 remains third

        # Check that other data is still associated correctly with the hash
        self.assertEqual(modified_list[1]['subject'], self.current_sample_commits[0]['subject']) # h1's subject

    def test_reorder_commits_move_up(self):
        # Initial: h1, h2, h3
        self.dialog._move_commit_up(1) # Move h2 up -> h2, h1, h3
        modified_list = self.dialog.get_modified_todo_list()

        self.assertEqual(len(modified_list), 3)
        self.assertEqual(modified_list[0]['hash'], 'h2')
        self.assertEqual(modified_list[1]['hash'], 'h1')
        self.assertEqual(modified_list[2]['hash'], 'h3')

        self.assertEqual(modified_list[0]['subject'], self.current_sample_commits[1]['subject']) # h2's subject

    def test_reorder_boundary_conditions(self):
        # Test moving first item up (should do nothing)
        self.dialog._move_commit_up(0)
        self.assertEqual(self.dialog.get_modified_todo_list(), self.current_sample_commits)

        # Test moving last item down (should do nothing)
        self.dialog._move_commit_down(len(self.current_sample_commits) - 1)
        self.assertEqual(self.dialog.get_modified_todo_list(), self.current_sample_commits)

        # Test with a single item list
        single_item_list = [{'action': 'pick', 'hash': 'single_h', 'subject': 'Single commit'}]
        single_item_dialog = RebaseTodoEditorDialog(single_item_list)
        single_item_dialog._move_commit_up(0)
        self.assertEqual(single_item_dialog.get_modified_todo_list(), single_item_list)
        single_item_dialog._move_commit_down(0)
        self.assertEqual(single_item_dialog.get_modified_todo_list(), single_item_list)
        single_item_dialog.close()


class TestBranchManagerDialog(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def test_select_highlighted_rows(self):
        dialog = BranchManagerDialog(["b1", "b2", "b3"])
        dialog.list_widget.item(0).setSelected(True)
        dialog.list_widget.item(2).setSelected(True)
        dialog.select_highlighted_rows()
        states = [dialog.list_widget.item(i).checkState() for i in range(3)]
        self.assertEqual(states, [Qt.Checked, Qt.Unchecked, Qt.Checked])
        self.assertEqual(dialog.get_checked_branches(), ["b1", "b3"])
        dialog.close()


if __name__ == '__main__':
    unittest.main()
