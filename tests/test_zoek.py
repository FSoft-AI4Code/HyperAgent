from codetext.utils import build_language
from repopilot.code_search import search_elements_inside_project
from repopilot.zoekt.zoekt_server import ZoektServer
language = "rust"
path = "data/repos/tokenizers"
backend = ZoektServer(language)
backend.setup_index(path)
build_language(language)

# we want to search function is_valid_sentencepiece method inside the project in Rust lang
results = search_elements_inside_project(["Unigram"], backend, verbose=True, language=language)
print(results["Unigram"][0]["implementation"])