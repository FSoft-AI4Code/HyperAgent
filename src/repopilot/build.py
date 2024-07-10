import os
from repopilot.tools.tools import *
from repopilot.prompts.utils import jupyter_prompt
from autogen.coding.base import CodeBlock
from autogen.coding.jupyter import EmbeddedIPythonCodeExecutor

class EICE(EmbeddedIPythonCodeExecutor):
    # Override the execute_code_blocks method to only execute the tool functions or initialization of these functions. 
    def execute_code_blocks(self, code_blocks: List[CodeBlock]):
        tool_call_code_blocks = [block for block in code_blocks if "_run" in block.code or "Initialize" in block.code]
        return super().execute_code_blocks(tool_call_code_blocks)

def initialize_tools(repo_dir, db_path, index_path, language):
    initialized_codeblock = jupyter_prompt.format(repo_dir=repo_dir, index_path=index_path, language=language)
    initialized_codeblock = CodeBlock(code=initialized_codeblock, language="python")
    
    jupyter_executor = EICE(kernel_name="repopilot")
    result = jupyter_executor.execute_code_blocks([initialized_codeblock])
    
    if result.exit_code != 0:
        print("bug!", result)
        raise Exception(f"Failed to initialize tools: {result}")
    else:
        print("Tools initialized successfully")
    
    return jupyter_executor