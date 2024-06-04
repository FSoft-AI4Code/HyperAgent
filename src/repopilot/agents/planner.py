import re
import ast

from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.messages import SystemMessage

from langchain_experimental.plan_and_execute.planners.base import LLMPlanner
from langchain_core.output_parsers import BaseOutputParser
from langchain_experimental.plan_and_execute.schema import PlanOutputParser
from repopilot.prompts.planner import PLANNER_TEMPLATE
import json
import re

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
        text = text.replace("```", "")
        text = text.replace("Thought:", "")
        pattern = r'Action:\s*(\{.*?\})'

        # Search for the pattern in the text
        match = re.search(pattern, text, re.DOTALL)
        if match:
            action_str = match.group(1)
            # Convert the string representation of the dictionary to an actual dictionar
            return json.loads(action_str, strict=False)   
        elif "json" in text:
            json_txt = text.split("json")[1].replace("```", "").strip()
            return json.loads(json_txt)
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
            HumanMessagePromptTemplate.from_template("Human Request: \n```{input}```\nPrevious Plan Results: \n```{previous_steps}```"),
        ]
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt_template)
    return LLMPlanner(
        llm_chain=llm_chain,
        output_parser=PlanningOutputParser()
    )
    
    
