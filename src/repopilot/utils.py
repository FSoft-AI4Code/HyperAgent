from pathlib import Path
from git import Repo
import subprocess
import os
from repopilot.multilspy.lsp_protocol_handler.lsp_types import SymbolKind

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
    if language == "python":
        return ".py"
    elif language == "javascript":
        return ".js"
    elif language == "java":
        return ".java"
    elif language == "csharp":
        return ".cs"
    elif language == "rust":
        return ".rs"

def matching_kind_symbol(symbol):
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
    
def word_to_position(source, word, line=None, offset=0):
    """find position of a word in a source"""
    lines = source.splitlines()
    for i, _line in enumerate(lines):
        if word in _line:
            return {"line": (line + offset) if line else (i + offset), "column": lines[line].index(word)+1 if line else (_line.index(word) + 1)} ## +1 because the position is 0-based
    return None

def add_num_line(source, start_line):
    lines = source.split("\n")
    results = []
    for idx, _line in enumerate(lines):
        _line = str(idx + start_line) + " " + _line
        results.append(_line)
    return "\n".join(results)

def matching_symbols(symbols, object):
    for symbol in symbols:
        ## approximat matching only is strong enough
        if symbol["location"]["range"]["start"]["line"] == object["range"]["start"]["line"]:
            return symbol
    return None

def get_text(doc, range):
    return doc[offset_at_position(doc, range["start"]):offset_at_position(doc, range["end"])]

def offset_at_position(doc, position):
    return position["character"] + len("".join(doc.splitlines(True)[: position["line"]]))