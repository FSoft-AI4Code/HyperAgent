from repopilot.multilspy import SyncLanguageServer
from repopilot.multilspy.multilspy_config import MultilspyConfig
from repopilot.multilspy.multilspy_logger import MultilspyLogger
from repopilot.utils import matching_kind_symbol, matching_symbols, add_num_line, get_text, word_to_position
from repopilot.multilspy.lsp_protocol_handler.lsp_types import SymbolKind
from repopilot.multilspy.multilspy_exceptions import MultilspyException
from repopilot.multilspy import lsp_protocol_handler
from concurrent.futures import ThreadPoolExecutor
import logging

logging.getLogger("multilspy").setLevel(logging.WARNING)

class LSPToolKit:
    def __init__(self, root_path, language="python"):
        self.root_path = root_path
        self.language = language
        self.server = SyncLanguageServer.create(MultilspyConfig(code_language=language), MultilspyLogger(), root_path)
        
    def open_file(self, relative_path):
        try:
            with self.server.start_server():
                try:
                    with self.server.open_file(relative_path):
                        result = self.server.get_open_file_text(relative_path)
                except:
                    return "The tool cannot open the file, the file path is not correct."
        except lsp_protocol_handler.server.Error:
            return "Error: internal server error"
        
        return result
    
    def get_definition(self, word, relative_path, line=None, offset=0, verbose=False):
        doc = self.open_file(relative_path)
        cursor_pos = word_to_position(doc, word, line=line, offset=offset)
        if cursor_pos is not None:
            with self.server.start_server():
                output = self.server.request_definition(relative_path, **cursor_pos)
        else:
            return "The tool cannot find the word in the file"
        if verbose and len(output) > 0:
            symbols = self.get_symbols(output[0]["relativePath"], verbose=False)
            symbol = matching_symbols(symbols, output[0])
            symbol_type = matching_kind_symbol(symbol)
            if "location" not in symbol:
                definition = add_num_line(get_text(self.open_file(output[0]["relativePath"]), symbol["range"]), symbol["range"]["start"]["line"])
            else:
                definition = add_num_line(get_text(self.open_file(output[0]["relativePath"]), symbol["location"]["range"]), symbol["location"]["range"]["start"]["line"])
            output = "Name: " + str(symbol["name"]) + "\n" + "Type: " + str(symbol_type) + "\n" + "Definition: " + definition
            
        return output
    
    def get_symbols(self, relative_path, preview_size=10, verbose=True):
        """Get all symbols in a file

        Args:
            relative_path (_type_): relavtive path to the file
            preview_size (int, optional): only preview preview_size number of lines of definitions to save number of tokens. Defaults to 1.

        Returns:
            _type_: _description_
        """
        with self.server.start_server():
            try:
                symbols = self.server.request_document_symbols(relative_path)[0]
            except MultilspyException:
                return f"The tool cannot open the file, the file path {relative_path} is not correct."
        if not verbose:
            return symbols
        source = self.open_file(relative_path)
        verbose_output = []
        with self.server.start_server():
            for item in symbols:
                definition = get_text(source, item["range"])
                major_symbols = [SymbolKind.Class, SymbolKind.Function, SymbolKind.Struct]
                major_symbols = [int(i) for i in major_symbols]
                if (item["kind"] in major_symbols):             
                    line_has_name = 0
                    for k in range(len(definition.split("\n"))):
                        if item["name"] in definition.split("\n")[k]:
                            line_has_name = k
                    try:
                        cha = definition.split("\n")[line_has_name].index(item["name"])
                        hover = self.server.request_hover(relative_path, item["range"]["start"]["line"], cha)
                        if hover != None:
                            documentation = hover["contents"]
                        else:
                            documentation = "None"
                                
                        if "value" not in documentation:
                            documentation = "None"
                            preview = "\n".join(definition.split("\n")[:preview_size+4])
                        else:
                            preview = "\n".join(definition.split("\n")[:preview_size])
                        preview = add_num_line(preview, item["range"]["start"]["line"])
                        item_out = "Name: " + str(item["name"]) + "\n" + "Type: " + str(matching_kind_symbol(item)) + "\n" + "Preview: " + str(preview) + "\n" + "Documentation: " + str(documentation) + "\n"
                        verbose_output.append(item_out)
                    except ValueError:
                        pass
                          
        symbols = [sym for sym in verbose_output if sym is not None]
        return symbols
    
    def get_references(self, word, relative_path, line=None, offset=0, verbose=False, context_size=10):
        doc = self.open_file(relative_path)
        try:
            cursor_pos = word_to_position(doc, word, line=line, offset=offset)
        except ValueError:
            ## LLM sometimes send the wrong line number or not aware of the line number
            cursor_pos = word_to_position(doc, word, line=None, offset=offset)
            
        if cursor_pos is None:
            return "The tool cannot find the word in the file"
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
    test_path = "/datadrive05/huypn16/focalcoder/data/repos/tokenizers"
    lsp = LSPToolKit(test_path, language="rust")
    output = lsp.get_references(word="RobertaProcessing", line=27, relative_path="tokenizers/src/processors/roberta.rs", verbose=True)
    print(output)