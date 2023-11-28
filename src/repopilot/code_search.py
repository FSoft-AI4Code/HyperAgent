import logging
from codetext.utils import parse_code
from codetext.parser import PythonParser, CsharpParser, RustParser, JavaParser
from repopilot.utils import add_num_line
import os
import jedi 

logging.getLogger('codetext').setLevel(logging.WARNING)

def get_node_text(start_byte, end_byte, code):
    return code[start_byte:end_byte]

def get_parser(language):
    if language == "python":
        return PythonParser()
    elif language == "csharp":
        return CsharpParser()
    elif language == "rust":
        return RustParser()
    elif language == "java":
        return JavaParser()
    else:
        raise NotImplementedError(f"Language {language} is not supported yet")

def get_code_jedi(definition, verbose=False):
    raw = definition.get_line_code(after=definition.get_definition_end_position()[0]-definition.get_definition_start_position()[0])
    start_num_line = definition.get_definition_start_position()[0] - 2 # jedi start from 1
    if not verbose:
        return raw
    else:
        results = []
        splited_raw = raw.split("\n")
        for idx, line in enumerate(splited_raw):
            new_line = str(start_num_line + 1) + " " + line
            results.append(new_line)
            start_num_line += 1
        return "\n".join(results)

def search_py_elements_inside_project(names, backend, num_result=2, verbose=False):
    """Get all matched identifiers from a repo
    
    Args:
        name (str): The name of the identifier
        repo_path (str): The path to the repo
        
    Returns:
        list: A list of matched identifiers
    """
    output_dict = {name: [] for name in names}
    for name in names:
        if not name.endswith(".py"):
            class_definitions = backend.search(f"class {name}", all_scopes=True)
            function_definitions = backend.search(f"def {name}", all_scopes=True)
            variable_definitions = backend.search(name, all_scopes=True)
            idx = 0
            for definition in class_definitions:
                if definition.is_definition():
                    extracted_definition = {
                        "name": definition.name,
                        "full_name": definition.full_name,
                        "documentation": definition._get_docstring(),
                        "implementation": get_code_jedi(definition, verbose)
                    }
                    output_dict[name].append(extracted_definition)
                    idx += 1
                    if idx == num_result:
                        break
            
            idx = 0
            for definition in function_definitions:
                if definition.is_definition():
                    extracted_definition = {
                        "name": definition.name,
                        "full_name": definition.full_name,
                        "documentation": definition._get_docstring(),
                        "implementation": get_code_jedi(definition, verbose),
                    }
                    output_dict[name].append(extracted_definition)
                    idx += 1
                    if idx == num_result:
                        break
            
            idx = 0
            for definition in variable_definitions:
                extracted_definition = {
                    "name": definition.name,
                    "full_name": definition.full_name,
                    "documentation": None,
                    "implementation": definition.description,
                }
                output_dict[name].append(extracted_definition)
                idx += 1
                if idx == num_result:
                    break
        else:
            definitions = backend.search(name.replace(".py", ""))
            for definition in definitions:
                implementation = ""
                with open(definition.module_path, "r") as f:
                    implementation += f.read()
                extracted_definition = {
                    "name": name,
                    "implementation": implementation
                }
                output_dict[name].append(extracted_definition)
            
    return output_dict
    
def search_zoekt_elements_inside_project(names, backend, num_result=2, verbose=False):
    parser = get_parser(backend.language)
    search_results = {name: [] for name in names}
    with backend.start_server():
        zoekt_results = backend.search([f"sym:{name}" for name in names], num_result=num_result)
    for name in names:
        files = zoekt_results[f'sym:{name}']["result"]["FileMatches"]
        for file in files:
            source = open(os.path.join(backend.repo_path, file["FileName"]), "r").read()
            root_node = parse_code(source, backend.language).root_node
            function_list = parser.get_function_list(root_node)
            class_list = parser.get_class_list(root_node)
            for func in function_list:
                metadata = parser.get_function_metadata(func, source)
                if name in metadata["identifier"]:
                    result = {
                        "file": file["FileName"],
                        "name": metadata["identifier"],
                        "documentation": parser.get_docstring(func, source),
                        "implementation": add_num_line(get_node_text(func.start_byte, func.end_byte, source), func.start_point[0])
                    } 
                    search_results[name].append(result)
            for cls in class_list:
                metadata = parser.get_class_metadata(cls, source)
                if name in metadata["identifier"]:
                    result = {
                        "file": file["FileName"],
                        "name": metadata["identifier"],
                        "documentation": parser.get_docstring(cls, source),
                        "implementation": add_num_line(get_node_text(cls.start_byte, cls.end_byte, source), cls.start_point[0])
                    } 
                    search_results[name].append(result)
        
    return search_results
    
def search_elements_inside_project(names, backend, verbose, language):
    if language == "python":
        assert backend == jedi.Project, "backend must be jedi.Project"
        return search_py_elements_inside_project(names, backend, verbose=verbose)
    else:
        return search_zoekt_elements_inside_project(names, backend, verbose=verbose)

if __name__ == "__main__":
    from codetext.utils import build_language
    from repopilot.zoekt.zoekt_server import ZoektServer
    language = "rust"
    path = "data/repos/tokenizers"
    backend = ZoektServer(language)
    backend.setup_index(path)
    build_language(language)
    
    # we want to search function is_valid_sentencepiece method inside the project in Rust lang
    results = search_elements_inside_project(["Unigram"], backend, verbose=True, language=language)
    print(results["Unigram"][0]["implementation"])