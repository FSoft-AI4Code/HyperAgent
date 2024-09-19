import os
from typing import Type, List, Optional, Callable
from pydantic import BaseModel, Field
from langchain.tools import BaseTool, Tool
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.generic import GenericLoader
from hyperagent.langchain_parsers.parsers import LanguageParser
from hyperagent.get_repo_struct import visualize_tree
from hyperagent.llm_multilspy import LSPToolKit, add_num_line
from hyperagent.code_search import search_elements_inside_project
from hyperagent.zoekt.zoekt_server import ZoektServer
from hyperagent.utils import identify_extension, find_non_utf8_files, find_all_file_paths
from langchain_community.embeddings.cohere import CohereEmbeddings
from langchain_community.vectorstores import Chroma
from hyperagent.utils import get_symbol_verbose
from codetext.utils import parse_code
from hyperagent.code_search import get_parser
import jedi
import uuid
from hyperagent.multilspy import lsp_protocol_handler
from hyperagent.utils import find_all_file_paths, find_matching_abs_path
from hyperagent.constants import SEMANTIC_CODE_SEARCH_DB_PATH
import os.path as osp
from transformers import AutoModel
from numpy.linalg import norm

class CodeSearchArgs(BaseModel):
    names: list[str] = Field(..., description="The names of the identifiers to search. Identifier should be a single word like `some_function` not `something.something`")

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
    description = """Useful when you want to find all matched primary symbols (function, class name) in a repository. You want to quickly find a class or function like `some_function` function not `something.something`"""
    args_schema: Type[BaseModel] = CodeSearchArgs
    path = ""
    verbose = False
    language = "python"
    backend: ZoektServer = None
    
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
        if any ("." in name for name in names):
            return "Please check the word again, the word should be identifier only, not `something.something`"
        result = search_elements_inside_project(names, self.backend, verbose=verbose, language=self.language)
        return result


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
        try:
            return self.lsptoolkit.get_definition(word, relative_path, line, verbose=verbose)
        except:
            return "File read failed, please check the path again"

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
        if relative_file_path is None:
            return "Please specify the relative file path"
        # if "/" not in relative_file_path:
        #     return "Invalid relative file path, please check the path again"
        
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
    description = "Useful when you want to find all symbols (functions, classes, methods) of source files. If you want to look for a specific keyword inside the name of the symbol, specify it, otherwise if you want to see all the symbols, do not provide the keyword. Prioritize using keyword to shorten the search."
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
    depths: int = Field(2, description="The depth of the tree structure we want to explore")

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
    
    def _run(self, relative_path: str, depth: int = 2):
        abs_path = os.path.join(self.path, relative_path)
        try:
            output = visualize_tree(abs_path, level=depth)
            output = "The tree structure of " + relative_path + " is: \n" + output
        except: 
            output = "Execution failed, please check the relative path again, likely the relative path lacks of prefix directory name. Using get_tree_structure on the parent directory such as '.' or 'something/' to get the list of files and directories to continue exploring."
        return output

class OpenFileArgs(BaseModel):
    relative_file_path: str = Field(..., description="The relative path of the file you want to open")
    keywords: List[str] = Field(..., description="The list of keywords you want to search in the file, it's should be a single word like grpc but not grpcio.grpc")
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
    language = ""
    parser: Optional[Callable] = None
    model: AutoModel = None
    
    def __init__(self, path, language=None):
        super().__init__()
        self.path = path
        self.parser = get_parser(language)
        self.language = language
        self.model = AutoModel.from_pretrained('jinaai/jina-embeddings-v2-base-code', trust_remote_code=True)
    
    def _run(self, relative_file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, keywords: Optional[List[str]] = [], preview_size: int = 8, max_num_result: int = 5, semantic_query: str = ""):
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
        
        abs_path = find_matching_abs_path(self.path, relative_file_path)
        # abs_path = os.path.join(self.path, relative_file_path)
        source = open(abs_path, "r").read()
        lines = source.split("\n")

        cos_sim = lambda a,b: (a @ b.T) / (norm(a)*norm(b))

        def chunk_list(lst, chunk_size):
            return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]
        
        if semantic_query != "":
            embeddings = self.modle.encode(
                [
                    "\n".join(segment_lst) for segment_lst in chunk_list(lines, 50)
                ]
            )

            query = self.model.encode([semantic_query])
            similarities = []
            for emb in embeddings:
                similarities.append(cos_sim(query, emb))
            
            sorted_idx = sorted(range(len(similarities)), key=lambda x: similarities[x], reverse=True)

            line_ranges = sorted_idx[:max_num_result]
            line_ranges = [(i*50, (i+1)*50) for i in line_ranges]
            returned_source = []
            for start, end in line_ranges:
                expanded_source = "\n".join(lines[start:end])
                expanded_source = add_num_line(expanded_source, start+1)
                returned_source.append(expanded_source)
            
            semantic_query_result =  "\n--------------\n".join(returned_source)

        try:
            if start_line is not None and end_line is not None and len(keywords) == 0:
                if end_line - start_line > 90:
                    return f"The number of lines to show is limited at 90, the requested number of lines is {end_line - start_line}, please specify the start and end line again or using keyword instead. For example {start_line}:{start_line+90}"
                
                if start_line > len(lines):
                    return f"Invalid start line, the start line is greater than the total number of lines in the file, the total number of lines in the file is {len(lines)}"
                
                source = "\n".join(lines[start_line:end_line]) 
            else:
                out_str = "The content of " + relative_file_path.replace(self.path, "") + " is: \n"     

                for keyword in keywords:
                    returned_source = []
                    out_str += f"\nResults for keyword: {keyword}\n"           
                    # if any([keyword in line for line in lines[start_line:end_line]]) and start_line is not None and end_line is not None:
                    #     expanded_source = "\n".join(lines[start_line:end_line])
                    #     expanded_source = add_num_line(expanded_source, start_line)
                    #     returned_source.append(expanded_source)

                    line_idx = []
                    for i, line in enumerate(lines):
                        if keyword in line:
                            line_idx.append(i)
                    
                    line_idx = line_idx[:max_num_result]
                    line_ranges = [None for _ in line_idx]

                    root_node = parse_code(source, self.language).root_node
                    function_list = self.parser.get_function_list(root_node)
                    class_list = self.parser.get_class_list(root_node)


                    for class_ in class_list:

                        for i, idx in enumerate(line_idx):
                            if class_.start_point[0]== idx:
                                line_ranges[i] = (class_.start_point[0], class_.end_point[0]+1)

                    for func in function_list:

                        for i, idx in enumerate(line_idx):
                            if func.start_point[0] == idx:
                                line_ranges[i] = (func.start_point[0], func.end_point[0]+1) 

                    if len(line_idx) == 0:
                        out_str += f"No keyword found in the file, please check the keyword again or use the start and end line instead for this keyword {keyword}"
                    else:
                        for i in range(len(line_idx)):
                            if line_ranges[i] is None:
                                # keyword found not in function or class
                                expanded_source = "\n".join(lines[max(0, line_idx[i]-preview_size):min(len(lines), line_idx[i]+preview_size)])
                                expanded_source = add_num_line(expanded_source, max(1, line_idx[i]-preview_size)+1)
                                returned_source.append(expanded_source)
                            else:
                                def checkcover(target, line_ranges_lst):
                                    for _range in line_ranges_lst:
                                        if _range is None:
                                            continue
                                        if target is None:
                                            continue
                                        if _range[0] > target[0] and _range[1] < target[1]:
                                            return True
                                    return False
                                if checkcover(line_ranges[i], line_ranges[:i]):
                                    continue
                                else:
                                    expanded_source = "\n".join(lines[max(0, line_ranges[i][0]):min(len(lines), line_ranges[i][1])])
                                    expanded_source = add_num_line(expanded_source, max(1, line_ranges[i][0])+1)
                                    returned_source.append(expanded_source)
                        out_str += "\n--------------\n".join(returned_source)
                    
                    out_str += ("\n" + semantic_query_result) if semantic_query != "" else "" 
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

class FindFileArgs(BaseModel):
    file_name: str = Field(..., description="The name of the file you want to find")

class FindFileTool(BaseTool):
    """
    Tool for finding a file inside a repository.

    Args:
        path (str): The path to the repository.
        language (str): The language of the repository.

    Attributes:
        name (str): The name of the tool.
        description (str): The description of the tool.
        args_schema (class): The schema for the tool's arguments.
        path (str): The path to the repository.

    Methods:
        _run(file_name: str) -> str:
            Runs the tool to find the specified file.

    """

    name = "find_file"
    description = """Useful when you want to find a file inside a repo. Remember to provide the file name correctly.
    """
    args_schema = FindFileArgs
    path = ""
    
    def __init__(self, path, language=None):
        super().__init__()
        self.path = path
    
    def _run(self, file_name: str):
        """
        Finds the specified file inside the repository.

        Args:
            file_name (str): The name of the file to find.

        Returns:
            str: The path to the file.

        """
        file_paths = find_all_file_paths(self.path, file_name)
        file_paths = [file_path.replace(self.path, "") for file_path in file_paths]
        if len(file_paths) == 0:
            return "The file is not found, please check the file name again"
        return "The file is found at: " + "\n".join(file_paths)
    
if __name__ == "__main__":
    # open_file = OpenFileTool(path='/datadrive5/huypn16/autogen_repo/repos/repo__astropy__astropy__commit__a5917978be39d13cd90b517e1de4e7a539ffaa48', language="python")
    # find_all_refs = FindAllReferencesTool(path='/datadrive5/huypn16/autogen_repo/repos/repo__astropy__astropy__commit__a5917978be39d13cd90b517e1de4e7a539ffaa48', language="python")
    # code_search = CodeSearchTool(path='/datadrive5/huypn16/autogen_repo/repos/repo__astropy__astropy__commit__a5917978be39d13cd90b517e1de4e7a539ffaa48', language="python", index_path="/datadrive5/huypn16/HyperAgent/data/indexes")
    # # result = open_file._run(relative_file_path="astropy/io/ascii/rst.py", keywords=["RST"], start_line=0, end_line=40)
    # result = find_all_refs._run(word="RST", relative_file_path="astropy/io/ascii/rst.py", line=33)
    # result = code_search._run(names=["RST"])
    # result = open_file._run(relative_file_path="astropy/io/ascii/ui.py", keywords=["get_writer"], start_line=770, end_line=820)

    get_all_symbols = GetAllSymbolsTool(path='/datadrive5/huypn16/HyperAgent-Master/data/repos/Chart-7', language="java")
    # result = open_file._run(relative_file_path="test/com/google/javascript/jscomp/CodePrinterTest.java", keywords=["assertPrint"])
    # result = open_file._run(relative_file_path="test/com/google/javascript/jscomp/FoldConstantsTest.java", keywords=["string", "join", "constant"], start_line=0, end_line=1000)
    # result = open_file._run(relative_file_path="source/org/jfree/data/time/TimePeriodValues.java", keywords=["add"], start_line=235, end_line=249)
    # result = open_file._run(relative_file_path="source/org/jfree/data/time/TimePeriodValues.java", keywords=["getMaxMiddleIndex"], start_line=0, end_line=900)
    # result = get_all_symbols._run(path_to_file="source/org/jfree/data/time/TimePeriodValues.java", keyword="maxMiddleIndex")
    # print(result)
