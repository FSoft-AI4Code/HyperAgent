import fire
import os
from repopilot.pilot import Setup
from repopilot import server
import uuid
import requests

class RepoPilotCLI:
    def __init__(self):
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", None)
        assert self.openai_api_key is not None, "Please provide an OpenAI API key."
        self.system = None

    def setup(self, local=False, remote=False, commit="", repo_folder="data/repos", local_agent=False, repo_path=None, lang=None):
        if local:
            print(f'Setting up local repo at {repo_path}')
        elif remote:
            print(f'Setting up remote repo at {repo_path}')
        system = Setup(repo=repo_path,
                commit=commit,
                openai_api_key=self.openai_api_key,
                local=local,
                language=lang,
                save_trajectories_path=None,
                headers=None,
                local_agent=local_agent)
        
        server_id=str(uuid.uuid4())
        server.serve(system, server_id=server_id)
        print(f'Server started at {server_id}')

    def query(self, query: str):
        assert self.system is not None, "Please setup a repo first."
        requests.post(f'http://localhost:server_id/query', json={'query': query})
    
    def turn_off(self, server_id: str):
        assert self.system is not None, "Please setup a repo first."
        server.systems.pop(server_id)
        
if __name__ == '__main__':
    fire.Fire(RepoPilotCLI)

