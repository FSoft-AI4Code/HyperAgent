ReAct_prompt = """Use the following format:

Thought: you should always think about what to do
Action: the action as block of code to take 
Observation: the result of the action
... (this process can repeat multiple times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

For example:

Query: Please find the file and function definition for the `separability_matrix` function in the astropy codebase.

Thought: To find the definition of the `separability_matrix` function, I will first search for it in the codebase using the `code_search` tool.

Action:
```python
result = code_search._run(names=["separability_matrix"])
print(result)
```

Observation:
Results for separability_matrix:
====================
File: astropy/modeling/separable.py
Name: separability_matrix
Line Range: (65, 101)
Documentation: 
    Compute the correlation between outputs and inputs.

    Parameters
    ----------
    transform : `~astropy.modeling.core.Model`
        A (compound) model.

    Returns
    -------
    separable_matrix : ndarray
        A boolean correlation matrix of shape (n_outputs, n_inputs).
        Indicates the dependence of outputs on inputs. For completely
        independent outputs, the diagonal elements are True and
        off-diagonal elements are False.

    Examples
    --------
    >>> from astropy.modeling.models import Shift, Scale, Rotation2D, Polynomial2D
    >>> separability_matrix(Shift(1) & Shift(2) | Scale(1) & Scale(2))
        array([[ True, False], [False,  True]]...)
    >>> separability_matrix(Shift(1) & Shift(2) | Rotation2D(2))
        array([[ True,  True], [ True,  True]]...)
    >>> separability_matrix(Shift(1) & Shift(2) | Mapping([0, 1, 0, 1]) | \
        Polynomial2D(1) & Polynomial2D(2))
        array([[ True,  True], [ True,  True]]...)
    >>> separability_matrix(Shift(1) & Shift(2) | Mapping([0, 1, 0, 1]))
        array([[ True, False], [False,  True], [ True, False], [False,  True]]...)

Thought:
The `separability_matrix` function is defined in the `astropy.modeling.separable` module. It takes a `~astropy.modeling.core.Model` object as input and returns a boolean correlation matrix indicating the dependence of the model's outputs on its inputs.
The issue appears to be related to the behavior of the `separability_matrix` function when dealing with nested compound models. To understand this better, I will:

1. Look at the implementation of the `separability_matrix` function.
2. Check if there are any known issues or discussions related to this in the Astropy codebase.

Action:
```python
result = open_file._run(relative_file_path="astropy/modeling/separable.py", keywords=["separability_matrix"], start_line=65, end_line=101)
print(result)
```



Begin!
Query: {input}""" 


jupyter_prompt = """from hyperagent.tools.tools import *
repo_dir = "{repo_dir}"
language = "{language}"
index_path = "{index_path}"

nav_tool_cls = [CodeSearchTool, GoToDefinitionTool, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool, OpenFileTool, FindFileTool]
gen_tool_cls = [EditorTool, OpenFileToolForGenerator, FindAllReferencesTool, GoToDefinitionTool, GetTreeStructureTool]

# Initialize tools for navigation
code_search = CodeSearchTool(repo_dir, language=language, index_path=index_path, build=True)
go_to_def = GoToDefinitionTool(repo_dir, language=language)
find_all_refs = FindAllReferencesTool(repo_dir, language=language)
get_all_symbols = GetAllSymbolsTool(repo_dir, language=language)
get_folder_structure = GetTreeStructureTool(repo_dir, language=language)
open_file = OpenFileTool(repo_dir, language=language)
find_file = FindFileTool(repo_dir, language=language)

# Initialize tools for editing
editor = EditorTool(repo_dir, language=language)
open_file_gen = OpenFileToolForGenerator(repo_dir, language=language)"""

def react_prompt_message(content):
   request = content.split("Request:")[-1]
   request = request.split("Navigator:")[-1]
   request = request.split("Editor:")[-1]
   request = request.split("Executor:")[-1]
   return ReAct_prompt.format(input=request)