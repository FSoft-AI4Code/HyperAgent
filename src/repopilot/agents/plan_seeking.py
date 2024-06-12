from typing import List
from langchain.schema.language_model import BaseLanguageModel
from langchain.tools import BaseTool
from typing import Any, Dict, List

from langchain.agents.structured_chat.prompt import PREFIX, SUFFIX
from repopilot.agents.base import ChainExecutor, StructuredChatAgent
from repopilot.agents.agent_executor import AgentExecutor
from repopilot.agents.llms import LocalLLM
from repopilot.langchain_parsers.struct_parser import StructuredGeneratorChatOutputParser, StructuredBashChatOutputParser
from langchain_community.callbacks import get_openai_callback
from repopilot.constants import DEFAULT_TRAJECTORIES_PATH

PLANNER_HUMAN_MESSAGE_TEMPLATE = """Objective: {current_step}
Project Structure:
{struct}
Planner scratchpad:
{agent_scratchpad}
"""

EXEC_HUMAN_MESSAGE_TEMPLATE = """Objective: {current_step}
Execution Memory:
{bash_memory}
Agent scratchpad:
{agent_scratchpad}"""

NAV_HUMAN_MESSAGE_TEMPLATE = """Objective: {current_step}
Agent scratchpad:
{agent_scratchpad}
"""

GENERATOR_HUMAN_MESSAGE_TEMPLATE = """Objective: {current_step}
Editing Context: {context}
Provided Hints: {hints}
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
    text = text.replace('"action_input":', "")
    text = text.replace('"action:"', "")
    text = text.replace("```json", "")
    text = text.replace("Action:", "")
    text = text.replace("action", "")
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
    input_variables = ["current_step", "agent_scratchpad", "file_path", "file_content", "context", "hints"]
    template = GENERATOR_HUMAN_MESSAGE_TEMPLATE
    format_instructions = FORMAT_INSTRUCTIONS

    agent = StructuredChatAgent.from_llm_and_tools(
        llm,
        tools,
        human_message_template=template,
        output_parser=StructuredGeneratorChatOutputParser(),
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
    commit_hash: str = "",
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
    if commit_hash == "":
        commit_hash = input("You did not provide a commit hash, please provide a default name for your environment that executor is going to build.")
    
    
    input_variables = ["current_step", "agent_scratchpad"]
    template = EXEC_HUMAN_MESSAGE_TEMPLATE
    format_instructions = FORMAT_INSTRUCTIONS
    
    agent = StructuredChatAgent.from_llm_and_tools(
        llm,
        tools,
        human_message_template=template,
        input_variables=input_variables,
        output_parser=StructuredBashChatOutputParser(),
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

def load_agent_planner(
    llm: BaseLanguageModel,
    tools: List[BaseTool],
    prefix: str = PREFIX,
    suffix: str = SUFFIX,
    verbose: int = 1,
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
    input_variables = ["current_step", "agent_scratchpad", "struct"]
    template = PLANNER_HUMAN_MESSAGE_TEMPLATE
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
        agent=agent, tools=tools, verbose=verbose, return_intermediate_steps=True, max_iterations=10
    )
    agent_executor.handle_parsing_errors = True
    return ChainExecutor(chain=agent_executor, name="Planner", description="Plan the next steps to resolve the query"
)