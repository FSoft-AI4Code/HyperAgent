import re

from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.schema.language_model import BaseLanguageModel
from langchain.schema.messages import SystemMessage

from langchain_experimental.plan_and_execute.planners.base import LLMPlanner
from langchain_experimental.plan_and_execute.schema import (
    Plan,
    PlanOutputParser,
    Step,
)
from repopilot.prompts.planner import ADAPTIVE_PLANNER_TEMPLATE, PLANNER_TEMPLATE

SYSTEM_PROMPT = (
    "Let's first understand the problem and devise a plan to solve the problem."
    " Please output the plan starting with the header 'Plan:' "
    "and then followed by a numbered list of steps. "
    "Please make the plan the minimum number of steps required "
    "to accurately complete the task. If the task is a question, "
    "the final step should almost always be 'Given the above steps taken, "
    "please respond to the users original question'. "
    "At the end of your plan, say '<END_OF_PLAN>'"
)


class PlanningOutputParser(PlanOutputParser):
    """Planning output parser."""

    def parse(self, text: str) -> Plan:
        steps = [Step(value=v) for v in re.split("\n\s*\d+\. ", text)[1:]]
        return Plan(steps=steps)

def load_chat_planner(
    llm: BaseLanguageModel, type="static", **kwargs
) -> LLMPlanner:
    """
    Load a chat planner.

    Args:
        llm: Language model.
        system_prompt: System prompt.

    Returns:
        LLMPlanner
    """
    if type == "adaptive":
        system_prompt = ADAPTIVE_PLANNER_TEMPLATE.format(
            struct=kwargs["struct"], 
            formatted_tools=kwargs["formatted_tools"], 
            examples=kwargs["examples"],
        )
        prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=system_prompt),
                HumanMessagePromptTemplate.from_template("Human Request: {input}\n Previous Plan Results{previous_steps}"),
            ]
        )
    elif type == "static":
        system_prompt = PLANNER_TEMPLATE.format(
            struct=kwargs["struct"], 
            formatted_tools=kwargs["formatted_tools"], 
            examples=kwargs["examples"]
        )
        ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=system_prompt),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )
    llm_chain = LLMChain(llm=llm, prompt=prompt_template)
    return LLMPlanner(
        llm_chain=llm_chain,
        output_parser=PlanningOutputParser(),
        stop=["<END_OF_PLAN>"],
    )
