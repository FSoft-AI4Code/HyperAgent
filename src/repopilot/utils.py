from pathlib import Path
from git import Repo
import subprocess
import os
from urllib.parse import urlparse
import socketserver
from repopilot.multilspy.lsp_protocol_handler.lsp_types import SymbolKind
import json
import difflib

def find_most_matched_string(word_list, target):
    # Get close matches; n=1 ensures only the top match is returned
    matches = difflib.get_close_matches(target, word_list, n=1)
    return matches[0] if matches else None

def find_free_port():
    with socketserver.TCPServer(("localhost", 0), None) as s:
        free_port = s.server_address[1]
    return free_port

def check_local_or_remote(path: str):
    # Check if link is a valid folder path
    if os.path.isdir(path):
        return (True, path)
    # Check if link is a valid URL
    try:
        result = urlparse(path)
        if all([result.scheme, result.netloc, result.path]) and 'github.com' in result.netloc:
            return (False, result.path[1:])
    except:
        raise ValueError("Please provide a valid folder path or GitHub URL.")
    
def get_env_path():
    python_path = subprocess.check_output("which python", shell=True).strip().decode("utf-8")
    return python_path

def clone_repo(repo, commit, root_dir, token, logger):
    """
    Clones a GitHub repository to a specified directory.

    Args:
        repo (str): The GitHub repository to clone.
        commit (str): The commit to checkout.
        root_dir (str): The root directory to clone the repository to.
        token (str): The GitHub personal access token to use for authentication.

    Returns:
        Path: The path to the cloned repository directory.
    """
    repo_dir = Path(root_dir, f"repo__{repo.replace('/', '__')}__commit__{commit}")
    
    if not repo_dir.exists():
        repo_url = f"https://{token}@github.com/{repo}.git"
        logger.info(f"Cloning {repo} {os.getpid()}")
        Repo.clone_from(repo_url, repo_dir)
        cmd = f"cd {repo_dir} && git reset --hard {commit} && git clean -fdxq"
        subprocess.run(
                cmd,
                shell=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
        )
    return root_dir + "/" + repo_dir.name

def identify_extension(language):
    """
    Identify the file extension based on the given programming language.

    Args:
        language (str): The programming language.

    Returns:
        str: The file extension corresponding to the programming language.
    """
    if language == "python":
        return ".py"
    elif language == "java":
        return ".java"
    elif language == "csharp":
        return ".cs"
    elif language == "rust":
        return ".rs"

def matching_kind_symbol(symbol):
    """
    Returns the string representation of the symbol kind.

    Args:
        symbol (dict): The symbol object.

    Returns:
        str: The string representation of the symbol kind.
    """
    kind = symbol["kind"]
    if kind == SymbolKind.File:
        return "File"
    elif kind == SymbolKind.Module:
        return "Module"
    elif kind == SymbolKind.Namespace:
        return "Namespace"
    elif kind == SymbolKind.Package:
        return "Package"
    elif kind == SymbolKind.Class:
        return "Class"
    elif kind == SymbolKind.Method:
        return "Method"
    elif kind == SymbolKind.Property:
        return "Property"
    elif kind == SymbolKind.Field:
        return "Field"
    elif kind == SymbolKind.Function:
        return "Function"
    elif kind == SymbolKind.Variable:
        return "Variable"
    elif kind == SymbolKind.Constant:
        return "Constant"
    elif kind == SymbolKind.String:
        return "String"
    elif kind == SymbolKind.Number:
        return "Number"
    elif kind == SymbolKind.Boolean:
        return "Boolean"
    elif kind == SymbolKind.Array:
        return "Array"
    elif kind == SymbolKind.Object:
        return "Object"
    elif kind == SymbolKind.Key:
        return "Key"
    elif kind == SymbolKind.Null:
        return "Null"
    elif kind == SymbolKind.Enum:
        return "Enum"
    elif kind == SymbolKind.EnumMember:
        return "EnumMember"
    elif kind == SymbolKind.Struct:
        return "Struct"
    elif kind == SymbolKind.Event:
        return "Event"
    elif kind == SymbolKind.Operator:
        return "Operator"
    elif kind == SymbolKind.TypeParameter:
        return "TypeParameter"
    else:
        return "Unknown"
    
def word_to_position(source: str, word: str, line: None|int|list = None, offset: int = 0):
    """
    Find the position of a word in a source.

    Args:
        source (str): The source string to search in.
        word (str): The word to find the position of.
        line (None|int|list, optional): The line number(s) to search in. Defaults to None.
        offset (int, optional): The offset to adjust the line number(s) by. Defaults to 0.

    Returns:
        dict: A dictionary containing the line and column position of the word.
              The line position is 0-based, while the column position is 1-based.
              Returns None if the word is not found.
    """
    if isinstance(line, list):
        line = line[0]
    lines = source.splitlines()
    try:
        for i, _line in enumerate(lines):
            if word in _line:
                return {"line": (line + offset) if line else (i + offset), "column": lines[line].index(word)+1 if line else (_line.index(word) + 1)} ## +1 because the position is 0-based
    except ValueError:
        for i, _line in enumerate(lines):
            if word in _line:
                return {"line": i, "column": lines[i].index(word)+1}
    return None

def add_num_line(source: str, start_line: int):
    """
    Add line numbers to each line of the source code.

    Args:
        source (str): The source code as a string.
        start_line (int): The starting line number.

    Returns:
        str: The source code with line numbers added.
    """
    lines = source.split("\n")
    results = []
    for idx, _line in enumerate(lines):
        _line = str(idx + start_line) + " " + _line
        results.append(_line)
    return "\n".join(results)

def matching_symbols(symbols, object):
    """
    Find a matching symbol based on line range.

    Args:
        symbols (list): List of symbols to search through.
        object (dict): The object to match against.

    Returns:
        dict or None: The matching symbol if found, None otherwise.
    """
    for symbol in symbols:
        ## approximat matching only is strong enough
        if "location" not in symbol:
            if symbol["range"]["start"]["line"] == object["range"]["start"]["line"]:
                return symbol
            else:
                continue
        if symbol["location"]["range"]["start"]["line"] == object["range"]["start"]["line"]:
            return symbol
    return None

def get_text(doc, range):
    """
    Retrieves the text within the specified range in the given document.

    Args:
        doc (str): The document to extract text from.
        range (dict): The range object specifying the start and end positions.

    Returns:
        str: The extracted text within the specified range.
    """
    return doc[offset_at_position(doc, range["start"]):offset_at_position(doc, range["end"])]

def offset_at_position(doc, position):
    """
    Calculates the offset at a given position in a document.

    Args:
        doc (str): The document content.
        position (dict): The position object containing the line and character.

    Returns:
        int: The offset at the given position.
    """
    return position["character"] + len("".join(doc.splitlines(True)[: position["line"]]))

def save_infos_to_folder(infos_dict, name, folder):
    if not os.path.exists(folder):
        os.makedirs(folder)
    with open(folder + "/" + name + ".json", "w") as f:
        json.dump(infos_dict, f, indent=4)

def get_file_paths_recursive(directory):
    file_paths = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            # Construct the file path
            file_path = os.path.join(root, file)
            file_paths.append(file_path)
    return file_paths