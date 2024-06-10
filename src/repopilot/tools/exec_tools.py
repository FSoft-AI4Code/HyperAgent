from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional
import subprocess
import selectors
import os

class InteractiveBashSession:
    def __init__(self):
        self.sel = selectors.DefaultSelector()
        self.proc = None

    def initialize(self):
        # Open a subprocess with a Bash shell
        self.proc = subprocess.Popen(
            ['bash'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
        )

        # Register the subprocess stdout and stderr for non-blocking reading
        self.sel.register(self.proc.stdout, selectors.EVENT_READ, data='stdout')
        self.sel.register(self.proc.stderr, selectors.EVENT_READ, data='stderr')

    def command(self, command_str):
        if not self.proc:
            raise RuntimeError("Session not initialized. Call initialize() first.")
        
        # Send the command to the subprocess
        self.proc.stdin.write(command_str + "\n")
        self.proc.stdin.flush()

        output = []
        error = []

        # Use selectors to handle non-blocking I/O
        while True:
            events = self.sel.select(timeout=1)
            if not events:
                break
            for key, _ in events:
                data = key.data
                if data == 'stdout':
                    chunk = os.read(key.fileobj.fileno(), 4096).decode()
                    if chunk:
                        output.append(chunk)
                elif data == 'stderr':
                    chunk = os.read(key.fileobj.fileno(), 4096).decode()
                    if chunk:
                        error.append(chunk)

        if error:
            return ''.join(error)
        return ''.join(output)

    def close(self):
        if self.proc:
            # Clean up: close the subprocess and unregister the selector
            self.proc.stdin.close()
            self.proc.stdout.close()
            self.proc.stderr.close()
            self.sel.unregister(self.proc.stdout)
            self.sel.unregister(self.proc.stderr)
            self.proc.terminate()
            self.proc.wait()
            self.proc = None

class BashExecutorArgs(BaseModel):
    command: str = Field(..., description="The bash command to execute")
    
class BashExecutorTool(BaseTool):
    """Tool to run shell commands."""
    
    repo_dir: str = ""
    name: str = "terminal"
    bash_session: Optional[InteractiveBashSession] = None 
    """Name of tool."""

    description = f"Run shell commands on this linux machine."

    def __init__(self, repo_dir):
        super().__init__()
        self.repo_dir = repo_dir
        self.bash_session = InteractiveBashSession()
        self.bash_session.initialize()
        self.bash_session.command(f"cd {self.repo_dir}")

    def _run(
        self,
        command,
    ) -> str:
        """Run commands and return final output."""

        print(f"Executing command:\n {command}") 
        return self.bash_session.command(command)