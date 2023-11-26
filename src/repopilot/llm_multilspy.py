import os
from pylsp.plugins.definition import pylsp_definitions
from pylsp import uris
from pylsp.config.config import Config
from pylsp.plugins.symbols import pylsp_document_symbols
from pylsp.lsp import SymbolKind
from pylsp.plugins.hover import pylsp_hover

from repopilot.multilspy import SyncLanguageServer
from repopilot.multilspy.multilspy_config import MultilspyConfig
from repopilot.multilspy.multilspy_logger import MultilspyLogger

CALL_TIMEOUT_IN_SECONDS = 10

def word_to_position(source, word, line=None, offset=0):
    """find position of a word in a source"""
    lines = source.splitlines()
    for i, _line in enumerate(lines):
        if word in _line:
            return {"line": (line + offset) if line else (i + offset), "character": lines[line].index(word)+1 if line else (_line.index(word) + 1)} ## +1 because the position is 0-based
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
    return doc.source[doc.offset_at_position(range["start"]):doc.offset_at_position(range["end"])]

def matching_py_kind_symbol(symbol):
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

class LSPToolKit:
    def __init__(self, root_path, language="python", logger=None):
        self.root_path = root_path
        self.logger = logger if logger else MultilspyLogger()
        self.server = SyncLanguageServer.create(MultilspyConfig(code_language=language), self.logger, root_path)
        
    def open_file(self, relative_path):
        with self.server.start_server():
            result = self.server.get_open_file_text(relative_path)
        return result
    
    def get_document(self, uri):
        return self.server.get_document(uri)
    
    def get_definition(self, word, relative_path, line=None, offset=0, verbose=False):
        uri = uris.from_fs_path(os.path.join(self.root_path, relative_path)) if "://" not in relative_path else relative_path
        doc = self.get_document(uri)
        cursor_pos = word_to_position(doc.source, word, line=line, offset=offset)
        cfg = Config(self.root_path, {}, 0, {})
        cfg._plugin_settings = {
            "plugins": {"pylint": {"enabled": False, "args": [], "executable": None}}
        }
        output = pylsp_definitions(cfg, doc, cursor_pos)
        
        if verbose:
            symbols = self.get_symbols(output[0]["uri"])
            symbol = matching_symbols(symbols, output[0])
            symbol_type = matching_py_kind_symbol(symbol)
            output = "Parent Name: " + str(symbol["containerName"]) + "\n" + "Name: " + str(symbol["name"]) + "\n" + "Type: " + str(symbol_type) + "\n" + "Definition: " + get_text(self.get_document(output[0]["uri"]), symbol["location"]["range"])
            
        return output
    
    def get_symbols(self, relative_path, verbose_level=1, verbose=False, preview_size=1):
        """Get all symbols in a file

        Args:
            relative_path (_type_): relavtive path to the file
            verbose (bool, optional): verbose result as string for LLM interaction. Defaults to False.
            verbose_level (int, optional): efficient verbose settings to save number of tokens. There're 3 levels of details.
                1 - only functions and classes - default
                2 - functions, classes, and methods of classes 
                3 - functions, classes, methods of classes, and variables
            preview_size (int, optional): only preview preview_size number of lines of definitions to save number of tokens. Defaults to 1.

        Returns:
            _type_: _description_
        """
        uri = uris.from_fs_path(os.path.join(self.root_path, relative_path)) if "://" not in relative_path else relative_path
        doc = self.get_document(uri)
        cfg = Config(self.root_path, {}, 0, {})
        cfg._plugin_settings = {
            "plugins": {"pylint": {"enabled": False, "args": [], "executable": None},
                        "jedi_symbols": {"all_scopes": False}  
            },
        }
        symbols = pylsp_document_symbols(cfg, doc)
        if verbose:
            verbose_output = []
            for item in symbols:
                definition = get_text(self.get_document(item["location"]["uri"]), item["location"]["range"])
                if verbose_level == 1:
                    if (item["kind"] == SymbolKind.Class or item["kind"] == SymbolKind.Function) and ((item["location"]["range"]["end"]["line"] - item["location"]["range"]["start"]["line"]) > 2) and ("import" not in definition):
                        
                        cha = definition.split("\n")[0].index(item["name"])
                        documentation = pylsp_hover(doc._config, doc, {"line": item["location"]["range"]["start"]["line"], "character": cha})["contents"]
                        if "value" not in documentation:
                            documentation = "None"
                            preview = "\n".join(definition.split("\n")[:preview_size+4])
                        else:
                            preview = "\n".join(definition.split("\n")[:preview_size])
                        preview = add_num_line(preview, item["location"]["range"]["start"]["line"])
                        item_out = "Parent Name: " + str(item["containerName"]) + "\n" + "Name: " + str(item["name"]) + "\n" + "Type: " + str(matching_py_kind_symbol(item)) + "\n" + "Preview: " + str(preview) + "\n" + "Documentation: " + str(documentation) + "\n"
                        verbose_output.append(item_out)
                elif verbose_level == 2:
                    if (item["kind"] == SymbolKind.Class or item["kind"] == SymbolKind.Function or item["kind"] == SymbolKind.Method) and ((item["location"]["range"]["end"]["line"] - item["location"]["range"]["start"]["line"]) > 2) and ("import" not in definition):
                        cha = definition.split("\n")[0].index(item["name"])
                        documentation = pylsp_hover(doc._config, doc, {"line": item["location"]["range"]["start"]["line"], "character": cha})["contents"]
                        if "value" not in documentation:
                            documentation = "None"
                            preview = "\n".join(definition.split("\n")[:preview_size+4])
                        else:
                            preview = "\n".join(definition.split("\n")[:preview_size])
                        preview = add_num_line(preview, item["location"]["range"]["start"]["line"])
                        item_out = "Parent Name: " + str(item["containerName"]) + "\n" + "Name: " + str(item["name"]) + "\n" + "Type: " + str(matching_py_kind_symbol(item)) + "\n" + "Preview: " + str(preview) + "\n" + "Documentation: " + str(documentation) + "\n"
                        verbose_output.append(item_out)
                        
            symbols = verbose_output
        return symbols
    
    def get_references(self, word, relative_path, line=None, offset=0, verbose=False, context_size=10):
        uri = uris.from_fs_path(os.path.join(self.root_path, relative_path)) if "://" not in relative_path else relative_path
        print("uri", uri)
        doc = self.open_file(relative_path)
        import ipdb; ipdb.set_trace()
        try:
            cursor_pos = word_to_position(doc.source, word, line=line, offset=offset)
        except ValueError:
            ## LLM sometimes send the wrong line number or not aware of the line number
            cursor_pos = word_to_position(doc.source, word, line=None, offset=offset)
        output = self.server.request_references(relative_path, **cursor_pos)
        if verbose: 
            verbose_output = []
            for item in output:
                doc_item = self.get_document(item["uri"])
                item["range"]["start"]["line"] = max(0, item["range"]["start"]["line"] - context_size)
                item["range"]["end"]["line"] = min(len(doc_item.lines), item["range"]["end"]["line"] + context_size)
                item["range"]["start"]["character"] = 0
                item["range"]["end"]["character"] = len(doc_item.lines[item["range"]["end"]["line"]-1])
                implementation = get_text(doc_item, item["range"])
                results = []
                for idx, _line in enumerate(implementation.split("\n")):
                    _line = str(idx + item["range"]["start"]["line"]) + " " + _line
                    results.append(_line)
                    
                implementation = "\n".join(results)
                
                item["uri"] = str(item["uri"]).replace("file://" + self.root_path, "")
                item_out = "File Name: " + str(item["uri"]) + "\n" + "Implementation: " + str(implementation) + "\n"
                verbose_output.append(item_out)
            output = verbose_output
        return output


if __name__ == "__main__":
    test_path = "/datadrive05/huypn16/focalcoder/data/repos/repo__krohling__bondai__commit__"
    lsp = LSPToolKit(test_path, language="python")
    output = lsp.open_file("bondai/tools/langchain_tool.py")
    output = lsp.get_references(word="LangChainTool", relative_path="bondai/tools/langchain_tool.py", line=1, verbose=True)
    print(output)