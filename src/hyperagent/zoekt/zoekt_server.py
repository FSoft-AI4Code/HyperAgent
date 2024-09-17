import subprocess
from pathlib import Path
import requests
from typing import Optional
from contextlib import contextmanager
import time
import os
import signal

class ZoektServer:
    """
    Represents a Zoekt server for indexing and searching repositories.

    Args:
        language (str): The language of the repositories to be indexed.

    Attributes:
        index_path (str): The path to the Zoekt index.
        zoekt_server (subprocess.Popen): The subprocess representing the Zoekt web server.
        repo_path (str): The path to the repository.
        language (str): The language of the repositories.

    Methods:
        setup_index: Sets up the index for the repository.
        start_server: Starts the Zoekt web server.
        search: Performs a search on the Zoekt server.

    """

    def __init__(self, language, repo_path:Optional[str]=None, index_path:Optional[str]=None):
        self.index_path = index_path
        self.zoekt_server = None
        self.repo_path = repo_path
        self.language = language
    
    def setup_index(self, repo_path:str, root_index_path:str="/tmp/zoekt_tmp", index_path:Optional[str]=None):
        """
        Sets up the index for the repository.

        Args:
            repo_path (str): The path to the repository.
            index_path (str, optional): The path to the index directory. Defaults to ".zoekt_tmp".

        """
        zoekt_index_repo_path = f"{root_index_path}/{repo_path.split('/')[-1]}" 
        self.repo_path = repo_path
        self.index_path = zoekt_index_repo_path
        if not Path(zoekt_index_repo_path).is_dir():
            Path(zoekt_index_repo_path).mkdir(parents=True)
        subprocess.run(
            f"$GOPATH/bin/zoekt-index -index {zoekt_index_repo_path} -parallelism=1 {repo_path}",
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    
    @contextmanager
    def start_server(self):
        """
        Starts the Zoekt web server.

        Yields:
            ZoektServer: The current instance of the ZoektServer class.

        """
        self.zoekt_server = subprocess.Popen(
            f"$GOPATH/bin/zoekt-webserver -listen :6070 -index {self.index_path}",
            shell=True,
        )
        while True:
            try:
                response = requests.get("http://localhost:6070/health")  # replace with the correct endpoint if necessary
                if response.status_code == 200:
                    break
            except requests.exceptions.ConnectionError:
                time.sleep(1)  # wait for 1 second before trying again

        try:
            yield self
        finally:
            output = subprocess.check_output(["lsof", "-i", ":6070"])
            pid = int(output.split()[output.split().index(b'zoekt-web')+1])
            os.kill(pid, signal.SIGTERM)
            try:
                self.zoekt_server.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.zoekt_server.kill()
                
                
    def search(self, names, num_result=5):
        """
        Performs a search on the Zoekt server.

        Args:
            names (list): A list of names to search for.
            num_result (int, optional): The number of search results to retrieve. Defaults to 2.

        Returns:
            dict: A dictionary containing the search results for each name.

        """
        url = "http://localhost:6070/search"
        search_results = {name: [] for name in names}
        for name in names:
            params = {
                "q": name,
                "num": num_result,
                "format": "json"
            }

            response = requests.get(url, params=params)
            if response.status_code == 200:
                results = response.json()
                search_results[name] = results

        return search_results