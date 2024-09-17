from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional
import subprocess
import selectors
import os
import time
import os.path as osp

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
    
class OpenFileToolForExecutorArgs(BaseModel):
    relative_file_path: str = Field(..., description="The relative path of the file we want to open")
    keyword: Optional[str] = Field(..., description="The keyword we want to search in the file")
    start_line: Optional[int] = Field(..., description="The starting line number of the file we want to open")
    end_line: Optional[int] = Field(..., description="The ending line number of the file we want to open")

class OpenFileToolForExecutor(BaseTool):
    """
    Tool for opening a file inside a repository.

    Args:
        path (str): The path to the repository.
        language (str): The language of the file.

    Attributes:
        name (str): The name of the tool.
        description (str): The description of the tool.
        args_schema (class): The schema for the tool's arguments.
        path (str): The path to the repository.

    Methods:
        _run(relative_file_path: str, max_new_line: int = 500) -> str:
            Runs the tool to open the specified file.

    """

    name = "open_file"
    description = """Useful when you want to open a file inside a repo for reading. If you have a keyword in mind, you can use it to search the keyword in the file. Otherwise, you can specify the start and end line to view the content of the file. The number of lines to show is limited at 200 for example (100:300) or (40:240).
    """
    args_schema = OpenFileToolForExecutorArgs
    path = ""
    
    def __init__(self, path, language=None):
        super().__init__()
        self.path = path
    
    def _run(self, relative_file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, keyword: Optional[str] = None, preview_size: int = 10, max_num_result: int = 5):
        """
        Opens the specified file and returns its content.

        Args:
            relative_file_path (str): The relative path to the file.
            max_new_line (int, optional): The maximum number of lines to include in the returned content. Defaults to 500.

        Returns:
            str: The content of the file.

        """
        abs_path = os.path.join(self.path, relative_file_path)
        try:
            if start_line is not None and end_line is not None:
                if end_line - start_line > 200:
                    return f"The number of lines to show is limited at 200, the requested number of lines is {end_line - start_line}, please specify the start and end line again (smaller |end_line-start_line|) or using keyword instead."
                source = open(abs_path, "r").read()
                lines = source.split("\n")
                source = "\n".join(lines[start_line:end_line]) 
            else:
                line_idx = []
                returned_source = []
                if osp.isfile(abs_path):
                    source = open(abs_path, "r").read()
                else:
                    return "Your path is not a file, please check the path again. Use the get_folder_structure tool to see the structure of the folder"
                lines = source.split("\n")
                for i, line in enumerate(lines):
                    if keyword in line:
                        line_idx.append(i)
                
                line_idx = line_idx[:max_num_result]
                
                if len(line_idx) == 0:
                    return "No keyword found in the file, please check the keyword again or use the start and end line instead"
                else:
                    for i in range(len(line_idx)):
                        expanded_source = "\n".join(lines[max(0, line_idx[i]-preview_size):min(len(lines), line_idx[i]+preview_size)])
                        returned_source.append(expanded_source)
                    return "The content of " + relative_file_path.replace(self.path, "") + " is:" + "\n".join(returned_source)
        except FileNotFoundError:
            return "File not found, please check the path again"
        except TypeError:
            source = open(abs_path, "r").read()
        return "The content of " + relative_file_path.replace(self.path, "") + " is: \n" + source