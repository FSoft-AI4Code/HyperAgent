import subprocess
import os
import logging
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from repopilot.tools import GoToDefinitionTool, CodeSearchTool, SemanticCodeSearchTool, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool, OpenFileTool
from repopilot.utils import clone_repo
from langchain_experimental.plan_and_execute import load_chat_planner
from repopilot.agents.plan_seeking import load_agent_navigator, load_agent_analyzer, PlanSeeking
from repopilot.prompts.general_qa import example_qa
from repopilot.prompts import analyzer as analyzer_prompt
from repopilot.prompts import planner as planner_prompt
from repopilot.prompts import navigator as navigator_prompt
from langchain.llms import VLLM
import re

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

from langchain.llms.base import LLM
from typing import Optional, List, Mapping, Any

def Setup(
    repo: str,
    commit: str,
    openai_api_key: str,
    local: bool = True,
    language: str = "python",
    clone_dir: str = "data/repos",
    examples: List[Mapping[str, Any]] = example_qa,
    save_trajectories_path: Optional[str] = None,
    headers: Optional[Mapping[str, Any]] = None,
    local_agent: bool = False
) -> PlanSeeking:
    
    gh_token = os.environ.get("GITHUB_TOKEN", None)
    repo_dir = clone_repo(repo, commit, clone_dir, gh_token, logger) if not local else repo
    repo_dir = os.path.join(os.getcwd(), repo_dir)

    if save_trajectories_path and not os.path.exists(save_trajectories_path):
        os.makedirs(save_trajectories_path)

    tools = []
    tool_classes = [CodeSearchTool, SemanticCodeSearchTool, GoToDefinitionTool, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool, OpenFileTool]

    for tool_class in tool_classes:
        tools.append(tool_class(repo_dir, language=language))

    print("Tools initialized!")
            
    tool_strings = [f"{tool.name}: {tool.description}, args: {re.sub('}', '}}}}', re.sub('{', '{{{{', str(tool.args)))}" for tool in tools]
    formatted_tools = "\n".join(tool_strings)

    struct = subprocess.check_output(["tree", "-L","2", "-d", repo_dir]).decode("utf-8")

    ## Set up the LLM
    if local_agent:
        llm = VLLM(model="model/mistral_repopilot/full_model",
            trust_remote_code=True,  
            max_new_tokens=1500,
            top_k=9,
            top_p=0.95,
            temperature=0.1,
            tensor_parallel_size=2 # for distributed inference
        )
    else:
        llm = ChatOpenAI(temperature=0, model="gpt-4-1106-preview", openai_api_key=openai_api_key)

    ## Set up the planner agent 
    llm_plan = ChatOpenAI(temperature=0, model="gpt-4", openai_api_key=openai_api_key)
    llm_analyzer = ChatOpenAI(temperature=0, model="gpt-4-1106-preview")
    planner = load_chat_planner(llm_plan, system_prompt=planner_prompt.PLANNER_TEMPLATE.format(struct=struct, formatted_tools=formatted_tools, examples=examples))
    
    ## Set up the vectorstore for analyzer's memory
    vectorstore = Chroma("langchain_store", OpenAIEmbeddings())  
    ## Set up the executor and planner agent (the system)
    navigator = load_agent_navigator(llm, 
        tools, 
        navigator_prompt.PREFIX, 
        navigator_prompt.SUFFIX, 
        verbose=True, 
        include_task_in_prompt=True, 
        save_trajectories_path=save_trajectories_path
    )
    analyzer = load_agent_analyzer(llm_analyzer, 
        analyzer_prompt.PREFIX, 
        analyzer_prompt.SUFFIX, 
        vectorstore, 
        verbose=True
    )
    system = PlanSeeking(planner=planner, 
        navigator=navigator, 
        analyzer=analyzer, 
        vectorstore=vectorstore, 
        verbose=True
    )
    
    return system

class RepoPilot:
    def __init__(self, local_path, openai_api_key=None, local=True, commit=None, language="python", clone_dir="data/repos", examples=example_qa, save_trajectories_path=None, headers=None):
        self.local_path = local_path
        self.openai_api_key = openai_api_key
        self.language = language
        openai_api_key = os.environ.get("OPENAI_API_KEY", None)
        if openai_api_key is None:
            raise ValueError("Please provide an OpenAI API key.")
        self.system = Setup(self.local_path, commit, openai_api_key, local=local, language=language, clone_dir=clone_dir, examples=examples, save_trajectories_path=save_trajectories_path, headers=headers)
    
    def query_codebase(self, query):
        result = self.system.run(query)
        return result