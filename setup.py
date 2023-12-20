from setuptools import setup, find_packages

VERSION = '0.0.1' 
# Setting up
setup(
        name="repopilot", 
        version=VERSION,
        author="Huy Phan Nhat",
        author_email="HuyPN16@fpt.com",
        packages=find_packages(where="src"),
        package_dir={'': 'src'},
        install_requires=["langchain", 
                          "fastapi",
                          "openai", 
                          "tree-sitter", 
                          "tree-sitter-languages", 
                          "vllm",
                          "datasets",
                          "Click",
                          "codetext",
                          "fire",
                          "chromadb",
                          "tiktoken"], # add any additional packages that 
        # needs to be installed along with your package. Eg: 'caer'
        entry_points={"console_scripts": ['repopilot = repopilot.cli:main',],},
)