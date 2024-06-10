import os.path as osp
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
import subprocess
from typing import List, Optional
from repopilot.llm_multilspy import add_num_line
import os

class EditorArgs(BaseModel):
    relative_file_path: str = Field(..., description="The relative file path of the file that is need to be edited")
    start_line: int = Field(..., description="The starting line number of the block of code that is need to be replaced")
    end_line: int = Field(..., description="The ending line number of the block of code that is need to be replaced")
    patch: str = Field(..., description="A single block of code that you can replace into the file, make sure the code is syntactically correct, identation is correct, and the code resolved the request. Remember to add indentation to the patch if the original code position is indented.")

class EditorTool(BaseTool):
    name = "editor_file"
    description = """Useful when you want to edit a file inside a repo with a patch."""
    args_schema = EditorArgs
    path = ""
    
    def __init__(self, path, language=None):
        super().__init__()
        self.path = path
    
    def _run(self, relative_file_path: str, start_line:int = None, end_line: int = None, patch: str = None):
        """
        Opens the specified file and returns its content.

        Args:
            relative_file_path (str): The relative path to the file.
            max_new_line (int, optional): The maximum number of lines to include in the returned content. Defaults to 500.

        Returns:
            str: The content of the file.

        """
        if "/" not in relative_file_path:
            return "Invalid relative file path, please check the path again"
        
        with open(osp.join(self.path, relative_file_path), 'r') as file:
            lines = file.readlines()
            
        if end_line is  None or end_line is None:
            return "Please specify either start and end line"
        
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return "Invalid start and end line, please check the line number again"
        
        start_index = start_line - 1
        end_index = end_line
        updated_lines = lines[:start_index] + [patch + '\n'] + lines[end_index:]
        
        patch_file_path = osp.join(self.path, relative_file_path.split('.')[0] + '_patched.' + relative_file_path.split('.')[1])
        
        with open(patch_file_path, "w") as file:
            file.writelines(updated_lines)
        
        command_fix = f"autopep8 --in-place --aggressive {patch_file_path}"
        result = subprocess.run(command_fix, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        command = f"flake8 --isolated --select=F821,F822,F831,E111,E112,E113,E999,E902 {patch_file_path}"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        stderr_output = result.stderr
        stdout_output = result.stdout
        exit_code = result.returncode
        if exit_code == 0:
            with open(osp.join(self.path, relative_file_path), 'w') as file:
                file.writelines(updated_lines)
            os.remove(patch_file_path)
            return f"Successfully edited the file {relative_file_path} from line {start_line} to {end_line}"
        else:
            os.remove(patch_file_path)
            return f"Error executing command. Error message: {stdout_output + stderr_output}. Please read this error message carefully, reopen the file using open_file tool then try to fix the generated code."

class OpenFileToolForGeneratorArgs(BaseModel):
    relative_file_path: str = Field(..., description="The relative path of the file we want to open")
    keyword: Optional[str] = Field(..., description="The keyword we want to search in the file")
    start_line: Optional[int] = Field(..., description="The starting line number of the file we want to open")
    end_line: Optional[int] = Field(..., description="The ending line number of the file we want to open")

class OpenFileToolForGenerator(BaseTool):
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
    description = """Useful when you want to open a file inside a repo for editing. If you have a keyword in mind, you can use it to search the keyword in the file. Otherwise, you can specify the start and end line to view the content of the file. The number of lines to show is limited at 20 for example (100:120) or (240:260).
    """
    args_schema = OpenFileToolForGeneratorArgs
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
                if end_line - start_line > 70:
                    return f"The number of lines to show is limited at 70, the requested number of lines is {end_line - start_line}, please specify the start and end line again (smaller |end_line-start_line|) or using keyword instead."
                source = open(abs_path, "r").read()
                lines = source.split("\n")
                source = "\n".join(lines[start_line-1:end_line]) 
            else:
                line_idx = []
                returned_source = []
                source = open(abs_path, "r").read()
                lines = source.split("\n")
                for i, line in enumerate(lines):
                    if keyword in line:
                        line_idx.append(i)
                
                line_idx = line_idx[:max_num_result]
                
                if len(line_idx) == 0:
                    return "No keyword found in the file, please check the keyword again or use the start and end line instead"
                else:
                    import_source = add_num_line("\n".join(lines[:80]), 1)
                    for i in range(len(line_idx)):
                        expanded_source = "\n".join(lines[max(0, line_idx[i]-preview_size):min(len(lines), line_idx[i]+preview_size)])
                        expanded_source = add_num_line(expanded_source, max(1, line_idx[i]-preview_size)+1)
                        returned_source.append(expanded_source)
                    return "The content of " + relative_file_path.replace(self.path, "") + " is: \n" + import_source + "\n".join(returned_source)
        except FileNotFoundError:
            return "File not found, please check the path again"
        except TypeError:
            source = open(abs_path, "r").read()
        source = add_num_line(source, start_line)
        return "The content of " + relative_file_path.replace(self.path, "") + " is: \n" + source
    
