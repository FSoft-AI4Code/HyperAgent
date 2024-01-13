import os
import numpy as np
from typing import Type, List, Optional
from pydantic import BaseModel, Field
from langchain.tools import BaseTool, Tool
from openai import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders.generic import GenericLoader
from repopilot.langchain_parsers.parsers import LanguageParser
from .get_repo_struct import visualize_tree
from .llm_multilspy import LSPToolKit, add_num_line
from .code_search import search_elements_inside_project
from .zoekt.zoekt_server import ZoektServer
from .utils import identify_extension, get_file_paths_recursive, find_most_matched_string
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from repopilot.utils import get_env_path
import jedi
import uuid
from codetext.utils import build_language
from repopilot.multilspy import lsp_protocol_handler
from repopilot.constants import SEMANTIC_CODE_SEARCH_DB_PATH

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
    description = """Useful when you want to find all matched identifiers (variable, function, class name) from a python repository, primarily used for class, function search. The results
    are mixed and not sorted by any criteria. So considered using this when you want to find all possible candidates for a given name. Otherwise, consider using other tools for more precise results"""
    args_schema: Type[BaseModel] = CodeSearchArgs
    path = ""
    verbose = False
    language = "python"
    backend: jedi.Project | ZoektServer = None
    
    def __init__(self, path: str, language: str, index_path: Optional[str] = None, build: bool = False):
        super().__init__()
        self.path = path
        self.language = language
        if language != "python":
            "Code Search Tool will switch to use Zoekt non-python search engine, this may not be accurate as Jedi"
            if build:
                if not os.path.exists(index_path):
                    os.makedirs(index_path)
                self.backend = ZoektServer(language)
                self.backend.setup_index(path, index_path=index_path)
                build_language(language)
            else:
                self.backend = ZoektServer(language, repo_path=path, index_path=index_path)

        elif language == "python":
            "Code Search Tool will switch to use Jedi python search engine, this provides more fine-grained results such as implementation, docstring, etc."
            self.backend = jedi.Project(path, environment_path=get_env_path())
    
    def _run(self, names: list[str], verbose: bool = True):
        return search_elements_inside_project(names, self.backend, verbose=verbose, language=self.language)
    
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
    description = """Useful when you want to find the definition of a symbol inside a code snippet if the current context is not cleared enough such as 
    0 import matplotlib.pyplot as plt
    1 class Directory(object):
    2
    3    def add_member(self, id, name):
    4        self.members[id] = plt.figure() we might want to find the definition of plt.figure() invoke with params ("figure", 4, 'test.py')"""
    args_schema = GoToDefinitionArgs
    path = ""
    lsptoolkit: LSPToolKit = None
    language = "python"
    verbose = False
    
    def __init__(self, path: str, language: str):
        super().__init__()
        self.path = path
        self.lsptoolkit = LSPToolKit(path, language)
    
    def _run(self, word: str, line: int, relative_path: str, verbose: bool = True):
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
        return self.lsptoolkit.get_definition(word, relative_path, line, verbose=verbose)


class FindAllReferencesArgs(BaseModel):
    word: str = Field(..., description="The name of the symbol to find all references")
    line: int = Field(..., description="The line number of the symbol to find all references")
    relative_path: str = Field(..., description="The relative path of the file containing the symbol to find all references")

class FindAllReferencesTool(BaseTool):
    """
    Tool for finding all references of a target symbol inside a project.
    """

    name = "find_all_references"
    description = """Given a code snippet that contains target symbol, find all references of this symbol inside the project.
    """
    args_schema = FindAllReferencesArgs
    lsptoolkit: LSPToolKit = None
    openai_engine: OpenAI = None
    path = ""
    verbose = False
    language = "python"
    
    def __init__(self, path: str, language: str):
        super().__init__()
        self.path = path
        self.lsptoolkit = LSPToolKit(path, language)
        self.openai_engine = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def _run(self, word: str, line: int, relative_path: str, reranking: bool = False, query: str = ""):
        """
        Run the tool to find all references of a target symbol.

        Args:
            word (str): The target symbol to find references for.
            line (int): The line number where the target symbol is located.
            relative_path (str): The relative path of the file containing the target symbol.
            reranking (bool, optional): Whether to rerank the results based on a query. Defaults to False.
            query (str, optional): The query used for reranking. Defaults to "".

        Returns:
            Union[str, List[str]]: The list of references or an error message if an exception occurs.
        """
        try:
            results = self.lsptoolkit.get_references(word, relative_path, line, verbose=True)
        except FileNotFoundError:
            abs_path = os.path.join(self.path, relative_path)
            all_paths = get_file_paths_recursive(self.path)
            most_matched = find_most_matched_string(all_paths, abs_path)
            relative_path = most_matched.replace(self.path, "")
            results = self.lsptoolkit.get_references(word, relative_path, line, verbose=True)
            return "The file is not found, please check the path again, may lack of prefix directory name"
        except IsADirectoryError:
            return "The relative path is a folder, please specify the file path instead. Consider using get_tree_structure to find the file name then use this tool one file path at a time"
        if reranking:
            return self.rerank(results, query)
        else:
            return results[:5]
    
    def rerank(self, results: List[str], query: str):
        """
        Rerank the results based on a query.

        Args:
            results (List[str]): The list of references to rerank.
            query (str): The query used for reranking.

        Returns:
            List[str]: The reranked list of references.
        """
        reranked_results = []
        for item in results[:20]:
            new_item = {}
            new_item["score"] = self.similarity(query, item)
            new_item["content"] = item
        results = sorted(reranked_results, key=lambda x: x["score"], reverse=True)
        return [item["content"] for item in results[:5]]
    
    def similarity(self, query: str, implementation):
        """
        Calculate the similarity score between a query and an implementation.

        Args:
            query (str): The query string.
            implementation (str): The implementation string.

        Returns:
            float: The similarity score between the query and implementation.
        """
        embed_query = np.array(self.openai_engine.embeddings.create(input=query, model="text-embedding-ada-002").data[0].embedding)
        embed_implementation = np.array(self.openai_engine.embeddings.create(input=implementation, model="text-embedding-ada-002").data[0].embedding)
        score = np.dot(embed_query, embed_implementation) / (np.linalg.norm(embed_query) * np.linalg.norm(embed_implementation))
        return score

class GetAllSymbolsArgs(BaseModel):
    path_to_file: str = Field(..., description="The path of the python file we want extract all symbols from.")
    preview_size: int = Field(..., description="The number of lines of the definition to preview, useful when the definition is too long and we want to save number of tokens, default by 5")

class GetAllSymbolsTool(BaseTool):
    """
    A tool for finding all symbols (functions, classes, methods) of a Python/Rust/C#/Java file.

    Args:
        path (str): The path to the source file.
        language (str, optional): The language of the file. Defaults to "python".
    """

    name = "get_all_symbols"
    description = "Useful when you want to find all symbols (functions, classes, methods) of a python file"
    args_schema = GetAllSymbolsArgs
    lsptoolkit: LSPToolKit = None
    path = ""
    verbose = False
    language = "python"
    
    def __init__(self, path: str, language: str ="python"):
        super().__init__()
        self.path = path
        self.lsptoolkit = LSPToolKit(path, language)
    
    def _run(self, path_to_file: str, preview_size: int = 5):
        """
        Run the tool to get all symbols of a Python file.

        Args:
            path_to_file (str): The path to the Python file.
            preview_size (int, optional): The number of symbols to preview. Defaults to 5.

        Returns:
            Union[List[str], str]: The list of symbols or an error message.
        """
        try:
            return self.lsptoolkit.get_symbols(path_to_file, preview_size=preview_size)
        except IsADirectoryError:
            return "The relative path is a folder, please specify the file path instead. Consider using get_tree_structure to find the file name then use this tool one file path at a time"
        except FileNotFoundError:
            return "The file is not found, please check the path again"
        except lsp_protocol_handler.server.Error:
            return "Internal error, please use other tool"

class GetTreeStructureArgs(BaseModel):
    relative_path: str = Field(..., description="The relative path of the folder we want to explore")
    level: int = Field(..., description="The level of the tree structure we want to explore, prefer to use 2 (default) for a quick overview of the folder structure then use 3 for more details")

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
    
    def __init__(self, path, language):
        super().__init__()
        self.path = path
    
    def _run(self, relative_path: str, level: int = 2):
        abs_path = os.path.join(self.path, relative_path)
        try:
            output = visualize_tree(abs_path, level=level)
            output = "The tree structure of " + relative_path + " is: \n" + output
        except: 
            output = "Execution failed, please check the relative path again, likely the relative path lacks of prefix directory name"
        return output

class OpenFileArgs(BaseModel):
    relative_file_path: str = Field(..., description="The relative path of the file we want to open")

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
    description = """Useful when you want to open a file inside a repo, use this tool only when it's very necessary, usually a main or server or training script. Consider combinining other alternative tools such as GetAllSymbols and CodeSearch to save the number of tokens for other cases."""
    args_schema = OpenFileArgs
    path = ""
    
    def __init__(self, path, language):
        super().__init__()
        self.path = path
    
    def _run(self, relative_file_path: str, max_new_line: int = 500):
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
            source = open(abs_path, "r").read()
            lines = source.split("\n")
            source = "\n".join(lines[:max_new_line]) 
        except FileNotFoundError:
            return "File not found, please check the path again"
        source = add_num_line(source, 0)
        return "The content of " + relative_file_path + " is: \n" + source
    

class SemanticCodeSearchTool(Tool):
    def __init__(self, path, language:str="python", db_path: Optional[str] = None, build: bool = False):
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
                language=language, chunk_size=800, chunk_overlap=200
            )
            loader = GenericLoader.from_filesystem(
                path,
                suffixes=[extension],
                parser=LanguageParser(language=language, parser_threshold=500),
            )
            
            documents = loader.load()
            texts = splitter.split_documents(documents)
            db = Chroma.from_documents(texts, OpenAIEmbeddings(disallowed_special=()), persist_directory=db_path)
            db.persist()
        else:
            db = Chroma(persist_directory=db_path, embedding_function=OpenAIEmbeddings(disallowed_special=()))
        
        def semantic_code_search(query):
            retrieved_docs = db.similarity_search(query, k=3)
            return [doc.page_content for doc in retrieved_docs]
        
        super().__init__(
            name="Semantic Code Search",
            func=semantic_code_search,
            description="useful for when the query is a sentance, semantic and vague. If exact search such as code search failed after multiple tries, try this",
        )

tool_classes = [CodeSearchTool, SemanticCodeSearchTool, GoToDefinitionTool, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool, OpenFileTool]