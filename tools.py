from typing import Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
import jedi
from LSP import LSPToolKit

def get_code_jedi(definition, verbose=False):
    raw = definition.get_line_code(after=definition.get_definition_end_position()[0]-definition.get_definition_start_position()[0])
    start_num_line = definition.get_definition_start_position()[0] - 2 # jedi start from 1
    if not verbose:
        return raw
    else:
        results = []
        splited_raw = raw.split("\n")
        for idx, line in enumerate(splited_raw):
            new_line = str(start_num_line + 1) + " " + line
            results.append(new_line)
            start_num_line += 1
        return "\n".join(results)

def search_preliminary_inside_project(names, repo_path, num_result=2, verbose=False):
    """Get all matched identifiers from a repo
    
    Args:
        name (str): The name of the identifier
        repo_path (str): The path to the repo
        
    Returns:
        list: A list of matched identifiers
    """
    output_dict = {name: [] for name in names}
    project = jedi.Project(repo_path, environment_path="/datadrive05/huypn16/anaconda3/envs/knn-llm/bin/python3")
    for name in names:
        if not name.endswith(".py"):
            class_definitions = project.search(f"class {name}", all_scopes=True)
            function_definitions = project.search(f"def {name}", all_scopes=True)
            variable_definitions = project.search(name, all_scopes=True)
            idx = 0
            for definition in class_definitions:
                if definition.is_definition():
                    extracted_definition = {
                        "name": definition.name,
                        "full_name": definition.full_name,
                        "documentation": definition._get_docstring(),
                        "implementation": get_code_jedi(definition, verbose)
                    }
                    output_dict[name].append(extracted_definition)
                    if idx == num_result:
                        break
            
            idx = 0
            for definition in function_definitions:
                if definition.is_definition():
                    extracted_definition = {
                        "name": definition.name,
                        "full_name": definition.full_name,
                        "documentation": definition._get_docstring(),
                        "implementation": get_code_jedi(definition, verbose),
                    }
                    output_dict[name].append(extracted_definition)
                    if idx == num_result:
                        break
            
            idx = 0
            for definition in variable_definitions:
                extracted_definition = {
                    "name": definition.name,
                    "full_name": definition.full_name,
                    "documentation": None,
                    "implementation": definition.description,
                }
                output_dict[name].append(extracted_definition)
                if idx == num_result:
                    break
        else:
            definitions = project.search(name.replace(".py", ""))
            for definition in definitions:
                implementation = ""
                with open(definition.module_path, "r") as f:
                    implementation += f.read()
                extracted_definition = {
                    "name": name,
                    "implementation": implementation
                }
                output_dict[name].append(extracted_definition)
            
    return output_dict

class CodeSearchArgs(BaseModel):
    names: list[str] = Field(..., description="The names of the identifiers to search")

class CodeSearchTool(BaseTool):
    name = "search_preliminary_inside_project"
    description = "Useful when you want to find all matched identifiers (variable, function, class name) from a python repository, primarily used for class, function search"
    args_schema: Type[BaseModel] = CodeSearchArgs
    
    def _run(self, names: list[str], repo_path: str, verbose: bool = True):
        return search_preliminary_inside_project(names, repo_path, verbose=verbose)
    
    def _arun(self, names: list[str], repo_path: str):
        return NotImplementedError("Code Search Tool is not available for async run")

class GoToDefinitionArgs(BaseModel):
    word: str = Field(..., description="The name of the symbol to search")
    line: int = Field(..., description="The line number of the symbol to search")
    relative_path: str = Field(..., description="The relative path of the file containing the symbol to search")
    
class GoToDefinitionTool(BaseTool):
    name = "go_to_definition"
    description = """Useful when you want to find the definition of a symbol inside a code snippet if the current context is not cleared enough such as 
    0 import matplotlib.pyplot as plt
    1 class Directory(object):
    2
    3    def add_member(self, id, name):
    4        self.members[id] = plt.figure() we might want to find the definition of plt.figure() invoke with params ("figure", 6, 'test.py')"""
    args_schema = GoToDefinitionArgs
    
    def __init__(self, path, *args, **kwargs):
        super().__init__(path, *args, **kwargs)
        self.lsptoolkit = LSPToolKit(path)
    
    
    def _run(self, word: str, line: int, relative_path: str):
        return self.lsptoolkit.get_definition(word, relative_path, line, verbose=True)

    def _arun(self, word: str, line: int, relative_path: str):
        return NotImplementedError("Go To Definition Tool is not available for async run")

class FindAllReferencesTool(BaseTool):
    name = "find_all_references"
    description = "Useful when you want to find all references of a symbol inside a code snippet"
    args_schema = GoToDefinitionArgs
    
    def _run(self, word: str, line: int, relative_path: str):
        return self.lsptoolkit.get_references(word, relative_path, line, verbose=True)

    def _arun(self, word: str, line: int, relative_path: str):
        return NotImplementedError("Find All References Tool is not available for async run")