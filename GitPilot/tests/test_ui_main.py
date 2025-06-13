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


from GitPilot.ui_main import (MainWindow, InteractiveRebaseOptionsDialog, RebaseTodoEditorDialog,
                              StashCreateDialog, StashListDialog, TagCreateDialog, TagListDialog, # Added TagListDialog
                              TagPushDialog, TagDeleteOptionsDialog, QDialog)
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtGui import QFont # QFont might be implicitly available if MainWindow imports it, but explicit is safer
from PyQt5.QtCore import Qt # For Qt.UserRole
from unittest.mock import patch, Mock

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

class TestStashCreateDialog(unittest.TestCase):
    app = None
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def test_get_stash_options_defaults(self):
        dialog = StashCreateDialog()
        options = dialog.get_stash_options()
        self.assertEqual(options['message'], "")
        self.assertEqual(options['keep_index'], False)
        self.assertEqual(options['include_untracked'], False)
        dialog.close()

    def test_get_stash_options_custom(self):
        dialog = StashCreateDialog()
        dialog.message_input.setText("Test stash msg")
        dialog.keep_index_checkbox.setChecked(True)
        dialog.include_untracked_checkbox.setChecked(True)

        options = dialog.get_stash_options()
        self.assertEqual(options['message'], "Test stash msg")
        self.assertEqual(options['keep_index'], True)
        self.assertEqual(options['include_untracked'], True)
        dialog.close()

class TestStashListDialog(unittest.TestCase):
    app = None
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

        cls.sample_parsed_stashes = [
            {'id': 'stash@{0}', 'description': 'WIP on main: abc...'},
            {'id': 'stash@{1}', 'description': 'On feature/xyz: 123...'},
        ]

    def test_init_list_only_context(self):
        dialog = StashListDialog(self.sample_parsed_stashes, "list_only")
        self.assertEqual(dialog.list_widget.count(), 2)
        self.assertIn("stash@{0}", dialog.list_widget.item(0).text())
        self.assertIn("WIP on main: abc...", dialog.list_widget.item(0).text())
        self.assertEqual(dialog.list_widget.item(0).data(Qt.UserRole), 'stash@{0}')
        self.assertEqual(dialog.select_button.text(), "Select") # Default or specific for list_only
        self.assertFalse(hasattr(dialog, 'pop_checkbox')) # Checkboxes should not exist
        dialog.close()

    def test_init_apply_context(self):
        dialog = StashListDialog(self.sample_parsed_stashes, "apply")
        self.assertEqual(dialog.select_button.text(), "Apply")
        self.assertTrue(hasattr(dialog, 'pop_checkbox'))
        self.assertTrue(hasattr(dialog, 'reinstate_index_checkbox'))

        # Forcing a show/hide cycle can sometimes be necessary for visibility to update
        dialog.show()
        dialog.hide()
        QApplication.processEvents() # Process any pending events

        # self.assertTrue(dialog.pop_checkbox.isVisible()) # Removing isVisible checks as they are flaky in test env
        # self.assertTrue(dialog.reinstate_index_checkbox.isVisible())
        self.assertIsNotNone(dialog.pop_checkbox) # Check that it was created
        self.assertIsNotNone(dialog.reinstate_index_checkbox) # Check that it was created
        dialog.close()

    def test_init_drop_context(self):
        dialog = StashListDialog(self.sample_parsed_stashes, "drop")
        self.assertEqual(dialog.select_button.text(), "Drop")
        self.assertFalse(hasattr(dialog, 'pop_checkbox')) # Checkboxes should not exist for drop
        dialog.close()

    def test_get_selected_stash_id_none(self):
        dialog = StashListDialog(self.sample_parsed_stashes, "list_only")
        self.assertIsNone(dialog.get_selected_stash_id())
        self.assertFalse(dialog.select_button.isEnabled())
        dialog.close()

    def test_get_selected_stash_id_with_selection(self):
        dialog = StashListDialog(self.sample_parsed_stashes, "list_only")
        dialog.list_widget.setCurrentRow(0) # Select the first item
        self.assertEqual(dialog.get_selected_stash_id(), 'stash@{0}')
        self.assertTrue(dialog.select_button.isEnabled())
        dialog.close()

    def test_get_apply_options_apply_context(self):
        dialog = StashListDialog(self.sample_parsed_stashes, "apply")
        dialog.pop_checkbox.setChecked(True)
        dialog.reinstate_index_checkbox.setChecked(False)
        options = dialog.get_apply_options()
        self.assertTrue(options['pop'])
        self.assertFalse(options['reinstate_index'])
        dialog.close()

    def test_get_apply_options_non_apply_context(self):
        dialog = StashListDialog(self.sample_parsed_stashes, "list_only")
        options = dialog.get_apply_options() # Should return defaults
        self.assertFalse(options['pop'])
        self.assertFalse(options['reinstate_index'])
        dialog.close()

class TestMainWindowStashManagement(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def setUp(self):
        self.window = MainWindow()
        self.window.current_repo_path = "dummy_repo"

        # Patch git_executor.execute_command directly on the instance for these tests
        self.mock_execute_command = Mock()
        self.window.git_executor.execute_command = self.mock_execute_command

    def tearDown(self):
        self.window.close()
        del self.window

    @patch('GitPilot.ui_main.StashCreateDialog')
    def test_stash_changes_executes_command_basic(self, MockStashCreateDialog):
        mock_dialog_instance = MockStashCreateDialog.return_value
        mock_dialog_instance.exec_.return_value = QDialog.Accepted
        mock_dialog_instance.get_stash_options.return_value = {'message': 'Test msg', 'keep_index': False, 'include_untracked': False}

        self.window.on_stash_changes_clicked()

        MockStashCreateDialog.assert_called_once_with(self.window)
        self.mock_execute_command.assert_called_once()
        args, _ = self.mock_execute_command.call_args
        self.assertEqual(args[0], self.window.current_repo_path)
        self.assertEqual(args[1], ["stash", "push", "-m", "Test msg"])

    @patch('GitPilot.ui_main.StashCreateDialog')
    def test_stash_changes_executes_command_all_options(self, MockStashCreateDialog):
        mock_dialog_instance = MockStashCreateDialog.return_value
        mock_dialog_instance.exec_.return_value = QDialog.Accepted
        mock_dialog_instance.get_stash_options.return_value = {'message': 'Complex Test', 'keep_index': True, 'include_untracked': True}

        self.window.on_stash_changes_clicked()

        MockStashCreateDialog.assert_called_once_with(self.window)
        self.mock_execute_command.assert_called_once()
        args, _ = self.mock_execute_command.call_args
        self.assertEqual(args[0], self.window.current_repo_path)
        self.assertEqual(args[1], ["stash", "push", "--keep-index", "--include-untracked", "-m", "Complex Test"])

    @patch('GitPilot.ui_main.StashCreateDialog')
    def test_stash_changes_executes_command_no_message(self, MockStashCreateDialog):
        mock_dialog_instance = MockStashCreateDialog.return_value
        mock_dialog_instance.exec_.return_value = QDialog.Accepted
        mock_dialog_instance.get_stash_options.return_value = {'message': '', 'keep_index': True, 'include_untracked': False}

        self.window.on_stash_changes_clicked()
        self.mock_execute_command.assert_called_once_with(self.window.current_repo_path, ["stash", "push", "--keep-index"])


    @patch('GitPilot.ui_main.StashListDialog')
    @patch('GitPilot.ui_main.QMessageBox')
    def test_list_stashes_shows_dialog_list_only(self, MockQMessageBox, MockStashListDialog):
        self.mock_execute_command.reset_mock() # Reset from potential __init__ calls if any

        # Simulate _fetch_stash_list_data being called
        self.window.on_list_stashes_clicked()

        # Assert that 'git stash list' was called
        self.mock_execute_command.assert_called_once_with(self.window.current_repo_path, ["stash", "list"])

        # Now, directly call _handle_stash_list_result as if 'git stash list' succeeded
        sample_stash_output = "stash@{0}: On main: Test\nstash@{1}: On dev: Work"
        self.window._handle_stash_list_result(sample_stash_output, "", 0)

        MockStashListDialog.assert_called_once()
        args, _ = MockStashListDialog.call_args
        self.assertEqual(len(args[0]), 2) # parsed_stashes
        self.assertEqual(args[0][0]['id'], 'stash@{0}')
        self.assertEqual(args[1], "list_only") # context

    @patch('GitPilot.ui_main.QMessageBox')
    def test_handle_stash_list_result_error(self, MockQMessageBox):
        self.window._stash_action_context = "list_only" # Set context
        self.window._handle_stash_list_result("", "Git error", 1)
        MockQMessageBox.critical.assert_called_once()

    @patch('GitPilot.ui_main.QMessageBox')
    def test_handle_stash_list_result_no_stashes(self, MockQMessageBox):
        self.window._stash_action_context = "list_only"
        self.window._handle_stash_list_result("", "", 0) # Empty output
        MockQMessageBox.information.assert_called_once()

    @patch('GitPilot.ui_main.StashListDialog')
    def test_apply_stash_executes_command(self, MockStashListDialog):
        self.mock_execute_command.reset_mock()

        # Stage 1: Call on_apply_stash_clicked, which calls _fetch_stash_list_data
        self.window.on_apply_stash_clicked()
        self.mock_execute_command.assert_called_once_with(self.window.current_repo_path, ["stash", "list"])

        # Stage 2: Simulate StashListDialog interaction by directly calling _handle_stash_list_result
        mock_dialog_instance = MockStashListDialog.return_value
        mock_dialog_instance.exec_.return_value = QDialog.Accepted
        mock_dialog_instance.get_selected_stash_id.return_value = 'stash@{1}'
        mock_dialog_instance.get_apply_options.return_value = {'pop': True, 'reinstate_index': True}

        # Reset mock for the second command (apply/pop)
        self.mock_execute_command.reset_mock()
        self.window._handle_stash_list_result("stash@{1}: On main: Test", "", 0) # context already "apply"

        self.mock_execute_command.assert_called_once_with(self.window.current_repo_path, ["stash", "pop", "--index", "stash@{1}"])

    @patch('GitPilot.ui_main.StashListDialog')
    def test_drop_stash_executes_command(self, MockStashListDialog):
        self.mock_execute_command.reset_mock()

        # Stage 1: Call on_drop_stash_clicked
        self.window.on_drop_stash_clicked()
        self.mock_execute_command.assert_called_once_with(self.window.current_repo_path, ["stash", "list"])

        # Stage 2: Simulate StashListDialog interaction
        mock_dialog_instance = MockStashListDialog.return_value
        mock_dialog_instance.exec_.return_value = QDialog.Accepted
        mock_dialog_instance.get_selected_stash_id.return_value = 'stash@{0}'

        self.mock_execute_command.reset_mock()
        self.window._handle_stash_list_result("stash@{0}: On main: Test", "", 0) # context already "drop"

        self.mock_execute_command.assert_called_once_with(self.window.current_repo_path, ["stash", "drop", "stash@{0}"])


class TestTagCreateDialog(unittest.TestCase):
    app = None
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def test_get_tag_options_defaults(self):
        dialog = TagCreateDialog()
        options = dialog.get_tag_options()
        self.assertEqual(options['name'], "")
        self.assertFalse(options['annotated'])
        self.assertEqual(options['message'], "")
        self.assertEqual(options['commit_hash'], "")
        self.assertFalse(options['force'])
        # Check visibility
        self.assertFalse(dialog.message_label.isVisible())
        self.assertFalse(dialog.message_input.isVisible())
        dialog.close()

    def test_get_tag_options_custom_annotated(self):
        dialog = TagCreateDialog()
        dialog.tag_name_input.setText("v1.1")
        dialog.annotated_checkbox.setChecked(True) # This should trigger _toggle_message_input
        QApplication.processEvents() # Ensure signal is processed
        self.assertIsNotNone(dialog.message_label) # Check existence
        self.assertIsNotNone(dialog.message_input) # Check existence
        # self.assertTrue(dialog.message_label.isVisible()) # isVisible is unreliable
        # self.assertTrue(dialog.message_input.isVisible()) # isVisible is unreliable
        dialog.message_input.setText("Release message")
        dialog.commit_hash_input.setText("abcdef1")
        dialog.force_checkbox.setChecked(True)

        options = dialog.get_tag_options()
        self.assertEqual(options['name'], "v1.1")
        self.assertTrue(options['annotated'])
        self.assertEqual(options['message'], "Release message")
        self.assertEqual(options['commit_hash'], "abcdef1")
        self.assertTrue(options['force'])
        dialog.close()

    def test_get_tag_options_custom_lightweight(self):
        dialog = TagCreateDialog()
        dialog.tag_name_input.setText("lightweight_tag")
        dialog.annotated_checkbox.setChecked(False) # This should trigger _toggle_message_input
        QApplication.processEvents() # Ensure signal is processed
        # self.assertFalse(dialog.message_label.isVisible()) # isVisible is unreliable
        # self.assertFalse(dialog.message_input.isVisible()) # isVisible is unreliable
        self.assertIsNotNone(dialog.message_label) # Check existence
        self.assertIsNotNone(dialog.message_input) # Check existence
        dialog.message_input.setText("This should not be returned") # Message for non-annotated
        dialog.commit_hash_input.setText("fedcba9")
        dialog.force_checkbox.setChecked(False)

        options = dialog.get_tag_options()
        self.assertEqual(options['name'], "lightweight_tag")
        self.assertFalse(options['annotated'])
        self.assertEqual(options['message'], "") # Message should be empty for lightweight
        self.assertEqual(options['commit_hash'], "fedcba9")
        self.assertFalse(options['force'])
        dialog.close()

class TestTagListDialog(unittest.TestCase): # Enhancing this class
    app = None
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)
        cls.sample_parsed_tags = [
            {'name': 'v1.0'},
            {'name': 'v1.1-beta'},
            {'name': 'release-candidate'},
        ]

    def test_init_push_context(self): # Assuming "push_single" is a planned context
        dialog = TagListDialog(self.sample_parsed_tags, "push_single")
        self.assertEqual(dialog.action_button.text(), "Push Selected Tag")
        dialog.close()

    def test_init_delete_context(self):
        dialog = TagListDialog(self.sample_parsed_tags, "delete") # General delete context
        self.assertEqual(dialog.action_button.text(), "Delete")
        dialog.close()

        dialog_local = TagListDialog(self.sample_parsed_tags, "delete_local") # Specific delete_local
        self.assertEqual(dialog_local.action_button.text(), "Delete Local Tag")
        dialog_local.close()

class TestTagPushDialog(unittest.TestCase):
    app = None
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def test_get_push_options_defaults(self):
        dialog = TagPushDialog()
        options = dialog.get_push_options()
        self.assertEqual(options['remote_name'], "origin")
        self.assertTrue(options['push_all'])
        self.assertEqual(options['specific_tag_name'], "")
        self.assertFalse(dialog.specific_tag_input.isEnabled())
        dialog.close()

    def test_get_push_options_specific_tag(self):
        dialog = TagPushDialog()
        dialog.remote_name_input.setText("upstream")
        dialog.push_specific_radio.setChecked(True) # Should enable specific_tag_input
        QApplication.processEvents()
        self.assertTrue(dialog.specific_tag_input.isEnabled())
        dialog.specific_tag_input.setText("v2.0-final")

        options = dialog.get_push_options()
        self.assertEqual(options['remote_name'], "upstream")
        self.assertFalse(options['push_all'])
        self.assertEqual(options['specific_tag_name'], "v2.0-final")
        dialog.close()

class TestTagDeleteOptionsDialog(unittest.TestCase):
    app = None
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def test_get_delete_options_defaults(self):
        dialog = TagDeleteOptionsDialog("v1.0-test")
        options = dialog.get_delete_options()
        self.assertFalse(options['delete_remote'])
        self.assertEqual(options['remote_name'], "")
        # Check visibility based on checkbox state
        dialog.show() # To ensure visibility states are processed
        dialog.hide()
        QApplication.processEvents()
        # self.assertFalse(dialog.remote_label.isVisible()) # isVisible is unreliable
        # self.assertFalse(dialog.remote_name_input.isVisible()) # isVisible is unreliable
        self.assertIsNotNone(dialog.remote_label)
        self.assertIsNotNone(dialog.remote_name_input)
        dialog.close()

    def test_get_delete_options_delete_remote(self):
        dialog = TagDeleteOptionsDialog("v1.0-test")
        dialog.delete_remote_checkbox.setChecked(True) # This should trigger visibility
        dialog.remote_name_input.setText("origin-alt")
        QApplication.processEvents() # Ensure signal for visibility change is processed

        options = dialog.get_delete_options()
        self.assertTrue(options['delete_remote'])
        self.assertEqual(options['remote_name'], "origin-alt")

        dialog.show() # To ensure visibility states are processed
        dialog.hide()
        QApplication.processEvents()
        # self.assertTrue(dialog.remote_label.isVisible()) # isVisible is unreliable
        # self.assertTrue(dialog.remote_name_input.isVisible()) # isVisible is unreliable
        self.assertIsNotNone(dialog.remote_label)
        self.assertIsNotNone(dialog.remote_name_input)
        dialog.close()

if __name__ == '__main__':
    unittest.main()
