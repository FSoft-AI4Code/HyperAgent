import os
from pylsp.text_edit import OverLappingTextEditException, apply_text_edits
from pylsp.plugins.definition import pylsp_definitions
from pylsp.plugins.references import pylsp_references
from pylsp import uris
from pylsp.config.config import Config
from server import ClientServerPair
from pylsp.plugins.symbols import pylsp_document_symbols
from pylsp.lsp import SymbolKind

CALL_TIMEOUT_IN_SECONDS = 10

def word_to_position(source, word, line=None, offset=0):
    """find position of a word in a source"""
    lines = source.splitlines()
    for i, _line in enumerate(lines):
        if word in _line:
            return {"line": (line + offset) if line else (i + offset), "character": _line.index(word)+1} ## +1 because the position is 0-based
    return None

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

def test_finding_definition(pylsp, word, relative_path):
    ## to get a document source, test_doc.source
    DOC_URI = uris.from_fs_path(os.path.join(test_path, relative_path))
    test_doc = pylsp.workspace.get_document(DOC_URI)
    cursor_pos = word_to_position(test_doc.source, word)
    cfg = Config(pylsp.workspace.root_uri, {}, 0, {})
    cfg._plugin_settings = {
        "plugins": {"pylint": {"enabled": False, "args": [], "executable": None}}
    }
    output = pylsp_definitions(cfg, test_doc, cursor_pos)
    print(output)

class LSPToolKit:
    def __init__(self, root_path):
        self.root_path = root_path
        client_server_pair_obj = ClientServerPair()
        self.client = client_server_pair_obj.client
        self.server = client_server_pair_obj.server
        self.client._endpoint.request(
            "initialize",
            {"rootPath": root_path, 
             "initializationOptions": {},
            },
        ).result(timeout=CALL_TIMEOUT_IN_SECONDS)
    
    def get_document(self, uri):
        return self.server.workspace.get_document(uri)
    
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
    
    def get_symbols(self, relative_path, verbose=False):
        uri = uris.from_fs_path(os.path.join(self.root_path, relative_path)) if "://" not in relative_path else relative_path
        doc = self.get_document(uri)
        cfg = Config(self.root_path, {}, 0, {})
        cfg._plugin_settings = {
            "plugins": {"pylint": {"enabled": False, "args": [], "executable": None},
                        "jedi_symbols": {"all_scopes": False}  
            },
        }
        symbols = pylsp_document_symbols(cfg, doc)
        return symbols
    
    def get_references(self, word, relative_path, line=None, offset=0, verbose=False):
        uri = uris.from_fs_path(os.path.join(self.root_path, relative_path)) if "://" not in relative_path else relative_path
        doc = self.get_document(uri)
        cursor_pos = word_to_position(doc.source, word, line=line, offset=offset)
        output = pylsp_references(doc, cursor_pos, exclude_declaration=True)
        return output

    def shutdown(self):
        self.client._endpoint.request("shutdown", {}).result(timeout=CALL_TIMEOUT_IN_SECONDS)
        self.client._endpoint.notify("exit", {})

if __name__ == "__main__":
    test_path = "/datadrive05/huypn16/focalcoder/data/repos/repo__astropy__astropy__commit__3832210580d516365ddae1a62071001faf94d416/"
    lsp = LSPToolKit(test_path)
    output = lsp.get_definition("__init__", "astropy/convolution/kernels.py", line=0, offset=0, verbose=True)
    # lsp.get_symbols("astropy/convolution/kernels.py")
    print(output)
    lsp.shutdown()