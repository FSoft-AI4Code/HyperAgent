import subprocess
from pathlib import Path
import requests
from contextlib import contextmanager
import time
import os
import signal

class ZoektServer:
    def __init__(self, language):
        self.index_path = None
        self.zoekt_server = None
        self.repo_path = None
        self.language = language
    
    def setup_index(self, repo_path, index_path=".zoekt_tmp"):
        zoekt_index_repo_path = f"{index_path}/{repo_path.split('/')[-1]}"
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
                
                
    def search(self, names, num_result=2):
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
    
if __name__ == "__main__":
    repo_path = "data/repos/repo__astropy__astropy__commit__bc80072326ba18732aa12eff11d5d76dcdd3e6d0"
    zs = ZoektServer()
    zs.setup_index(repo_path)
    with zs.start_server() as server:
        search_results = server.search(["sym:Kernel1D"], num_result=2)
    print(search_results)