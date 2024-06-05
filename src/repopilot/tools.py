import os
import numpy as np
from typing import Type, List, Optional
from pydantic import BaseModel, Field
from langchain.tools import BaseTool, Tool
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.generic import GenericLoader
from repopilot.langchain_parsers.parsers import LanguageParser
from .get_repo_struct import visualize_tree
from .llm_multilspy import LSPToolKit, add_num_line
from .code_search import search_elements_inside_project
from .zoekt.zoekt_server import ZoektServer
from .utils import identify_extension, find_non_utf8_files
from langchain_community.embeddings.cohere import CohereEmbeddings
from langchain_community.vectorstores import Chroma
from repopilot.utils import get_symbol_verbose, get_symbol_with_keyword
import jedi
import platform
import uuid
from repopilot.multilspy import lsp_protocol_handler
from repopilot.constants import SEMANTIC_CODE_SEARCH_DB_PATH
import os.path as osp
import subprocess

def _get_default_bash_process():
    """Get default bash process."""
    try:
        from langchain_experimental.llm_bash.bash import BashProcess
    except ImportError:
        raise ImportError(
            "BashProcess has been moved to langchain experimental."
            "To use this tool, install langchain-experimental "
            "with `pip install langchain-experimental`."
        )
    return BashProcess(return_err_output=True)

def _get_platform() -> str:
    """Get platform."""
    system = platform.system()
    if system == "Darwin":
        return "MacOS"
    return system

class CodeSearchArgs(BaseModel):
    names: list[str] = Field(..., description="The names of the identifiers to search")

class CodeSearchTool(BaseTool):
    """
    A tool for searching for matched identifiers (variable, function, class name) from a Python repository.
    Primarily used for class and function search. The results are mixed and not sorted by any criteria.

    Args:
        path (str): The path to the Python repository.
        language (str): The programming language of the repository.

    Attributes:
        name (str): The name of the tool.
        description (str): A description of the tool.
        args_schema (Type[BaseModel]): The schema for the tool's arguments.
        path (str): The path to the Python repository.
        verbose (bool): Whether to display verbose output.
        language (str): The programming language of the repository.
        backend (jedi.Project | ZoektServer): The search engine backend.

    Methods:
        _run(names: list[str], verbose: bool = True) -> List[SearchResult]:
            Run the code search tool synchronously.
        _arun(names: list[str], verbose: bool = True) -> List[SearchResult]:
            Run the code search tool asynchronously (not implemented).

    """

    name = "code_search"
    description = """Useful when you want to find all matched primary symbols (function, class name) in a repository. You want to quickly find a class or function like 'some_function' function."""
    args_schema: Type[BaseModel] = CodeSearchArgs
    path = ""
    verbose = False
    language = "python"
    backend: jedi.Project | ZoektServer = None
    
    def __init__(self, path: str, language: str, index_path: Optional[str] = None, build: bool = False):
        super().__init__()
        self.path = path
        self.language = language
        if build:
            if not os.path.exists(index_path):
                os.makedirs(index_path)
            self.backend = ZoektServer(language)
            self.backend.setup_index(path, index_path=index_path)
        else:
            self.backend = ZoektServer(language, repo_path=path, index_path=index_path)

    
    def _run(self, names: list[str], verbose: bool = True):
        try:
            result = search_elements_inside_project(names, self.backend, verbose=verbose, language=self.language)
            return result
        except TypeError:
            return "The search engine is not available, please check the word again, the word should be identifier only"
    def _arun(self, names: list[str], verbose: bool = True):
        return NotImplementedError("Code Search Tool is not available for async run")

class GoToDefinitionArgs(BaseModel):
    word: str = Field(..., description="The name of the symbol to search")
    line: int = Field(..., description="The line number of the symbol to search")
    relative_path: str = Field(..., description="The relative path of the file containing the symbol to search")
    
class GoToDefinitionTool(BaseTool):
    """
    A tool for finding the definition of a symbol inside a code snippet.

    Args:
        path (str): The path to the code snippet.
        language (str): The programming language of the code snippet.

    Attributes:
        name (str): The name of the tool.
        description (str): A description of the tool.
        args_schema (class): The schema for the tool's arguments.
        path (str): The path to the code snippet.
        lsptoolkit (LSPToolKit): An instance of the LSPToolKit class.
        language (str): The programming language of the code snippet.
        verbose (bool): Flag indicating whether to display verbose output.

    Methods:
        _run(word: str, line: int, relative_path: str) -> str: Runs the tool to find the definition of a symbol.

    """

    name = "go_to_definition"
    description = """Useful when you want to find the definition of an identifier inside a code snippet that you saw. This can be applied into variable."""
    args_schema = GoToDefinitionArgs
    path = ""
    lsptoolkit: LSPToolKit = None
    language = "python"
    verbose = False
    
    def __init__(self, path: str, language: str):
        super().__init__()
        self.path = path
        self.lsptoolkit = LSPToolKit(path, language)
    
    def _run(self, word: str, relative_path: str, line: int = None, verbose: bool = True):
        """
        Runs the tool to find the definition of a symbol.

        Args:
            word (str): The symbol to find the definition of.
            line (int): The line number of the symbol in the code snippet.
            relative_path (str): The relative path of the code snippet.
            verbose (bool, optional): Whether to display verbose output. Defaults to True.
            
        Returns:
            str: The definition of the symbol.

        """
        if line is not None:
            line = int(line)
        return self.lsptoolkit.get_definition(word, relative_path, line, verbose=verbose)


class FindAllReferencesArgs(BaseModel):
    word: str = Field(..., description="The name of the symbol to find all references")
    relative_file_path: str = Field(..., description="The relative path of the file containing the symbol to find all references")
    line: int = Field(..., description="The line number of the symbol to find all references")
    
class FindAllReferencesTool(BaseTool):
    """
    Tool for finding all references of a target symbol inside a project.
    """

    name = "find_all_references"
    description = """Given a code snippet that contains target symbol, find all references of this symbol inside the project."""
    args_schema = FindAllReferencesArgs
    lsptoolkit: LSPToolKit = None
    path = ""
    verbose = False
    language = "python"
    
    def __init__(self, path: str, language: str):
        super().__init__()
        self.path = path
        self.lsptoolkit = LSPToolKit(path, language)
    
    def _run(self, word: str, relative_file_path: str, line: Optional[int] = None, num_results: int = 10):
        """
        Run the tool to find all references of a target symbol.

        Args:
            word (str): The target symbol to find references for.
            line (int): The line number where the target symbol is located.
            relative_path (str): The relative path of the file containing the target symbol.
            query (str, optional): The query used for reranking. Defaults to "".

        Returns:
            Union[str, List[str]]: The list of references or an error message if an exception occurs.
        """
        if "/" not in relative_file_path:
            return "Invalid relative file path, please check the path again"
        
        abs_path = os.path.join(self.path, relative_file_path)
        
        is_dir = os.path.isdir(abs_path)
        if is_dir:
            return "The relative path is a folder, please specify the file path instead. Consider using get_tree_structure to find the file name then use this tool one file path at a time"
        
        file_exists = os.path.exists(abs_path)
        if not file_exists:
            return "The file is not found, please check the path again. If you want to find the file, consider using get_tree_structure to find the file name then use this tool one file path at a time or recall your memory."
        
        results = self.lsptoolkit.get_references(word, relative_file_path, line, verbose=True)
            
        return results[:num_results]

class GetAllSymbolsArgs(BaseModel):
    path_to_file: str = Field(..., description="The path of the python file we want extract all symbols from.")
    keyword: Optional[str] = Field(None, description="The keyword we want to search among the symbols. Optional.")
    
class GetAllSymbolsTool(BaseTool):
    """
    A tool for finding all symbols (functions, classes, methods) of a Python/Rust/C#/Java file.

    Args:
        path (str): The path to the source file.
        language (str, optional): The language of the file. Defaults to "python".
    """

    name = "get_all_symbols"
    description = "Useful when you want to find all symbols (functions, classes, methods) of source files. If you want to look for a specific keyword, specify it, otherwise if you want to see all the symbols, do not provide the keyword. Prioritize using keyword to shorten the search."
    args_schema = GetAllSymbolsArgs
    lsptoolkit: LSPToolKit = None
    path = ""
    verbose = False
    language = "python"
    
    def __init__(self, path: str, language: str ="python"):
        super().__init__()
        self.path = path
    
    def _run(self, path_to_file: str, keyword: Optional[str] = None):
        """
        Run the tool to get all symbols of a Python file.

        Args:
            path_to_file (str): The path to the Python file.
            preview_size (int, optional): The number of symbols to preview. Defaults to 5.

        Returns:
            Union[List[str], str]: The list of symbols or an error message.
        """
        try:
            return get_symbol_verbose(osp.join(self.path, path_to_file), self.path, keyword)
        except IsADirectoryError:
            return "The relative path is a folder, please specify the file path instead. Consider using get_tree_structure to find the file name then use this tool one file path at a time"
        except FileNotFoundError:
            return "The file is not found, please check the path again"
        except lsp_protocol_handler.server.Error:
            return "Internal error, please use other tool"

class GetTreeStructureArgs(BaseModel):
    relative_path: str = Field(..., description="The relative path of the folder we want to explore")

class GetTreeStructureTool(BaseTool):
    """
    Tool for exploring the tree structure of a folder.

    This tool is useful when you want to explore the tree structure of a folder. It provides the ability to visualize the tree structure of a given folder path.

    Args:
        path (str): The base path of the folder.
        language (str): The programming language of the project.

    Attributes:
        name (str): The name of the tool.
        description (str): The description of the tool.
        args_schema (Type): The argument schema for the tool.
        path (str): The base path of the folder.
        verbose (bool): Flag indicating whether to display verbose output.

    Methods:
        _run(relative_path: str, level: int = 2) -> str:
            Runs the tool to visualize the tree structure of a folder.
        _arun(relative_path: str) -> NotImplementedError:
            Asynchronous version of the tool (not available).

    """

    name = "get_folder_structure"
    description = """Useful when you want to explore the tree structure of a folder, good for initial exploration with knowing the parent folder name. Remember to provide the relative path correctly.
    """
    args_schema = GetTreeStructureArgs
    path = ""
    verbose = False
    
    def __init__(self, path, language=None):
        super().__init__()
        self.path = path
    
    def _run(self, relative_path: str):
        abs_path = os.path.join(self.path, relative_path)
        try:
            output = visualize_tree(abs_path, level=1)
            output = "The tree structure of " + relative_path + " is: \n" + output
        except: 
            output = "Execution failed, please check the relative path again, likely the relative path lacks of prefix directory name"
        return output

class OpenFileArgs(BaseModel):
    relative_file_path: str = Field(..., description="The relative path of the file you want to open")
    keywords: List[str] = Field(..., description="The list of keywords you want to search in the file")
    start_line: Optional[int] = Field(..., description="The starting line number of the file you want to open")
    end_line: Optional[int] = Field(..., description="The ending line number of the file you want to open")
class OpenFileTool(BaseTool):
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
    description = """Useful when you want to open a file inside a repo. If you have a keyword in mind, you can use it to search the keyword in the file. Otherwise, you can specify the start and end line to view the content of the file. The number of lines to show is limited at 20 for example (100:120) or (240:260).
    """
    args_schema = OpenFileArgs
    path = ""
    
    def __init__(self, path, language=None):
        super().__init__()
        self.path = path
    
    def _run(self, relative_file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, keywords: Optional[List[str]] = [], preview_size: int = 10, max_num_result: int = 5):
        """
        Opens the specified file and returns its content.

        Args:
            relative_file_path (str): The relative path to the file.
            max_new_line (int, optional): The maximum number of lines to include in the returned content. Defaults to 500.

        Returns:
            str: The content of the file.

        """
        if len(keywords) == 0 and start_line is None and end_line is None:
            return "Please specify the keyword or start and end line to view the content of the file."
        
        abs_path = os.path.join(self.path, relative_file_path)
        try:
            if start_line is not None and end_line is not None and len(keywords) == 0:
                if end_line - start_line > 40:
                    return f"The number of lines to show is limited at 40, the requested number of lines is {end_line - start_line}, please specify the start and end line again or using keyword instead. For example {start_line}:{start_line+40}"
                source = open(abs_path, "r").read()
                lines = source.split("\n")
                source = "\n".join(lines[start_line-1:end_line]) 
            else:
                out_str = "The content of " + relative_file_path.replace(self.path, "") + " is: \n"
                for keyword in keywords:
                    out_str += f"Results for keyword: {keyword}\n"
                    line_idx = []
                    returned_source = []
                    source = open(abs_path, "r").read()
                    lines = source.split("\n")
                    for i, line in enumerate(lines):
                        if keyword in line:
                            line_idx.append(i)
                    
                    
                    line_idx = line_idx[:max_num_result]
                    
                    if len(line_idx) == 0:
                        out_str += f"No keyword found in the file, please check the keyword again or use the start and end line instead for this keyword {keyword}"
                    else:
                        for i in range(len(line_idx)):
                            expanded_source = "\n".join(lines[max(0, line_idx[i]-preview_size):min(len(lines), line_idx[i]+preview_size)])
                            expanded_source = add_num_line(expanded_source, max(1, line_idx[i]-preview_size)+1)
                            returned_source.append(expanded_source)
                        out_str += "\n".join(returned_source)
                return out_str
            # else:
            #     out_str = "The content of " + relative_file_path.replace(self.path, "") + f"with keyword {keywords} is: \n"
            #     for keyword in keywords:
            #         out_str += get_symbol_with_keyword(abs_path, self.path, keyword)
            #     out_str += "\n"
            #     return out_str
        except FileNotFoundError:
            return "File not found, please check the path again"
        source = add_num_line(source, start_line)
        return "The content of " + relative_file_path.replace(self.path, "") + " is: \n" + source


class SemanticCodeSearchTool(Tool):
    def __init__(self, path, language: str="python", db_path: Optional[str] = None, build: bool = False):
        """Semantic code search tool allows you to search for code using natural language. It's useful when the query is a sentance, semantic and vague. If exact search such as code search failed after multiple tries, try this

        Args:
            path (_type_): relative path to the repo
            language (str, optional): we have 4 options: python, rust, csharp, java. Defaults to "python".
        """
        if db_path == None:
            # randomize db_path
            db_path = os.path.join(SEMANTIC_CODE_SEARCH_DB_PATH, str(uuid.uuid4()))
        if not os.path.exists(db_path):
            os.makedirs(db_path)
        if build:
            extension = identify_extension(language)
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=language, chunk_size=400, chunk_overlap=100
            )

            non_utf8_files = find_non_utf8_files(path)

            loader = GenericLoader.from_filesystem(
                path,
                suffixes=[extension],
                exclude=non_utf8_files,
                parser=LanguageParser(language=language, parser_threshold=500),
                show_progress=True,
            )
            
            documents = loader.load()
            texts = splitter.split_documents(documents)
            db = Chroma.from_documents(texts, CohereEmbeddings(model="embed-english-light-v3.0", cohere_api_key=os.getenv("COHERE_API_KEY")), persist_directory=db_path)
            db.persist()
        else:
            db = Chroma(persist_directory=db_path, embedding_function=CohereEmbeddings(model="embed-english-light-v3.0", cohere_api_key=os.getenv("COHERE_API_KEY")))
        
        def semantic_code_search(query):
            retrieved_docs = db.similarity_search(query, k=3)
            return [doc.page_content for doc in retrieved_docs]
        
        super().__init__(
            name="Semantic Code Search",
            func=semantic_code_search,
            description="useful for when the query is a sentance, semantic and vague. If exact search such as code search failed after multiple tries, try this",
        )

class BashExecutorArgs(BaseModel):
    command: str = Field(..., description="The bash command to execute")
    
class BashExecutorTool(BaseTool):
    """Tool to run shell commands."""
    
    repo_dir = ""

    process = _get_default_bash_process()
    """Bash process to run commands."""

    name = "terminal"
    """Name of tool."""

    description = f"Run shell commands on this {_get_platform()} machine."
    """Description of tool."""

    args_schema: Type[BaseModel] = BashExecutorArgs
    """Schema for input arguments."""

    ask_human_input: bool = False
    """
    If True, prompts the user for confirmation (y/n) before executing 
    a command generated by the language model in the bash shell.
    """
    
    def __init__(self, repo_dir):
        super().__init__()
        self.repo_dir = repo_dir

    def _run(
        self,
        commands,
    ) -> str:
        """Run commands and return final output."""

        print(f"Executing command:\n {commands}") 
        commands = f"cd {self.repo_dir} && " + commands
        try:
            if self.ask_human_input:
                user_input = input("Proceed with command execution? (y/n): ").lower()
                if user_input == "y":
                    return self.process.run(commands)
                else:
                    return "Invalid input. User aborted command execution."
            else:
                return self.process.run(commands)

        except Exception as e:
            return f"Error during command execution: {e}"


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
    args_schema = OpenFileArgs
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
        source = add_num_line(source, start_line)
        return "The content of " + relative_file_path.replace(self.path, "") + " is: \n" + source