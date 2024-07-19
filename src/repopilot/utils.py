from pathlib import Path
from git import Repo
import subprocess
import os
from urllib.parse import urlparse
import socketserver
from typing import Dict, List, Optional, TextIO
from repopilot.multilspy.lsp_protocol_handler.lsp_types import SymbolKind
from repopilot.constants import DEFAULT_PATCHES_DIR
import json
import difflib
from transformers import AutoTokenizer
import tiktoken
import codecs
import logging
import random
import string

def generate_random_string(length, use_uppercase=True, use_lowercase=True, use_digits=True, use_punctuation=False):
    characters = ''
    if use_uppercase:
        characters += string.ascii_uppercase
    if use_lowercase:
        characters += string.ascii_lowercase
    if use_digits:
        characters += string.digits
    if use_punctuation:
        characters += string.punctuation
    
    if not characters:
        raise ValueError("At least one character set must be selected")
    
    return ''.join(random.choice(characters) for i in range(length))

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
        # logger.info(f"Cloning {repo} {os.getpid()}")
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
    
def word_to_position(source: str, word: str, line = None, offset: int = 0):
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
    except IndexError:
        for i, _line in enumerate(lines):
            if word in _line:
                return {"line": i, "column": _line.index(word)+1}
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
    if start_line is None:
        start_line = 1
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

def truncate_tokens(string: str, encoding_name: str, max_length: int = 8192) -> str:
    """Truncates a text string based on max number of tokens."""
    encoding = tiktoken.encoding_for_model(encoding_name)
    encoded_string = encoding.encode(string)
    num_tokens = len(encoded_string)

    if num_tokens > max_length:
        string = encoding.decode(encoded_string[:max_length-300])

    return string

def truncate_tokens_hf(string: str, encoding_name: str) -> str:
    """Truncates a text string based on max number of tokens."""
    tokenizer = AutoTokenizer.from_pretrained(encoding_name)
    max_tokens = tokenizer.model_max_length
    encoded_string = tokenizer.encode(string, return_tensors="pt")
    num_tokens = len(encoded_string[0])

    if num_tokens > max_tokens:
        string = tokenizer.decode(encoded_string[0][:max_tokens-400])

    return string

def find_non_utf8_files(path):
    """
    Finds all non-UTF-8 file paths in a given directory and returns their relative paths.

    Args:
        path (str): The path to the directory.

    Returns:
        list: A list of relative paths of non-UTF-8 files.
    """
    non_utf8_files = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                with codecs.open(file_path, 'r', 'utf-8') as f:
                    f.read()
            except UnicodeDecodeError:
                # Calculate the relative path by removing the base directory path
                relative_path = os.path.relpath(file_path, path)
                non_utf8_files.append(relative_path)
    return non_utf8_files

def find_abs_path(folder, file_name):
    # Walk through the directory and its subdirectories
    for root, dirs, files in os.walk(folder):
        # Construct the potential full path
        potential_path = os.path.join(root, file_name)
        # Check if this potential path is a file
        if os.path.isfile(potential_path):
            # Return the absolute path of the file
            return os.path.abspath(potential_path)
    # If file is not found, return None
    return None

def run_ctags(file_path):
    MAIN_KINDS = {"module": SymbolKind.Module, "namespace": SymbolKind.Namespace, "class": SymbolKind.Class, "method": SymbolKind.Method, "function": SymbolKind.Function, "member": SymbolKind.Method}
    filter_results = []
    final_results = []
    cmd = ["ctags", "--extras=*", "--fields={line}{end}{name}{kind}{scopeKind}", "--output-format=json", file_path]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        print(f"Error executing ctags: {stderr.decode()}")
    else:
        results = [json.loads(line) for line in stdout.decode().splitlines()]
    for symbol in results:
        if "kind" in symbol and "end" in symbol:
            if symbol["kind"] in MAIN_KINDS:
                symbol["kind"] = MAIN_KINDS[symbol["kind"]]
                symbol["range"] = {"start_line": symbol["line"], "end_line": symbol["end"]}
                symbol["created_by_ctags"] = True
                filter_results.append(symbol)
                
    # a simple heuristic to get the longest name for each symbol since ctags does not provide the full name
    for symbol in filter_results:
        if "scopeKind" in symbol:
            for result in results:
                if "line" in result and "scopeKind" in result and "name" in result:
                    if result["line"] == symbol["line"] and result["scopeKind"] == symbol["scopeKind"] and len(result["name"]) > len(symbol["name"]):
                        symbol["name"] = result["name"]
    # filter out duplicate symbols, choose the longest end-start line
    filter_results = sorted(filter_results, key=lambda x: (x["line"], x["end"] - x["line"]), reverse=True)
    for symbol in filter_results:
        if symbol["name"] not in [result["name"] for result in final_results]:
            final_results.append(symbol)
    return final_results

def get_symbol_with_keyword(file_path: str, parent_path: str, keyword: str):
    out_symbols = get_symbol_per_file(file_path, [SymbolKind.Class, SymbolKind.Method, SymbolKind.Function], parent_path, keyword)
    for symbol in out_symbols:
        if keyword == symbol["name"]:
            return symbol["definition"]
    return F"No symbol {keyword} found in this file."

def get_symbol_per_file(file_path: str, primary_symbols, parent_path, keyword):
    out_file_symbols = []
    file_symbols = run_ctags(file_path)
    primary_symbols = [int(symbol_kind) for symbol_kind in primary_symbols]
    file_symbols = [symbol for symbol in file_symbols if symbol["kind"] in primary_symbols]
    
    for symbol in file_symbols:
        symbol_definition = open(file_path, "r").readlines()[symbol["range"]["start_line"]-1:symbol["range"]["end_line"]]
        symbol_definition = "".join(symbol_definition)
        output_item = {
            "name": symbol["name"],
            "definition": add_num_line(symbol_definition, symbol["range"]["start_line"]),
            "range": symbol["range"],
            "path": file_path.replace(parent_path, ""),
        }
        if keyword is not None:
            # if keyword exists, we prefer exact match over partial match to reduce false positives and redudant observation, otherwise we keep all partial matches.
            condition = (keyword == symbol["name"]) if keyword in [s["name"] for s in file_symbols] else (keyword in symbol["name"])
            if condition:
                out_file_symbols.append(output_item)
        else:
            out_file_symbols.append(output_item)
    
    return out_file_symbols

def get_symbol_verbose(file_path: str, parent_path: str, keyword: str = None):
    primary_symbols = [SymbolKind.Class, SymbolKind.Method, SymbolKind.Function, SymbolKind.Interface]
    with open(file_path, 'r+') as f:
        try:
            if not f.read().endswith('\n'):
                f.write('\n')
            out_file_symbols = get_symbol_per_file(file_path, primary_symbols, parent_path, keyword)
            out_str = ""
            out_str += f"Symbols in {file_path.replace(parent_path, '')}\n"
            num_line_per_symbol = [symbol["range"]["end_line"] - symbol["range"]["start_line"] for symbol in out_file_symbols]
            if len(out_file_symbols) == 0:
                return "No symbol found in this file."
            
            if len(out_file_symbols) >= 3 or max(num_line_per_symbol) > 35:
                out_str += "Name StartLine EndLine\n"
                for symbol in out_file_symbols:
                    out_str += f"{symbol['name']} {symbol['range']['start_line']} {symbol['range']['end_line']}\n"
            else:
                out_str += "Name StartLine EndLine Definition\n"
                for symbol in out_file_symbols:
                    out_str += f"{symbol['name']} {symbol['range']['start_line']} {symbol['range']['end_line']} \n{symbol['definition']}\n"
            
            return out_str
        except UnicodeDecodeError:
            print(f"Error in reading file {file_path}")
            return f"Error in reading file {file_path}"
        
def setup_logger():
    class CustomFormatter(logging.Formatter):

        grey = "\x1b[38;20m"
        yellow = "\x1b[33;20m"
        red = "\x1b[31;20m"
        bold_red = "\x1b[31;1m"
        reset = "\x1b[0m"
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

        FORMATS = {
            logging.DEBUG: grey + format + reset,
            logging.INFO: grey + format + reset,
            logging.WARNING: yellow + format + reset,
            logging.ERROR: red + format + reset,
            logging.CRITICAL: bold_red + format + reset
        }

        def format(self, record):
            log_fmt = self.FORMATS.get(record.levelno)
            formatter = logging.Formatter(log_fmt)
            return formatter.format(record)
    
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("multilspy").setLevel(logging.FATAL)
    logger = logging.getLogger("RepoPilot")
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    ch.setFormatter(CustomFormatter())

    logger.addHandler(ch)
    return logger

_TEXT_COLOR_MAPPING = {
    "blue": "36;1",
    "yellow": "33;1",
    "pink": "38;5;200",
    "green": "32;1",
    "red": "31;1",
}


def get_color_mapping(
    items: List[str], excluded_colors: Optional[List] = None
) -> Dict[str, str]:
    """Get mapping for items to a support color."""
    colors = list(_TEXT_COLOR_MAPPING.keys())
    if excluded_colors is not None:
        colors = [c for c in colors if c not in excluded_colors]
    color_mapping = {item: colors[i % len(colors)] for i, item in enumerate(items)}
    return color_mapping


def get_colored_text(text: str, color: str) -> str:
    """Get colored text."""
    color_str = _TEXT_COLOR_MAPPING[color]
    return f"\u001b[{color_str}m\033[1;3m{text}\u001b[0m"


def get_bolded_text(text: str) -> str:
    """Get bolded text."""
    return f"\033[1m{text}\033[0m"


def print_text(
    text: str, color: Optional[str] = None, end: str = "", file: Optional[TextIO] = None
) -> None:
    """Print text with highlighting and no end characters."""
    text_to_print = get_colored_text(text, color) if color else text
    print(text_to_print, end=end, file=file)
    
def extract_patch(
    repo_dir: str
) -> str:
    random_name = generate_random_string(8)
    os.system(f"cd {repo_dir} && git diff HEAD > {DEFAULT_PATCHES_DIR}/{random_name}.diff")
    
    with open(f"{DEFAULT_PATCHES_DIR}/{random_name}.diff", "r") as f:
        patch = f.read()
    return patch

def find_matching_abs_path(parent_folder, sub_path):
    # Walk through the parent folder to find matching sub-path
    for root, dirs, files in os.walk(parent_folder):
        for name in dirs + files:
            full_path = os.path.join(root, name)
            # Check if the sub_path matches the end of the full path
            if full_path.endswith(sub_path):
                return os.path.abspath(full_path)
    return None

def find_all_file_paths(parent_folder, file_name):
  """Finds all paths of files with the given name in a parent folder.

  Args:
    parent_folder: The path to the parent folder.
    file_name: The name of the file to find.

  Returns:
    A list of all full paths to the files if found, otherwise an empty list.
  """

  file_paths = []
  for root, _, files in os.walk(parent_folder):
    if file_name in files:
      file_paths.append(os.path.join(root, file_name))

  return file_paths

from pathlib import Path

def find_matching_file_path(parent_folder, sub_file_path):
    for root, dirs, files in os.walk(parent_folder):
        for name in dirs + files:
            full_path = os.path.join(root, name)
            if full_path.endswith(sub_file_path):
                return Path(full_path).resolve()
    
    file_paths = find_all_file_paths(parent_folder, sub_file_path.split("/")[-1])
    if len(file_paths) == 1:
        return Path(file_paths[0]).resolve()

    return None

if __name__ == "__main__":
    print(find_matching_file_path("/datadrive5/huypn16/RepoPilot-Master", "repopilot/prompts/executor.py"))