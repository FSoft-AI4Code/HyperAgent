import subprocess
import os
import logging
import re
from typing import Optional, List, Mapping, Any
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.llms import VLLM
from repopilot.tools import tool_classes, SemanticCodeSearchTool
from repopilot.utils import clone_repo, check_local_or_remote
from repopilot.agents.planner import load_chat_planner
from repopilot.agents.plan_seeking import load_agent_navigator, load_agent_analyzer, PlanSeeking
from repopilot.agents.adaptive_plan_seeking import AdaptivePlanSeeking
from repopilot.prompts.general_qa import example_qa
from repopilot.prompts import analyzer as analyzer_prompt
from repopilot.prompts import navigator as navigator_prompt
from repopilot.constants import DEFAULT_PLANNER_TYPE, DEFAULT_LOCAL_AGENT, DEFAULT_VERBOSE_LEVEL

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("multilspy").setLevel(logging.FATAL)
logger = logging.getLogger(__name__)


def Setup(
    repo_path: str,
    commit: str,
    openai_api_key: str,
    language: str = "python",
    clone_dir: str = "data/repos",
    examples: List[Mapping[str, Any]] = example_qa,
    save_trajectories_path: Optional[str] = None,
    db_path: Optional[str] = None,  
    local_agent: bool = False,
    planner_type: str = DEFAULT_PLANNER_TYPE,
    verbose: int = DEFAULT_VERBOSE_LEVEL,
) -> PlanSeeking:
    gh_token = os.environ.get("GITHUB_TOKEN", None)
    is_local, repo_path = check_local_or_remote(repo_path)
    repo_dir = clone_repo(repo_path, commit, clone_dir, gh_token, logger) if not is_local else repo_path
    repo_dir = os.path.join(os.getcwd(), repo_dir)

    if save_trajectories_path and not os.path.exists(save_trajectories_path):
        os.makedirs(save_trajectories_path)

    tools = []
    for tool_class in tool_classes:
        if issubclass(tool_class, SemanticCodeSearchTool):
            tools.append(tool_class(repo_dir, language=language, db_path=db_path))
        else:
            tools.append(tool_class(repo_dir, language=language))

    print("Tools initialized!")

    tool_strings = [f"{tool.name}: {tool.description}, args: {re.sub('}', '}}}}', re.sub('{', '{{{{', str(tool.args)))}" for tool in tools]
    formatted_tools = "\n".join(tool_strings)

    struct = subprocess.check_output(["tree", "-L","2", "-d", repo_dir]).decode("utf-8")

    # Set up the LLM
    if local_agent:
        llm = VLLM(
            model=DEFAULT_LOCAL_AGENT,
            trust_remote_code=True,
            max_new_tokens=1500,
            top_k=9,
            top_p=0.95,
            temperature=0.1,
            tensor_parallel_size=2  # for distributed inference
        )
    else:
        llm = ChatOpenAI(temperature=0, model="gpt-4-1106-preview", openai_api_key=openai_api_key)

    # Set up the planner agent
    planner_input = {
        "examples": examples,
        "formatted_tools": formatted_tools,
        "struct": struct,
    }
    llm_plan = ChatOpenAI(temperature=0, model="gpt-4-1106-preview", openai_api_key=openai_api_key)
    llm_analyzer = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-1106")
    planner = load_chat_planner(
        llm=llm_plan,
        type=planner_type,
        **planner_input
    )

    # Set up the vectorstore for analyzer's memory
    vectorstore = Chroma("langchain_store", OpenAIEmbeddings(disallowed_special=()))

    # Set up the executor and planner agent (the system)
    navigator = load_agent_navigator(
        llm,
        tools,
        navigator_prompt.PREFIX,
        navigator_prompt.SUFFIX,
        verbose=verbose,
        include_task_in_prompt=False,
        save_trajectories_path=save_trajectories_path
    )
    analyzer = load_agent_analyzer(
        llm_analyzer,
        analyzer_prompt.PREFIX,
        analyzer_prompt.SUFFIX,
        vectorstore,
        verbose=True
    )

    # seeking_algorithm = PlanSeeking
    seeking_algorithm = AdaptivePlanSeeking if planner_type == "adaptive" else PlanSeeking
    system = seeking_algorithm(
        planner=planner,
        navigator=navigator,
        analyzer=analyzer,
        vectorstore=vectorstore,
        verbose=DEFAULT_VERBOSE_LEVEL
    )
    return system

class RepoPilot:
    def __init__(
        self,
        repo_path,
        openai_api_key=None,
        commit=None,
        language="python",
        clone_dir="data/repos",
        examples=example_qa,
        save_trajectories_path=None,
    ):
        self.repo_path = repo_path
        self.openai_api_key = openai_api_key
        self.language = language
        openai_api_key = os.environ.get("OPENAI_API_KEY", None)
        if openai_api_key is None:
            raise ValueError("Please provide an OpenAI API key.")
        self.system = Setup(
            self.repo_path,
            commit,
            openai_api_key,
            language=language,
            clone_dir=clone_dir,
            examples=examples,
            save_trajectories_path=save_trajectories_path,
        )

    def query_codebase(self, query):
        result = self.system.run(query)
        return result