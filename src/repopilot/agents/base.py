from typing import Any, List, Optional, Sequence, Tuple, Union
from langchain.callbacks.manager import Callbacks
from langchain.chains.base import Chain

from langchain_experimental.plan_and_execute.schema import StepResponse
from langchain_experimental.pydantic_v1 import BaseModel
from langchain_core.language_models import BaseLanguageModel
from langchain_experimental.plan_and_execute.executors.base import BaseExecutor
from langchain_core.prompts import BasePromptTemplate
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_core.pydantic_v1 import Field

from langchain.agents.agent import Agent, AgentOutputParser
from langchain.agents.structured_chat.prompt import FORMAT_INSTRUCTIONS, PREFIX, SUFFIX
from langchain.callbacks.base import BaseCallbackManager
from langchain.chains.llm import LLMChain
from langchain.tools import BaseTool
from langchain_core.agents import AgentAction, AgentFinish
from repopilot.parsers.struct_parser import (
    StructuredChatOutputParserWithRetries,
)

import re
import os
import json

HUMAN_MESSAGE_TEMPLATE = "{input}\n\n{agent_scratchpad}"

class ChainExecutor(BaseExecutor):
    """Chain executor."""

    chain: Chain
    """The chain to use."""
    name: str = "Chain Executor"
    description: str = "Executes a chain of tools."

    def step(
        self, inputs: dict, callbacks: Callbacks = None, **kwargs: Any
    ) -> StepResponse:
        """Take step."""
        response = self.chain(inputs, callbacks=callbacks)
        if "intermediate_steps" in response:
            try:
                return StepResponse(response=response["output"]), response["intermediate_steps"]
            except ValueError as e:
                response = str(e)
                if not response.startswith("Could not parse LLM output: "):
                    raise e
                response = response.removeprefix("Could not parse LLM output: `").removesuffix("`")
                return StepResponse(response=response["output"]), response["intermediate_steps"]
        else:
            return StepResponse(response=response["output"])

    async def astep(
        self, inputs: dict, callbacks: Callbacks = None, **kwargs: Any
    ) -> StepResponse:
        """Take step."""
        response = await self.chain.arun(**inputs, callbacks=callbacks)
        return StepResponse(response=response)

class StructuredChatAgent(Agent):
    """Structured Chat Agent."""

    output_parser: AgentOutputParser = Field(
        default_factory=StructuredChatOutputParserWithRetries
    )
    save_trajectories_path: str | None = None
    """Output parser for the agent."""

    @property
    def observation_prefix(self) -> str:
        """Prefix to append the observation with."""
        return "Observation: "

    @property
    def llm_prefix(self) -> str:
        """Prefix to append the llm call with."""
        return "Thought:"

    def _construct_scratchpad(
        self, intermediate_steps: List[Tuple[AgentAction, str]]
    ) -> str:
        agent_scratchpad = super()._construct_scratchpad(intermediate_steps)
        if not isinstance(agent_scratchpad, str):
            raise ValueError("agent_scratchpad should be of type string.")
        if agent_scratchpad:
            return (
                f"This was your previous work "
                f"(but I haven't seen any of it! I only see what "
                f"you return as final answer):\n{agent_scratchpad}"
            )
        else:
            return agent_scratchpad
    
    def plan(
        self,
        intermediate_steps: List[Tuple[AgentAction, str]],
        callbacks: Callbacks = None,
        **kwargs: Any,
    ) -> Union[AgentAction, AgentFinish]:
        """Given input, decided what to do.

        Args:
            intermediate_steps: Steps the LLM has taken to date,
                along with observations
            callbacks: Callbacks to run.
            **kwargs: User inputs.

        Returns:
            Action specifying what tool to use.
        """
        full_inputs = self.get_full_inputs(intermediate_steps, **kwargs)
        input_prompt = self.llm_chain.prep_prompts(input_list=[full_inputs])
        full_output = self.llm_chain.predict(callbacks=callbacks, **full_inputs)
        if self.save_trajectories_path is not None:
            self.save_trajectories(full_output, input_prompt)
        return self.output_parser.parse(full_output)

    def save_trajectories(
        self,
        full_output: dict,
        prompt: str = None,
    ):
        """Save trajectories to file."""
        index = len(os.listdir(self.save_trajectories_path))
        instance = {
            "system_prompt": prompt[0][0].messages[0].content,
            "human_message": prompt[0][0].messages[1].content,
            "system_response": full_output
        }
        with open(os.path.join(self.save_trajectories_path, f"{index}_instance.json"), "w") as f:
            json.dump(instance, f)
        
    @classmethod
    def _validate_tools(cls, tools: Sequence[BaseTool]) -> None:
        pass

    @classmethod
    def _get_default_output_parser(
        cls, llm: Optional[BaseLanguageModel] = None, **kwargs: Any
    ) -> AgentOutputParser:
        return StructuredChatOutputParserWithRetries.from_llm(llm=llm)

    @property
    def _stop(self) -> List[str]:
        return ["Observation:"]

    @classmethod
    def create_prompt(
        cls,
        tools: Sequence[BaseTool],
        prefix: str = PREFIX,
        suffix: str = SUFFIX,
        human_message_template: str = HUMAN_MESSAGE_TEMPLATE,
        format_instructions: str = FORMAT_INSTRUCTIONS,
        input_variables: Optional[List[str]] = None,
        memory_prompts: Optional[List[BasePromptTemplate]] = None,
    ) -> BasePromptTemplate:
        tool_strings = []
        for tool in tools:
            args_schema = re.sub("}", "}}", re.sub("{", "{{", str(tool.args)))
            tool_strings.append(f"{tool.name}: {tool.description}, args: {args_schema}")
        formatted_tools = "\n".join(tool_strings)
        tool_names = ", ".join([tool.name for tool in tools])
        format_instructions = format_instructions.format(tool_names=tool_names)
        template = "\n\n".join([prefix, formatted_tools, format_instructions, suffix])
        if input_variables is None:
            input_variables = ["input", "agent_scratchpad"]
        _memory_prompts = memory_prompts or []
        messages = [
            SystemMessagePromptTemplate.from_template(template),
            *_memory_prompts,
            HumanMessagePromptTemplate.from_template(human_message_template),
        ]
        return ChatPromptTemplate(input_variables=input_variables, messages=messages)

    @classmethod
    def from_llm_and_tools(
        cls,
        llm: BaseLanguageModel,
        tools: Sequence[BaseTool],
        callback_manager: Optional[BaseCallbackManager] = None,
        output_parser: Optional[AgentOutputParser] = None,
        prefix: str = PREFIX,
        suffix: str = SUFFIX,
        human_message_template: str = HUMAN_MESSAGE_TEMPLATE,
        format_instructions: str = FORMAT_INSTRUCTIONS,
        input_variables: Optional[List[str]] = None,
        memory_prompts: Optional[List[BasePromptTemplate]] = None,
        **kwargs: Any,
    ) -> Agent:
        """Construct an agent from an LLM and tools."""
        cls._validate_tools(tools)
        prompt = cls.create_prompt(
            tools,
            prefix=prefix,
            suffix=suffix,
            human_message_template=human_message_template,
            format_instructions=format_instructions,
            input_variables=input_variables,
            memory_prompts=memory_prompts,
        )
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
            callback_manager=callback_manager,
        )
        tool_names = [tool.name for tool in tools]
        _output_parser = output_parser or cls._get_default_output_parser(llm=llm)
        return cls(
            llm_chain=llm_chain,
            allowed_tools=tool_names,
            output_parser=_output_parser,
            **kwargs,
        )

    @property
    def _agent_type(self) -> str:
        raise ValueError
