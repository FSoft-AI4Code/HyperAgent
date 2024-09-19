import docker
from hyperagent.tools.tools import *
from hyperagent.prompts.utils import jupyter_prompt
from autogen.coding.base import CodeBlock
from autogen.coding.jupyter import EmbeddedIPythonCodeExecutor
from autogen.coding import DockerCommandLineCodeExecutor
from autogen.coding.docker_commandline_code_executor import _wait_for_ready
from autogen.coding.base import CodeBlock, CommandLineCodeResult
from autogen.code_utils import TIMEOUT_MSG, _cmd
from autogen.coding.utils import _get_file_name_from_content, silence_pip
from hashlib import md5

import atexit
import logging
from typing import Any, ClassVar, Dict, List, Optional, Type, Union

from docker.errors import ImageNotFound
from pathlib import Path

class EICE(EmbeddedIPythonCodeExecutor):
    # Override the execute_code_blocks method to only execute the tool functions or initialization of these functions. 
    def execute_code_blocks(self, code_blocks: List[CodeBlock]):
        tool_call_code_blocks = [block for block in code_blocks if "_run" in block.code or "Initialize" in block.code]
        return super().execute_code_blocks(tool_call_code_blocks)

class DCLCE(DockerCommandLineCodeExecutor):
    def __init__(
        self,
        image: str = "python:3-slim",
        container_name: Optional[str] = None,
        timeout: int = 60,
        work_dir: Union[Path, str] = Path("."),
        bind_dir: Optional[Union[Path, str]] = None,
        auto_remove: bool = True,
        stop_container: bool = True,
        execution_policies: Optional[Dict[str, bool]] = None,
    ):
        if timeout < 1:
            raise ValueError("Timeout must be greater than or equal to 1.")

        if isinstance(work_dir, str):
            work_dir = Path(work_dir)
        work_dir.mkdir(exist_ok=True)

        if bind_dir is None:
            bind_dir = work_dir
        elif isinstance(bind_dir, str):
            bind_dir = Path(bind_dir)

        client = docker.from_env()
        # Check if the image exists
        try:
            client.images.get(image)
        except ImageNotFound:
            logging.info(f"Pulling image {image}...")
            # Let the docker exception escape if this fails.
            client.images.pull(image)

        if container_name is None:
            container_name = f"autogen-code-exec-{uuid.uuid4()}"

        # Start a container from the image, read to exec commands later
        self._container = client.containers.create(
            image,
            name=container_name,
            entrypoint="/bin/sh",
            tty=True,
            auto_remove=auto_remove,
            volumes={str(bind_dir.resolve()): {"bind": "/workspace/repository", "mode": "rw"}, str(work_dir.resolve()): {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
        )
        self._container.start()

        _wait_for_ready(self._container)

        def cleanup() -> None:
            try:
                container = client.containers.get(container_name)
                container.stop()
            except docker.errors.NotFound:
                pass
            atexit.unregister(cleanup)

        if stop_container:
            atexit.register(cleanup)

        self._cleanup = cleanup

        # Check if the container is running
        if self._container.status != "running":
            raise ValueError(f"Failed to start container from image {image}. Logs: {self._container.logs()}")

        self._timeout = timeout
        self._work_dir: Path = work_dir
        self._bind_dir: Path = bind_dir
        self.execution_policies = self.DEFAULT_EXECUTION_POLICY.copy()
        if execution_policies is not None:
            self.execution_policies.update(execution_policies)
        
        self.command_history = []
        self.latest_execution_out_str = ""
    
    def execute_code_blocks(self, code_blocks: List[CodeBlock]) -> CommandLineCodeResult:
        """(Experimental) Execute the code blocks and return the result.

        Args:
            code_blocks (List[CodeBlock]): The code blocks to execute.

        Returns:
            CommandlineCodeResult: The result of the code execution."""

        if len(code_blocks) == 0:
            raise ValueError("No code blocks to execute.")

        outputs = []
        files = []
        last_exit_code = 0
        for code_block in code_blocks:
            lang = self.LANGUAGE_ALIASES.get(code_block.language.lower(), code_block.language.lower())
            if lang not in self.DEFAULT_EXECUTION_POLICY:
                outputs.append(f"Unsupported language {lang}\n")
                last_exit_code = 1
                break

            execute_code = self.execution_policies.get(lang, False)
            code = silence_pip(code_block.code, lang)

            # Check if there is a filename comment
            try:
                filename = _get_file_name_from_content(code, self._work_dir)
            except ValueError:
                outputs.append("Filename is not in the workspace")
                last_exit_code = 1
                break

            if not filename:
                filename = f"tmp_code_{md5(code.encode()).hexdigest()}.{lang}"

            code_path = self._work_dir / filename

            with code_path.open("w", encoding="utf-8") as fout:
                fout.write("source /opt/miniconda3/bin/activate\n")
                fout.write("conda activate testbed\n")
                fout.write("cd /workspace/repository\n")
                fout.write(code)
            files.append(code_path)

            if not execute_code:
                outputs.append(f"Code saved to {str(code_path)}\n")
                continue

            command = ["timeout", str(self._timeout), _cmd(lang), filename]
            result = self._container.exec_run(command)
            exit_code = result.exit_code
            output = result.output.decode("utf-8")
            if exit_code == 124:
                output += "\n" + TIMEOUT_MSG
            outputs.append(output)

            last_exit_code = exit_code
            if exit_code != 0:
                break

        code_file = str(files[0]) if files else None
        return CommandLineCodeResult(exit_code=last_exit_code, output="".join(outputs), code_file=code_file)
    
def initialize_tools(repo_dir, db_path, index_path, language, image_name):
    initialized_codeblock = jupyter_prompt.format(repo_dir=repo_dir, index_path=index_path, language=language)
    initialized_codeblock = CodeBlock(code=initialized_codeblock, language="python")
    
    jupyter_executor = EICE(kernel_name="hyperagent", timeout=120)
    result = jupyter_executor.execute_code_blocks([initialized_codeblock])
    
    if result.exit_code != 0:
        print("bug!", result)
        raise Exception(f"Failed to initialize tools: {result}")
    else:
        print("Tools initialized successfully")

    docker_executor = DCLCE(image=image_name, bind_dir=repo_dir, work_dir="/tmp/autogen")    
    return jupyter_executor, docker_executor

if __name__ == "__main__":
    repo_dir = "/datadrive5/huypn16/HyperAgent-Master/data/repos/repo__astropy__astropy__commit__19cc80471739bcb67b7e8099246b391c355023ee"
    docker_executor = DCLCE(image="sweb.eval.x86_64.astropy__astropy-13453:latest", bind_dir=repo_dir, work_dir="/tmp/autogen")

    from hyperagent.prompts.executor import system_exec
    from autogen import UserProxyAgent, AssistantAgent, GroupChat, GroupChatManager, Agent, ConversableAgent
    from autogen.agentchat.contrib.society_of_mind_agent import SocietyOfMindAgent 

    llm_config = [{
        "model": "claude-3-5-sonnet-20240620",
        "api_type": os.environ.get("ANTHROPIC_API_KEY"),
        "stop_sequences": ["\nObservation:"],
        "price": [0.003, 0.015],
        "base_url": "https://api.anthropic.com",
        "api_type": "anthropic",
    }]

    executor_assistant = AssistantAgent(
        "Inner-Executor-Assistant",
        system_message=system_exec,
        llm_config={"config_list": llm_config},
        human_input_mode="NEVER",
    )

    executor_interpreter = UserProxyAgent(
        name="Executor Interpreter",
        llm_config=False,
        code_execution_config={
            "executor": docker_executor,
        },
        human_input_mode="NEVER",
        default_auto_reply="",
    )

    groupchat_exec = GroupChat(
        agents=[executor_assistant, executor_interpreter],
        messages=[],
        speaker_selection_method="round_robin",  # With two agents, this is equivalent to a 1:1 conversation.
        allow_repeat_speaker=False,
        max_round=15,
    )
    
    manager_exec = GroupChatManager(
        groupchat=groupchat_exec,
        name="Executor Manager",
        llm_config={"config_list": llm_config},
        max_consecutive_auto_reply=0
    )
    
    executor = SocietyOfMindAgent(
        "Executor",
        chat_manager=manager_exec,
        llm_config={"config_list": llm_config},
        # response_preparer=response_preparer
    )

    user_proxy = UserProxyAgent(
        name="Admin",
        system_message="A human admin. Interact with the planner to discuss the plan to resolve a codebase-related query.",
        human_input_mode="ALWAYS",
        code_execution_config=False,
        default_auto_reply="",
        max_consecutive_auto_reply=0
    )

    user_proxy.initiate_chat(executor, message="how many folders inside the project")