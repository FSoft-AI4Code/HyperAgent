from repopilot.multilspy import SyncLanguageServer
from repopilot.multilspy.multilspy_config import MultilspyConfig
from repopilot.multilspy.multilspy_logger import MultilspyLogger
from repopilot.utils import matching_kind_symbol, matching_symbols, add_num_line, get_text, word_to_position
from repopilot.multilspy.lsp_protocol_handler.lsp_types import SymbolKind
import logging

logging.getLogger("multilspy").setLevel(logging.WARNING)

class LSPToolKit:
    def __init__(self, root_path, language="python"):
        self.root_path = root_path
        self.language = language
        self.server = SyncLanguageServer.create(MultilspyConfig(code_language=language), MultilspyLogger(), root_path)
        
    def open_file(self, relative_path):
        with self.server.start_server():
            with self.server.open_file(relative_path):
                result = self.server.get_open_file_text(relative_path)
        return result
    
    def get_definition(self, word, relative_path, line=None, offset=0, verbose=False):
        doc = self.open_file(relative_path)
        cursor_pos = word_to_position(doc, word, line=line, offset=offset)
        with self.server.start_server():
            output = self.server.request_definition(relative_path, **cursor_pos)
        if verbose and len(output) > 0:
            symbols = self.get_symbols(output[0]["relativePath"])
            symbol = matching_symbols(symbols, output[0])
            symbol_type = matching_kind_symbol(symbol)
            definition = add_num_line(get_text(self.open_file(output[0]["relativePath"]), symbol["location"]["range"]), symbol["location"]["range"]["start"]["line"])
            output = "Name: " + str(symbol["name"]) + "\n" + "Type: " + str(symbol_type) + "\n" + "Definition: " + definition
            
        return output
    
    def get_symbols(self, relative_path, verbose_level=1, verbose=False, preview_size=10):
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
        with self.server.start_server():
            symbols = self.server.request_document_symbols(relative_path)[0]
        source = self.open_file(relative_path)
        if verbose:
            verbose_output = []
            for item in symbols:
                if verbose_level == 1:
                    definition = get_text(source, item["range"])
                    major_symbols = [SymbolKind.Class, SymbolKind.Function, SymbolKind.Module, SymbolKind.Struct]
                    major_symbols = [int(i) for i in major_symbols]
                    if (item["kind"] in major_symbols):             
                        line_has_name = 0
                        for k in range(len(definition.split("\n"))):
                            if item["name"] in definition.split("\n")[k]:
                                line_has_name = k
                        cha = definition.split("\n")[line_has_name].index(item["name"])
                        
                        with self.server.start_server():
                            documentation = self.server.request_hover(relative_path, item["range"]["start"]["line"], cha)["contents"]
                        if "value" not in documentation:
                            documentation = "None"
                            preview = "\n".join(definition.split("\n")[:preview_size+4])
                        else:
                            preview = "\n".join(definition.split("\n")[:preview_size])
                        preview = add_num_line(preview, item["range"]["start"]["line"])
                        item_out = "Name: " + str(item["name"]) + "\n" + "Type: " + str(matching_kind_symbol(item)) + "\n" + "Preview: " + str(preview) + "\n" + "Documentation: " + str(documentation) + "\n"
                        verbose_output.append(item_out)
                        
                elif verbose_level == 2:
                    definition = get_text(source, item["range"])
                    minor_symbols = [SymbolKind.Class, SymbolKind.Function, SymbolKind.Module, SymbolKind.Struct, SymbolKind.Method]
                    minor_symbols = [int(i) for i in minor_symbols]
                    if (item["kind"] in minor_symbols):          
                        line_has_name = 0
                        for k in range(len(definition.split("\n"))):
                            if item["name"] in definition.split("\n")[k]:
                                line_has_name = k 
                        cha = definition.split("\n")[line_has_name].index(item["name"])
                        with self.server.start_server():
                            documentation = self.server.request_hover(relative_path, item["range"]["start"]["line"], cha)["contents"]
                        if "value" not in documentation:
                            documentation = "None"
                            preview = "\n".join(definition.split("\n")[:preview_size+4])
                        else:
                            preview = "\n".join(definition.split("\n")[:preview_size])
                        preview = add_num_line(preview, item["range"]["start"]["line"])
                        item_out = "Name: " + str(item["name"]) + "\n" + "Type: " + str(matching_kind_symbol(item)) + "\n" + "Preview: " + str(preview) + "\n" + "Documentation: " + str(documentation) + "\n"
                        verbose_output.append(item_out)
                        
            symbols = verbose_output
        return symbols
    
    def get_references(self, word, relative_path, line=None, offset=0, verbose=False, context_size=10):
        doc = self.open_file(relative_path)
        try:
            cursor_pos = word_to_position(doc, word, line=line, offset=offset)
        except ValueError:
            ## LLM sometimes send the wrong line number or not aware of the line number
            cursor_pos = word_to_position(doc, word, line=None, offset=offset)
        with self.server.start_server():
            output = self.server.request_references(relative_path, **cursor_pos)
    
        if verbose: 
            verbose_output = []
            for item in output:
                doc_item = self.open_file(item["relativePath"])
                item["range"]["start"]["line"] = max(0, item["range"]["start"]["line"] - context_size)
                item["range"]["end"]["line"] = min(len(doc_item.splitlines(True)), item["range"]["end"]["line"] + context_size)
                item["range"]["start"]["character"] = 0
                item["range"]["end"]["character"] = len(doc_item.splitlines(True)[item["range"]["end"]["line"]-1])
                implementation = get_text(doc_item, item["range"])
                results = []
                for idx, _line in enumerate(implementation.split("\n")):
                    _line = str(idx + item["range"]["start"]["line"]) + " " + _line
                    results.append(_line)
                    
                implementation = "\n".join(results)
                
                item_out = "File Name: " + str(item["relativePath"]) + "\n" + "Implementation: " + str(implementation) + "\n"
                verbose_output.append(item_out)
            output = verbose_output
        return output


if __name__ == "__main__":
    test_path = "/datadrive05/huypn16/focalcoder/data/repos/repo__karatelabs__karate__commit__"
    lsp = LSPToolKit(test_path, language="java")
    output = lsp.get_symbols(relative_path="karate-core/src/main/java/com/intuit/karate/Runner.java", verbose=True)
    print(output)