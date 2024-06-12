from pydantic import BaseModel, Field
import openai
from langchain.tools import BaseTool
from repopilot.agents.plan_seeking import filter_response
from repopilot.agents.base import ChainExecutor
from repopilot.agents.llms import LLM
from typing import Optional

class NavigationArgs(BaseModel):
    request: str = Field(..., description="a detailed request, maybe multiple queries in the same request for navigator to give you neccessary contexts to resolve thought process questions.")
    
class Navigation(BaseTool):
    name: str = "codebase_navigator"
    args_schema = NavigationArgs
    nav_memory: str = ""
    navigator: Optional[ChainExecutor] = None
    summarizer: Optional[LLM] = None
    description: str = "Navigate the codebase to find relevant information or code snippets."

    def __init__(self, _agent, summarizer):
        super().__init__()
        self.navigator = _agent
        self.summarizer = summarizer
    
    def _run(self, request: str = "", title: str = ""):
        if len(request) == 0:
            return "Please provide a detailed request to collect relevant information about the codebase."
        current_notes = ""
        nav_inputs = {"current_step": request, "nav_memory": self.nav_memory}
        response, intermediate_steps = self.navigator.step(nav_inputs)
        
        for j, react_step in enumerate(intermediate_steps):
            if isinstance(react_step[1], list):
                obs_strings = [str(x) for x in react_step[1]]
                tool_output = "\n".join(obs_strings)
            else:
                tool_output = str(react_step[1])
                current_notes += f"\nStep:{j}\n\Analysis: {react_step[0].log.split('Action:')[0]}\nOutput: {tool_output}\n"
        try:
            current_notes = self.summarizer(current_notes) + "\n" + filter_response(response.response)
        except openai.BadRequestError:
            current_notes = response.response
        return current_notes

class CodeGeneratorArgs(BaseModel):
    request: str = Field(..., description="a very detailed request to generate the code snippet or patch, also give it a context. (Important). Also give it a full path to the file you want to edit in format like this `somefolder/somefile.py` (notes `` quote).")
    file_path: str = Field(None, description="The relative path the file that you want to edit.")
    context: str = Field(None, description="The context of why, what, how for the code snippet or patch. You might include the information about the object to edit, which file, what are necessary things to care about.")
    hints: str = Field(None, description="Any hints or additional information that can help the code generator to generate or find the relevant code snippet or patch. (line number or keyword or function name etc.)")
    
class CodeGenerator(BaseTool):
    name: str = "code_generator"
    args_schema = CodeGeneratorArgs
    generator: Optional[ChainExecutor] = None
    summarizer: Optional[LLM] = None
    repo_dir: str = ""
    description: str = "Generate code snippets or patch that can be applied to the codebase."
    
    def __init__(self, _agent, summarizer, repo_dir):
        super().__init__()
        self.generator = _agent
        self.summarizer = summarizer
        self.repo_dir = repo_dir
    
    def _run(self, request: str = "", file_path: str = None, context: str = "", title: str = "", hints: str = ""):
        if len(request) == 0:
            return "You provided no request, request field is empty. Please provide a detailed request to generate the code snippet or patch."
        if file_path:
            generator_inputs = {"current_step": request, "file_path": file_path, "context": context, "hints": hints}
            response, intermediate_steps = self.generator.step(generator_inputs)
            current_notes = response.response
        else:
            current_notes = f"File not Found"
        return current_notes

class BashExecutorArgs(BaseModel):
    request: str = Field(..., description="a detailed request to reproduce the issue or examine whether the human query is resolved.")

class BashExecutor(BaseTool):
    name: str = "bash_executor"
    args_schema = BashExecutorArgs
    bash_memory: str = ""
    executor: Optional[ChainExecutor] = None
    summarizer: Optional[LLM] = None
    description: str = "Execute bash commands on the codebase. Suitable for running scripts or commands or testing."
    
    def __init__(self, _agent, summarizer):
        super().__init__()
        self.executor = _agent
        self.summarizer = summarizer
    
    def _run(self, request: str):
        current_notes = ""
        executor_inputs = {"current_step": request, "bash_memory": self.bash_memory}
        response, intermediate_steps = self.executor.step(executor_inputs)        
        
        for j, react_step in enumerate(intermediate_steps):
            if isinstance(react_step[1], list):
                obs_strings = [str(x) for x in react_step[1]]
                tool_output = "\n".join(obs_strings)
            else:
                tool_output = str(react_step[1])
                current_notes += f"\nStep:{j}\n\Analysis: {react_step[0].log.split('Action:')[0]}\nOutput: {tool_output}\n"
        try:
            current_notes = self.summarizer(current_notes) + "\n" + response.response
        except openai.BadRequestError:
            current_notes = response.response

        return current_notes