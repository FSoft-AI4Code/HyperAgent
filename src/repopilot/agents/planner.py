import re
import ast

from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.messages import SystemMessage

from langchain_experimental.plan_and_execute.planners.base import LLMPlanner
from langchain_experimental.plan_and_execute.schema import PlanOutputParser
from repopilot.prompts.planner import PLANNER_TEMPLATE
import json
import re

def parse_manual(text):
    # Extract the action and input from the text
    action = text.split("Action: ")[1]
    agent_type = "Code Generator" if "Code Generator" in action else None
    agent_type = "Codebase Navigator" if "Codebase Navigator" in action else agent_type
    agent_type = "Bash Executor" if "Bash Executor" in action else agent_type
    request = action.split("request")[1].split("terminated")[0]
    terminated = False if "false" in action else True
    return {"agent_type": agent_type, "request": request, "terminated": terminated}

def parse_string_to_dict(s):
    # Remove leading and trailing whitespaces (if any)
    s = s.strip()

    # Split the string by the top-level commas, ignoring commas within quotes
    parts = re.split(r', (?=\w+: )', s)

    result_dict = {}
    for part in parts:
        key, value = part.split(': ', 1)
        key = key.strip().strip('"')
        value = value.strip().strip('"')
        
        # Handle boolean values
        if value.lower() == 'true':
            value = True
        elif value.lower() == 'false':
            value = False
        else:
            # Handle string values, ensuring internal quotes are properly managed
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\"', '"').replace('"', '\"')

        result_dict[key] = value

    return result_dict

class PlanningOutputParser(PlanOutputParser):
    """Planning output parser."""

    def parse(self, text: str):
        text = text.replace("```python", "")
        # pattern = r'Action:\s*(\{.*?\})'
        pattern = re.compile(r"```(?:json\s+)?(\W.*?)```", re.DOTALL)

        # Search for the pattern in the text
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1).strip(), strict=False) 
            except json.decoder.JSONDecodeError:
                return parse_manual(text)
        else:
            return parse_string_to_dict(text.split("Action: ")[1])

def load_chat_planner(
    llm: BaseLanguageModel, **kwargs
) -> LLMPlanner:
    """
    Load a chat planner.

    Args:
        llm: Language model.
        system_prompt: System prompt.

    Returns:
        LLMPlanner
    """
    system_prompt = PLANNER_TEMPLATE.format(
        struct=kwargs["struct"], 
        formatted_agents=kwargs["formatted_agents"], 
    )
    prompt_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=system_prompt),
            HumanMessagePromptTemplate.from_template("Planner Query <Focus Here!>: \n```{input}```\nAgent Scratchpad : \n```{previous_steps}```"),
        ]
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt_template)
    return LLMPlanner(
        llm_chain=llm_chain,
        output_parser=PlanningOutputParser(),
        stop=["Observation:"]
    )
    
    
