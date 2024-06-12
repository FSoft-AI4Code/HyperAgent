from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional
import subprocess
import selectors
import os
import time

class InteractiveShellSession:
    def __init__(self, shell='zsh'):
        self.shell = shell
        self.sel = selectors.DefaultSelector()
        self.proc = None

    def initialize(self):
        # Open a subprocess with the specified shell
        self.proc = subprocess.Popen(
            [self.shell], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
        )

        # Register the subprocess stdout and stderr for non-blocking reading
        self.sel.register(self.proc.stdout, selectors.EVENT_READ, data='stdout')
        self.sel.register(self.proc.stderr, selectors.EVENT_READ, data='stderr')

    def command(self, command_str):
        if not self.proc:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        # Unique marker to detect end of command execution
        marker = "END_OF_COMMAND_{}".format(time.time())
        full_command = f"{command_str} && echo {marker}\n"
        command_done = False

        # Send the command to the subprocess
        self.proc.stdin.write(full_command)
        self.proc.stdin.flush()

        output = []
        error = []
        time.sleep(5)

        while True:
            events = self.sel.select(timeout=0.1)
            for key, _ in events:
                data = key.data
                if data == 'stdout':
                    chunk = os.read(key.fileobj.fileno(), 4096).decode()
                    if chunk:
                        output.append(chunk)
                        if marker in chunk:
                            command_done = True
                            break
                elif data == 'stderr':
                    chunk = os.read(key.fileobj.fileno(), 4096).decode()
                    if chunk:
                        error.append(chunk)

            if command_done:
                break

        full_output = ''.join(output)
        clean_output = full_output.replace(marker, '').strip()

        if error:
            return ''.join(error)
        return clean_output

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
    bash_session: Optional[InteractiveShellSession] = None 
    """Name of tool."""

    description = f"Run shell commands on this linux machine."

    def __init__(self, repo_dir):
        super().__init__()
        self.repo_dir = repo_dir
        self.bash_session = InteractiveShellSession()
        self.bash_session.initialize()
        self.bash_session.command(f"cd {self.repo_dir}")
        self.bash_session.command(f"source ~/.zshrc")

    def _run(
        self,
        command,
    ) -> str:
        """Run commands and return final output."""

        print(f"Executing command:\n {command}") 
        return self.bash_session.command(command)