from typing import List

import re
import openai
from langchain.schema.language_model import BaseLanguageModel
from langchain.tools import BaseTool
from langchain_experimental.plan_and_execute.executors.base import ChainExecutor
from typing import Any, Dict, List, Optional

from langchain.callbacks.manager import (
    CallbackManagerForChainRun,
)
from langchain.chains.base import Chain

from langchain_experimental.plan_and_execute.executors.base import BaseExecutor
from langchain_experimental.plan_and_execute.planners.base import BasePlanner
from langchain_experimental.plan_and_execute.schema import (
    BaseStepContainer,
    ListStepContainer,
)
from langchain_experimental.pydantic_v1 import Field
from langchain.agents.structured_chat.prompt import PREFIX, SUFFIX
from repopilot.agents.base import ChainExecutor, StructuredChatAgent
from repopilot.agents.agent_executor import AgentExecutor
from repopilot.agents.llms import LocalLLM
from repopilot.utils import find_abs_path
from langchain_community.callbacks import get_openai_callback
from repopilot.constants import DEFAULT_TRAJECTORIES_PATH, DO_NOT_SUMMARIZED_KEYS

HUMAN_MESSAGE_TEMPLATE = """Objective: {current_step}
Agent scratchpad:
{agent_scratchpad}"""

NAV_HUMAN_MESSAGE_TEMPLATE = """Objective: {current_step}
Agent scratchpad:
{agent_scratchpad}
"""

GENERATOR_HUMAN_MESSAGE_TEMPLATE = """Objective: {current_step}
File Path To Edit: {file_path}
Agent scratchpad:
{agent_scratchpad}"""


FORMAT_INSTRUCTIONS = """Use a json blob to specify a tool by providing an action key (tool name) and an action_input key (tool input).

Valid "action" values: "Final Answer" or {tool_names}

Provide only ONE action per $JSON_BLOB, as shown:

```
{{{{
  "action": $TOOL_NAME,
  "action_input": $INPUT
}}}}
```

Follow this format:

Thought: consider previous and subsequent steps, notes down some useful information (like code snippet) from observation
Action:
```
$JSON_BLOB
```
Observation: action result
... (repeat Thought/Action/Observation N times)
Thought: I know what to respond
Action:
```
{{{{
  "action": "Final Answer",
  "action_input": "Final response to human"
}}}}
```"""
def filter_response(text):
    text = text.replace("```json", "")
    text = text.replace("action: ", "")
    text = text.replace("Final Answer", "")
    text = text.replace("action_input", "")
    return text

def load_agent_navigator(
    llm: BaseLanguageModel,
    tools: List[BaseTool],
    prefix: str = PREFIX,
    suffix: str = SUFFIX,
    verbose: int = 1,
    include_task_in_prompt: bool = False,
    save_trajectories_path: str = DEFAULT_TRAJECTORIES_PATH,
    
) -> ChainExecutor:
    """
    Load an agent executor.

    Args:
        llm: BaseLanguageModel
        tools: List[BaseTool]
        verbose: bool. Defaults to False.
        include_task_in_prompt: bool. Defaults to False.

    Returns:
        ChainExecutor
    """
    input_variables = ["current_step", "agent_scratchpad", "nav_memory"]
    template = NAV_HUMAN_MESSAGE_TEMPLATE
    format_instructions = FORMAT_INSTRUCTIONS

    agent = StructuredChatAgent.from_llm_and_tools(
        llm,
        tools,
        human_message_template=template,
        input_variables=input_variables,
        prefix=prefix,
        suffix=suffix,
        format_instructions=format_instructions,
    )
    agent.save_trajectories_path = save_trajectories_path
    agent_executor = AgentExecutor.from_agent_and_tools(
        agent=agent, tools=tools, verbose=verbose, return_intermediate_steps=True 
    )
    agent_executor.handle_parsing_errors = True
    return ChainExecutor(chain=agent_executor, name="Codebase Navigator", description="Navigate the codebase to find relevant information or code snippets.")

def load_agent_generator(
    llm: BaseLanguageModel,
    tools: List[BaseTool],
    prefix: str = PREFIX,
    suffix: str = SUFFIX,
    verbose: int = 1,
    include_task_in_prompt: bool = False,
    save_trajectories_path: str = DEFAULT_TRAJECTORIES_PATH,
    
) -> ChainExecutor:
    """
    Load an agent executor.

    Args:
        llm: BaseLanguageModel
        tools: List[BaseTool]
        verbose: bool. Defaults to False.
        include_task_in_prompt: bool. Defaults to False.

    Returns:
        ChainExecutor
    """
    input_variables = ["current_step", "agent_scratchpad", "file_path", "file_content"]
    template = GENERATOR_HUMAN_MESSAGE_TEMPLATE
    format_instructions = FORMAT_INSTRUCTIONS

    agent = StructuredChatAgent.from_llm_and_tools(
        llm,
        tools,
        human_message_template=template,
        input_variables=input_variables,
        prefix=prefix,
        suffix=suffix,
        format_instructions=format_instructions,
    )
    agent.save_trajectories_path = save_trajectories_path
    agent_executor = AgentExecutor.from_agent_and_tools(
        agent=agent, tools=tools, verbose=verbose, return_intermediate_steps=True 
    )
    agent_executor.handle_parsing_errors = True
    return ChainExecutor(chain=agent_executor, name="Code Generator", description="Generate code snippets or patch that can be applied to the codebase.")

def load_agent_executor(
    llm: BaseLanguageModel,
    tools: List[BaseTool],
    prefix: str = PREFIX,
    suffix: str = SUFFIX,
    verbose: int = 1,
    include_task_in_prompt: bool = False,
    save_trajectories_path: str = DEFAULT_TRAJECTORIES_PATH,
    
) -> ChainExecutor:
    """
    Load an agent executor.

    Args:
        llm: BaseLanguageModel
        tools: List[BaseTool]
        verbose: bool. Defaults to False.
        include_task_in_prompt: bool. Defaults to False.

    Returns:
        ChainExecutor
    """
    input_variables = ["current_step", "agent_scratchpad"]
    template = HUMAN_MESSAGE_TEMPLATE
    format_instructions = FORMAT_INSTRUCTIONS

    agent = StructuredChatAgent.from_llm_and_tools(
        llm,
        tools,
        human_message_template=template,
        input_variables=input_variables,
        prefix=prefix,
        suffix=suffix,
        format_instructions=format_instructions,
    )
    agent.save_trajectories_path = save_trajectories_path
    agent_executor = AgentExecutor.from_agent_and_tools(
        agent=agent, tools=tools, verbose=verbose, return_intermediate_steps=True 
    )
    agent_executor.handle_parsing_errors = True
    return ChainExecutor(chain=agent_executor, name="Bash Executor", description="Execute bash commands on the codebase. Suitable for running scripts or commands or testing.")

def load_summarizer():
    config = {"model": "mistralai/Mixtral-8x7B-Instruct-v0.1", "system_prompt": "Summarize the analysis, while remain details such as code snippet that is important.", "max_tokens": 25000}
    summarizer = LocalLLM(config)
    return summarizer

class PlanSeeking(Chain):
    """Plan and execute a chain of steps."""

    planner: BasePlanner
    """The planner to use."""
    navigator: BaseExecutor
    """The executor to use."""
    executor: BaseExecutor
    """The executor to use."""
    generator: BaseExecutor
    """The generator to use."""
    summarizer: LocalLLM
    
    repo_dir: str
    
    step_container: BaseStepContainer = Field(default_factory=ListStepContainer)
    """The step container to use."""
    input_key: str = "input"
    output_key: str = "output"
    analyzer_key: str = "analyzer_input"

    @property
    def input_keys(self) -> List[str]:
        return [self.input_key]

    @property
    def output_keys(self) -> List[str]:
        return [self.output_key]

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        terminated = False
        nav_memory = ""
        
        index = 0
        with get_openai_callback() as cb:
            while not terminated:
                planner_output, planner_response = self.planner.plan(inputs)
                agent_type = planner_output["agent_type"]
                planner_request = planner_output["request"]
                if agent_type == "Codebase Navigator":
                    current_notes = ""
                    nav_inputs = {"current_step": planner_request, "nav_memory": nav_memory}
                    response, intermediate_steps = self.navigator.step(
                        nav_inputs,
                        callbacks=run_manager.get_child() if run_manager else None,
                    )
                    
                    for j, react_step in enumerate(intermediate_steps):
                        if isinstance(react_step[1], list):
                            obs_strings = [str(x) for x in react_step[1]]
                            tool_output = "\n".join(obs_strings)
                        else:
                            tool_output = str(react_step[1])
                            current_notes += f"\nStep:{j}\n\Analysis: {react_step[0].log.split('Action:')[0]}\nOutput: {tool_output}\n"
                    if any([key in response.response for key in DO_NOT_SUMMARIZED_KEYS]):
                        try:
                            current_notes = self.summarizer(current_notes) + "\n" + response.response
                        except openai.BadRequestError:
                            current_notes = response.response
                    else:
                        current_notes = self.summarizer(current_notes + "\n" + filter_response(response.response)) 
                    next_key =  planner_response + "\n"
                    
                    next_key += f"Observation: {current_notes}\n"
                    nav_memory += f"Planner Request: {planner_request} \nYour Result: {response}\n"

                elif agent_type == "Code Generator":
                    pattern = r'`([^`]*)`'

                    # Find all matches
                    matches = re.findall(pattern, planner_request)
                    if matches:
                        file_paths = [match for match in matches if match.endswith(".py")]
                        if len(file_paths) > 0:
                            full_path = find_abs_path(self.repo_dir, file_paths[0])
                        else:
                            full_path = None
                    else:
                        pattern = r"'([^\']*)'"
                        matches = re.findall(pattern, planner_request)
                        file_paths = [match for match in matches if match.endswith(".py")]
                        if len(file_paths) > 0:
                            full_path = find_abs_path(self.repo_dir, file_paths[0])
                        else:
                            full_path = None
                        
                    if full_path is not None:
                        generator_inputs = {"current_step": planner_request, "file_path": file_paths[0] if file_paths else None}
                        response, intermediate_steps = self.generator.step(
                            generator_inputs,
                            callbacks=run_manager.get_child() if run_manager else None,
                        )
                        next_key =  planner_response + "\n"
                        next_key += f"Observation: {response}\n"
                        
                    else:
                        next_key = planner_response + "\n"
                        next_key = f"Observation: File not Found\n"
                
                elif agent_type == "Bash Executor":
                    executor_inputs = {"current_step": planner_request}
                    response, intermediate_steps = self.executor.step(
                        executor_inputs,
                        callbacks=run_manager.get_child() if run_manager else None,
                    )
                    
                    next_key = planner_response + "\n"
                    next_key += f"Observation: {response}\n"
                
                inputs["previous_steps"].append(next_key)
                index += 1
                print(f"Total Tokens: {cb.total_tokens}")
                print(f"Prompt Tokens: {cb.prompt_tokens}")
                print(f"Completion Tokens: {cb.completion_tokens}")
            
        answer = self.planner.output_parser.parse(inputs["previous_steps"])
        
        return {self.output_key: answer}