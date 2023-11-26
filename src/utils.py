from pathlib import Path
from git import Repo
import subprocess
import os

def clone_repo(repo, commit, root_dir, token, logger):
    """
    Clones a GitHub repository to a specified directory.

    Args:
        repo (str): The GitHub repository to clone.
        commit (str): The commit to checkout.
        root_dir (str): The root directory to clone the repository to.
        token (str): The GitHub personal access token to use for authentication.

    Returns:
        Path: The path to the cloned repository directory.
    """
    repo_dir = Path(root_dir, f"repo__{repo.replace('/', '__')}__commit__{commit}")
    
    if not repo_dir.exists():
        repo_url = f"https://{token}@github.com/{repo}.git"
        logger.info(f"Cloning {repo} {os.getpid()}")
        Repo.clone_from(repo_url, repo_dir)
        cmd = f"cd {repo_dir} && git reset --hard {commit} && git clean -fdxq"
        subprocess.run(
                cmd,
                shell=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
        )
    return root_dir + "/" + repo_dir.name

