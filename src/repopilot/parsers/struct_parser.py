from __future__ import annotations

import json
import logging
import re
import ast
from typing import Optional, Union

from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseLanguageModel
from langchain_core.pydantic_v1 import Field

from langchain.agents.agent import AgentOutputParser
from langchain.agents.structured_chat.prompt import FORMAT_INSTRUCTIONS
from langchain.output_parsers import OutputFixingParser

logger = logging.getLogger(__name__)

def extract_action_and_input(text):
    pattern = r'```\n{\n.*?}\n```'
    # Find all matches
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        if "action" in match:
            extracted_dict = json.loads(match.replace("```", ""), strict=False)
            break
    
    if len(extracted_dict) == 0:
        return {"action": "Final Answer", "action_input": text}
    
    return extracted_dict

class StructuredChatOutputParser(AgentOutputParser):
    """Output parser for the structured chat agent."""

    format_instructions: str = FORMAT_INSTRUCTIONS
    """Default formatting instructions"""

    pattern = re.compile(r"```(?:json\s+)?(\W.*?)```", re.DOTALL)
    """Regex pattern to parse the output."""

    def get_format_instructions(self) -> str:
        """Returns formatting instructions for the given output parser."""
        return self.format_instructions

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        try:
            if "Bash Executor" in text:
                pattern = r'"request":\s*"(.*?)",\s*"terminated"'
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    request_string = match.group(1)
                    return AgentAction("Bash Executor", {"request": request_string}, text)
                else:
                    pass
            if "summary" in text or "summarize" in text or "summarise" in text:
                return AgentFinish({"output": text}, text)
            
            if "action" in text:
                if ("```python" not in text) and ("```\ndef" not in text):
                    action_match = self.pattern.search(text)
                    if action_match is not None:
                        response = json.loads(action_match.group(1).strip(), strict=False)
                        if isinstance(response, list):
                            # gpt turbo frequently ignores the directive to emit a single action
                            logger.warning("Got multiple action responses: %s", response)
                            response = response[0]
                        if response["action"] == "Final Answer":
                            return AgentFinish({"output": response["action_input"]}, text)
                        else:
                            return AgentAction(
                                response["action"], response.get("action_input", {}), text
                            )
                    else:
                        return AgentFinish({"output": text}, text)
                else:
                    response = extract_action_and_input(text)
                    if response["action"] == "Final Answer":
                        return AgentFinish({"output": response["action_input"]}, text)
                    else:
                        return AgentAction(
                            response["action"], response.get("action_input", {}), text
                    )
            else:
                if "Final Answer:" in text:
                    text = text.split("Final Answer:")[1]
                    return AgentFinish({"output": text}, text)
                else:
                    return AgentFinish({"output": text}, text)
        except:
            return AgentFinish({"output": text}, text)

    @property
    def _type(self) -> str:
        return "structured_chat"

class StructuredBashChatOutputParser(AgentOutputParser):
    """Output parser for the structured chat agent."""

    format_instructions: str = FORMAT_INSTRUCTIONS
    """Default formatting instructions"""

    pattern = re.compile(r"```(?:json\s+)?(\W.*?)```", re.DOTALL)
    """Regex pattern to parse the output."""

    def get_format_instructions(self) -> str:
        """Returns formatting instructions for the given output parser."""
        return self.format_instructions

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        text = text.replace("```python", "")
        try:
            action_match = self.pattern.search(text)
            if action_match is not None:
                response = json.loads(action_match.group(1).strip(), strict=False)
                if isinstance(response, list):
                    # gpt turbo frequently ignores the directive to emit a single action
                    logger.warning("Got multiple action responses: %s", response)
                    response = response[0]
                if response["action"] == "Final Answer":
                    return AgentFinish({"output": response["action_input"]}, text)
                else:
                    return AgentAction(
                        response["action"], response.get("action_input", {}), text
                    )
            else:
                return AgentFinish({"output": text}, text)
        except Exception as e:
            # Define the regex patterns for each field
            patch_pattern = r'"patch":\s*"([^"]*)"'
            start_line_pattern = r'"start_line":\s*(\d+)'
            end_line_pattern = r'"end_line":\s*(\d+)'
            path_pattern = r'"relative_file_path":\s*"([^"]*)"'

            # Find matches for each pattern
            patch_match = re.search(patch_pattern, text)
            start_line_match = re.search(start_line_pattern, text)
            end_line_match = re.search(end_line_pattern, text)
            relative_file_path_match = re.search(path_pattern, text)
            relative_file_path = relative_file_path_match.group(1) if relative_file_path_match else None

            # Extract the values if the matches are found
            patch_string = patch_match.group(1).replace('\\n', '\n') if patch_match else None
            start_line = int(start_line_match.group(1)) if start_line_match else None
            end_line = int(end_line_match.group(1)) if end_line_match else None
            return AgentAction("editor_file", {"patch": patch_string, "start_line": start_line, "end_line": end_line, "relative_file_path": relative_file_path}, text)

    @property
    def _type(self) -> str:
        return "structured_chat"

class StructuredGeneratorChatOutputParser(AgentOutputParser):
    """Output parser for the structured chat agent."""

    format_instructions: str = FORMAT_INSTRUCTIONS
    """Default formatting instructions"""

    pattern = re.compile(r"```(?:json\s+)?(\W.*?)```", re.DOTALL)
    """Regex pattern to parse the output."""

    def get_format_instructions(self) -> str:
        """Returns formatting instructions for the given output parser."""
        return self.format_instructions
    
    def escape_inner_quotes(json_str):
    # Pattern to find the 'patch' value
        pattern = r'("patch":\s*")(.*?)([^\\]")'
        # Replacement function to escape double quotes
        def replacer(match):
            start = match.group(1)
            content = match.group(2).replace('"', '\\"')
            end = match.group(3)
            return f'{start}{content}{end}'
        # Apply the replacement
        return re.sub(pattern, replacer, json_str, flags=re.DOTALL)
    
    def extract_fields(self, json_str):
        fields = {}

        # Extract relative_file_path
        relative_file_path_match = re.search(r'"relative_file_path":\s*"([^"]+)"', json_str)
        if relative_file_path_match:
            fields['relative_file_path'] = relative_file_path_match.group(1)

        # Extract start_line
        start_line_match = re.search(r'"start_line":\s*(\d+)', json_str)
        if start_line_match:
            fields['start_line'] = int(start_line_match.group(1))

        # Extract end_line
        end_line_match = re.search(r'"end_line":\s*(\d+)', json_str)
        if end_line_match:
            fields['end_line'] = int(end_line_match.group(1))

        # Extract patch (handling multiline and escaped quotes)
        patch_match = re.search(r'"patch":\s*"((?:[^"\\]|\\.)*?)"', json_str, re.DOTALL)
        if patch_match:
            # Manually evaluate the patch value to handle escaped quotes and newlines
            patch_value = patch_match.group(1)
            fields['patch'] = ast.literal_eval(f'"{patch_value}"')

        return fields

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        if "Final Answer" not in text:
            if "editor_file" not in text:
                action_match = self.pattern.search(text)
                if action_match is not None:
                    response = json.loads(action_match.group(1).strip(), strict=False)
                    if isinstance(response, list):
                        # gpt turbo frequently ignores the directive to emit a single action
                        logger.warning("Got multiple action responses: %s", response)
                        response = response[0]
                    if response["action"] == "Final Answer":
                        return AgentFinish({"output": response["action_input"]}, text)
                    else:
                        return AgentAction(
                            response["action"], response.get("action_input", {}), text
                        )
                else:
                    return AgentFinish({"output": text}, text)
            else:
                response = self.extract_fields(text)
                return AgentAction(
                    "editor_file", response, text
                )
        else:
            text = text.split("Final Answer")[1]
            return AgentFinish({"output": text}, text)

    @property
    def _type(self) -> str:
        return "structured_chat"
    
class StructuredChatOutputParserWithRetries(AgentOutputParser):
    """Output parser with retries for the structured chat agent."""

    base_parser: AgentOutputParser = Field(default_factory=StructuredChatOutputParser)
    """The base parser to use."""
    output_fixing_parser: Optional[OutputFixingParser] = None
    """The output fixing parser to use."""

    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        try:
            if self.output_fixing_parser is not None:
                parsed_obj: Union[
                    AgentAction, AgentFinish
                ] = self.output_fixing_parser.parse(text)
            else:
                parsed_obj = self.base_parser.parse(text)
            return parsed_obj
        except Exception as e:
            raise OutputParserException(f"Could not parse LLM output: {text}") from e

    @classmethod
    def from_llm(
        cls,
        llm: Optional[BaseLanguageModel] = None,
        base_parser: Optional[StructuredChatOutputParser] = None,
    ) -> StructuredChatOutputParserWithRetries:
        if llm is not None:
            base_parser = base_parser or StructuredChatOutputParser()
            output_fixing_parser: OutputFixingParser = OutputFixingParser.from_llm(
                llm=llm, parser=base_parser
            )
            return cls(output_fixing_parser=output_fixing_parser)
        elif base_parser is not None:
            return cls(base_parser=base_parser)
        else:
            return cls()

    @property
    def _type(self) -> str:
        return "structured_chat_with_retries"
