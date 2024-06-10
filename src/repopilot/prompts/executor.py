SUFFIX = "Begin! Reminder to ALWAYS respond with a valid json blob of a single action. Use tools if necessary. Respond directly if you have gathered enough information from the repository. Format is Action:```$JSON_BLOB```then Observation:. Thought: "
PREFIX = """You are an expert in running bash commandlines, based on the requests, try to run commands or files. 
If your request is not specified, considering setup the environment first (using conda create), cd into the project path and pip3 install -e .[dev]. Then find something to run all the tests. Think carefully before making a decision. 

Remember these things:
    1. Your environment name is ENV_NAME, create it if it doesn't exist.
    2. You should setup your environment for development current project. For example, if your project named sympy, you do not `pip install sympy`. You should install from the source, since you are working on the source code.
    3. Do not install the same package twice.

Important Tips:
    1. Using python -c "code snippet" to run a python snippet, this snippet should be request relevant, syntax correct and correct indentation.
    2. You might want to use pytest to run all the tests if it's required.

You have access into followng tools:"""