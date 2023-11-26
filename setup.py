from setuptools import setup, find_packages

VERSION = '0.0.1' 
DESCRIPTION = 'RepoPilot'
LONG_DESCRIPTION = 'RepoPilot - A Next-Generation Coding Assistant for Codebase Exploration and Analysis'

# Setting up
setup(
        name="repopilot", 
        version=VERSION,
        author="Huy Phan Nhat",
        author_email="HuyPN16@fpt.com",
        description=DESCRIPTION,
        long_description=LONG_DESCRIPTION,
        packages=find_packages(where="src"),
        package_dir={'': 'src'},
        install_requires=["langchain", "openai"], # add any additional packages that 
        # needs to be installed along with your package. Eg: 'caer'
        
        keywords=['LLM', 'NLP'],
        classifiers= [
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Education",
            "Programming Language :: Python :: 2",
            "Programming Language :: Python :: 3",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: Microsoft :: Windows",
        ]
)