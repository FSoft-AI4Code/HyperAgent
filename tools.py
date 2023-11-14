import os
from typing import Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
import jedi
from LSP import LSPToolKit
from openai import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.text_splitter import Language
from langchain.document_loaders.generic import GenericLoader
from langchain.document_loaders.parsers import LanguageParser
from tree_struct_display import DisplayablePath, tree
from pathlib import Path
from LSP import add_num_line

python_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.PYTHON, chunk_size=2000, chunk_overlap=200
)

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
                    idx += 1
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
                    idx += 1
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
                idx += 1
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
    description = """Useful when you want to find all matched identifiers (variable, function, class name) from a python repository, primarily used for class, function search. The results
    are mixed and not sorted by any criteria. So considered using this when you want to find all possible candidates for a given name. Otherwise, consider using other tools for more precise results"""
    args_schema: Type[BaseModel] = CodeSearchArgs
    path = ""
    verbose = False
    
    def __init__(self, path):
        super().__init__()
        self.path = path
    
    def _run(self, names: list[str], verbose: bool = True):
        return search_preliminary_inside_project(names, repo_path=self.path, verbose=verbose)
    
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
    path = ""
    lsptoolkit: LSPToolKit = None
    verbose = False
    
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.lsptoolkit = LSPToolKit(path)
    
    def _run(self, word: str, line: int, relative_path: str):
        return self.lsptoolkit.get_definition(word, relative_path, line, verbose=True)

    def _arun(self, word: str, line: int, relative_path: str):
        return NotImplementedError("Go To Definition Tool is not available for async run")

class FindAllReferencesArgs(BaseModel):
    word: str = Field(..., description="The name of the symbol to find all references")
    line: int = Field(..., description="The line number of the symbol to find all references")
    relative_path: str = Field(..., description="The relative path of the file containing the symbol to find all references")

class FindAllReferencesTool(BaseTool):
    name = "find_all_references"
    description = "Useful when you want to find all references of a symbol inside a code snippet"
    args_schema = FindAllReferencesArgs
    lsptoolkit: LSPToolKit = None
    openai_engine: OpenAI = None
    path = ""
    verbose = False
    
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.lsptoolkit = LSPToolKit(path)
        self.openai_engine = OpenAI(api_key="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")
    
    def _run(self, word: str, line: int, relative_path: str, reranking: bool = True, query: str = ""):
        results = self.lsptoolkit.get_references(word, relative_path, line, verbose=True)
        if reranking:
            return self.rerank(results, query)
        else:
            return results[:5]
        
    def _arun(self, word: str, line: int, relative_path: str):
        return NotImplementedError("Find All References Tool is not available for async run")
    
    def rerank(self, results, query):
        for item in results[:20]:
            item["score"] = self.similarity(query, item["implementation"])
        results = sorted(results, key=lambda x: x["score"], reverse=True)
        return results[:3]
    
    def similarity(self, query, implementation):
        prompt = "On the scale of 1 to 10, how relevant is the query to the implementation, only output the score?\n Query: " + query + "\n Implementation: " + implementation + "\n"
        completion = self.openai_engine.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a programmer who is very helpful in finding relevant code snippet with the query."},
                {"role": "user", "content": prompt}
            ]
        )
        return int(completion.choices[0]["message"]["content"])

class GetAllSymbolsArgs(BaseModel):
    path_to_file: str = Field(..., description="The relative path of the python file we want extract all symbols from.")

class GetAllSymbolsTool(BaseTool):
    name = "get_all_symbols"
    description = "Useful when you want to find all symbols (functions, classes) of a python file"
    args_schema = GetAllSymbolsArgs
    lsptoolkit: LSPToolKit = None
    path = ""
    verbose = False
    
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.lsptoolkit = LSPToolKit(path)
    
    def _run(self, path_to_file: str):
        try:
            return self.lsptoolkit.get_symbols(path_to_file, verbose=True)
        except IsADirectoryError:
            return "The relative path is a folder, please specify the file path instead. Consider using get_tree_structure to find the file name"
        except FileNotFoundError:
            return "The file is not found, please check the path again"
        except:
            return "Try to open_file tool to access the file instead"
    
    def _arun(self, relative_path: str):
        return NotImplementedError("Get All Symbols Tool is not available for async run")

class GetTreeStructureArgs(BaseModel):
    relative_path: str = Field(..., description="The relative path of the folder we want to explore")
    level: int = Field(..., description="The level of the tree structure we want to explore, prefer to use 2 (default) for a quick overview of the folder structure then use 3 for more details")

class GetTreeStructureTool(BaseTool):
    name = "get_tree_structure"
    description = """Useful when you want to explore the tree structure of a folder, good for initial exploration with knowing the parent folder name. Remember to provide the relative path correctly.
    Such as if you see and want to explore config folder inside the astropy folder, you should provide the relative path as astropy/config.
    """
    args_schema = GetTreeStructureArgs
    path = ""
    verbose = False
    
    def __init__(self, path):
        super().__init__()
        self.path = path
    
    def _run(self, relative_path: str, level: int = 2):
        abs_path = os.path.join(self.path, relative_path)
        # def is_not_hidden(path):
        #     return not path.name.startswith(".")
        # paths = DisplayablePath.make_tree(Path(abs_path), criteria=is_not_hidden)
        # structure_tree = ""
        # for path in paths:
        #     structure_tree += path.displayable() + "\n"
        # return structure_tree
        try:
            output = tree(abs_path, level=level)
            output = "The tree structure of " + relative_path + " is: \n" + output + "\nConsider using other tools to explore the content of the folder such as get_all_symbols, find_all_references, open_file, etc."
        except: 
            output = "Execution failed, please check the relative path again, likely the relative path lacks of parent name"
        return output
    
    def _arun(self, relative_path: str):
        return NotImplementedError("Get Tree Structure Tool is not available for async run")

class OpenFileArgs(BaseModel):
    relative_file_path: str = Field(..., description="The relative path of the file we want to open")

class OpenFileTool(BaseTool):
    name = "open_file"
    description = "Useful when you want to open a file inside a repo, use this tool only when it's very necessary, usually a main or server or training script. Consider combinining other alternative tools such as GetAllSymbols and CodeSearch to save the number of tokens for other cases."
    args_schema = OpenFileArgs
    path = ""
    
    def __init__(self, path):
        super().__init__()
        self.path = path
    
    def _run(self, relative_file_path: str):
        abs_path = os.path.join(self.path, relative_file_path)
        try:
            source = open(abs_path, "r").read()
        except FileNotFoundError:
            return "File not found, please check the path again"
        source = add_num_line(source, 0)
        return "The content of " + relative_file_path + " is: \n" + source
    
    def _arun(self, relative_path: str):
        return NotImplementedError("Open File Tool is not available for async run")

def main():
    path = "/datadrive05/huypn16/focalcoder/data/repos/repo__astropy__astropy__commit__3832210580d516365ddae1a62071001faf94d416"
    FindAllReferencesTool(path)
    GetAllSymbolsTool(path)