import fire
import os
from repopilot.pilot import Setup
from repopilot import server
import socketserver
import requests

def find_free_port():
    with socketserver.TCPServer(("localhost", 0), None) as s:
        free_port = s.server_address[1]
    return free_port

class RepoPilotCLI:
    def __init__(self):
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", None)
        assert self.openai_api_key is not None, "Please provide an OpenAI API key."

    def setup(self, local=False, remote=False, commit="", repo_folder="data/repos", local_agent=False, repo_path=None, lang=None):
        assert not (local and remote), "Please choose either local or remote."
        assert repo_path is not None, "Please provide a repo path."
        assert lang is not None, "Please provide a language."
            
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
        port = find_free_port()
        print(f'Server started at {port}')
        server.serve(system, port)

    def query(self, query: str, port: int):
        data = {
            "query": query, 
        }
        url = f"http://localhost:{port}/query"
        # Use the requests.post() function to send the POST request
        response = requests.post(url, json=data)
        return response

def main():
    fire.Fire(RepoPilotCLI)

if __name__ == '__main__':
    main()

