from github import Github, GithubException

class GitHubManager:
    def __init__(self, token):
        """
        Initializes the GitHubManager with a GitHub Personal Access Token.
        Args:
            token (str): The GitHub PAT.
        """
        self.g = Github(token, per_page=100) # Added per_page for potentially many repos/branches
        self.user = None
        try:
            self.user = self.g.get_user()
            # Eagerly fetch login to confirm token validity early
            self.user.login
        except GithubException as e:
            # Handle cases like invalid token, rate limiting during initialization
            print(f"Error initializing GitHubManager: {e}") # Or raise a custom exception
            # Depending on desired behavior, could re-raise or set self.g to None
            # For now, let it proceed, methods will fail if self.g is problematic or user is None
            raise ConnectionError(f"Failed to connect to GitHub: {e.data.get('message', str(e))}")


    def get_repositories(self):
        """
        Fetches and returns a list of repository full names accessible by the token.
        Returns:
            list[str]: A list of repository full names (e.g., ['user/repo1', 'user/repo2']).
                       Returns an empty list if an error occurs or no repositories are found.
        """
        if not self.user:
            print("Error: GitHubManager not properly initialized or token is invalid.")
            return []
        try:
            repos = self.user.get_repos(type='all') # Fetch all types of repos user has access to
            return [repo.full_name for repo in repos]
        except GithubException as e:
            print(f"Error fetching repositories: {e}")
            return []
        except Exception as e: # Catch any other unexpected errors
            print(f"An unexpected error occurred while fetching repositories: {e}")
            return []

    def get_branches(self, repo_full_name):
        """
        Fetches and returns a list of branches for the specified repository.
        Each branch is a dictionary with 'name' and 'last_commit_date'.
        Args:
            repo_full_name (str): The full name of the repository (e.g., 'user/repo1').
        Returns:
            list[dict]: A list of dictionaries, e.g.,
                        [{'name': 'main', 'last_commit_date': '2023-01-01'}].
                        Returns an empty list if an error occurs.
        """
        if not self.user: # Check if user object is available
            print("Error: GitHubManager not properly initialized or token is invalid.")
            return []
        try:
            repo = self.g.get_repo(repo_full_name)
            branches_data = []
            for branch in repo.get_branches():
                commit = branch.commit
                # The commit object itself doesn't directly have a simple date string.
                # We need to access commit.commit.committer.date
                # PyGithub's commit object has a `commit` attribute which is a GitCommit object
                # This GitCommit object has `committer` which is a GitCommitter object with a `date` attribute.
                commit_date = commit.commit.committer.date.strftime('%Y-%m-%d')
                branches_data.append({'name': branch.name, 'last_commit_date': commit_date})
            return branches_data
        except GithubException as e:
            # Specific handling for common errors if desired
            if e.status == 404:
                print(f"Error: Repository '{repo_full_name}' not found or access denied.")
            elif e.status == 401:
                print(f"Error: Unauthorized access to '{repo_full_name}'. Check your token and permissions.")
            else:
                print(f"GitHub API error fetching branches for '{repo_full_name}': {e}")
            return []
        except Exception as e: # Catch any other unexpected errors
            print(f"An unexpected error occurred while fetching branches for '{repo_full_name}': {e}")
            return []

    def delete_branch(self, repo_full_name: str, branch_name: str) -> tuple[bool, str]:
        """
        Deletes a branch from the specified GitHub repository.

        Args:
            repo_full_name (str): The full name of the repository (e.g., 'user/repo1').
            branch_name (str): The name of the branch to delete.

        Returns:
            tuple[bool, str]: A tuple containing a boolean indicating success (True) or failure (False),
                              and a message string describing the outcome.
        """
        if not self.user:
            msg = "Error: GitHubManager not properly initialized or token is invalid."
            print(msg)
            return False, msg

        try:
            repo = self.g.get_repo(repo_full_name)
            ref_path = f"heads/{branch_name}" # PyGithub expects "heads/branch" not "refs/heads/branch" for get_git_ref argument related to branches

            # Check if the branch is the default branch, prevent deletion
            if branch_name == repo.default_branch:
                msg = f"Cannot delete the default branch '{branch_name}'."
                print(f"Attempted to delete default branch: {branch_name} in repo {repo_full_name}")
                return False, msg

            ref = repo.get_git_ref(ref_path) # This gets the ref object
            ref.delete()
            msg = f"Branch '{branch_name}' successfully deleted from '{repo_full_name}'."
            print(msg)
            return True, msg
        except GithubException as e:
            if e.status == 404 or e.status == 422: # 404 for not found, 422 if ref is not a branch ref or other issues
                # PyGithub might raise 422 if trying to get a ref that doesn't start with "refs/"
                # or if the ref is not found but it's not a simple 404.
                # Let's try to get ref with "refs/heads/" to be more specific if the first attempt fails,
                # as this is what GitHub API documentation usually refers to for branch deletion.
                # However, PyGithub's get_git_ref for deleting is usually just "heads/branchname".
                # The error "Reference does not exist" often comes as a 422 from `ref.delete()` if ref was obtained but points to non-deletable thing
                # or if it's already deleted.
                msg = f"Error deleting branch '{branch_name}' from '{repo_full_name}': Branch not found or already deleted (Status: {e.status})."
            elif e.status == 403:
                msg = f"Error deleting branch '{branch_name}' from '{repo_full_name}': Forbidden. Check token permissions. (Status: {e.status})"
            else:
                msg = f"Error deleting branch '{branch_name}' from '{repo_full_name}': {e.data.get('message', str(e))} (Status: {e.status})"
            print(msg)
            return False, msg
        except Exception as e:
            msg = f"An unexpected error occurred while deleting branch '{branch_name}' from '{repo_full_name}': {str(e)}"
            print(msg)
            return False, msg

if __name__ == '__main__':
    # Example Usage (requires a valid token and repo name for testing)
    # Replace 'YOUR_TOKEN' with a real GitHub PAT and 'USER/REPO' with a real repo
    # This part will not run during the subtask execution but is useful for local testing.
    print("GitHub Utils module")
    # try:
    #     # IMPORTANT: Do not commit actual tokens to version control.
    #     # Use environment variables or a local config for real testing.
    #     # token = "YOUR_ACTUAL_GITHUB_TOKEN"
    #     # if token == "YOUR_ACTUAL_GITHUB_TOKEN":
    #     #     print("Please replace 'YOUR_ACTUAL_GITHUB_TOKEN' with your actual GitHub token to test.")
    #     # else:
    #     #     manager = GitHubManager(token=token)
    #     #     print("Fetching repositories...")
    #     #     repos = manager.get_repositories()
    #     #     if repos:
    #     #         print(f"Found {len(repos)} repositories:")
    #     #         for r in repos[:5]: # Print first 5
    #     #             print(f"  - {r}")
    #     #
    #     #         # Test get_branches with the first repository found
    #     #         if repos:
    #     #             test_repo_full_name = repos[0]
    #     #             print(f"Fetching branches for {test_repo_full_name}...")
    #     #             branches = manager.get_branches(test_repo_full_name)
    #     #             if branches:
    #     #                 print(f"Found {len(branches)} branches in {test_repo_full_name}:")
    #     #                 for b in branches[:5]: # Print first 5
    #     #                     print(f"  - {b['name']} (Last commit: {b['last_commit_date']})")
    #     #             else:
    #     #                 print(f"No branches found or error fetching branches for {test_repo_full_name}.")
    #     #     else:
    #     #         print("No repositories found or error during fetching.")
    # except ConnectionError as ce:
    #    print(f"Test failed: {ce}")
    # except Exception as e:
    #    print(f"An unexpected error occurred during testing: {e}")
