import subprocess
import os
import warnings
from typing import Optional
from autogen import UserProxyAgent
from repopilot.utils import clone_repo, check_local_or_remote, setup_logger
from repopilot.agents.plan_seeking import load_agent_navigator, load_agent_editor, load_agent_executor, load_summarizer, load_agent_planner, load_manager
from repopilot.prompts.navigator import system_nav
from repopilot.prompts.editor import system_edit
from repopilot.prompts.executor import system_exec
from repopilot.prompts.planner import system_plan
from repopilot.build import initialize_tools
from repopilot.constants import DEFAULT_VERBOSE_LEVEL, DEFAULT_LLM_CONFIGS, DEFAULT_TRAJECTORIES_PATH
        
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

logger = setup_logger()

def Setup(
    repo_path: str,
    commit: str,
    language: str = "python",
    clone_dir: str = "data/repos",
    save_trajectories_path: Optional[str] = DEFAULT_TRAJECTORIES_PATH,
    db_path: Optional[str] = None,  
    index_path: Optional[str] = "data/indexes",
    llm_configs: Optional[dict] = None,
):
    
    # initialize the github repository
    gh_token = os.environ.get("GITHUB_TOKEN", None)
    is_local, repo_path = check_local_or_remote(repo_path)
    repo_dir = clone_repo(repo_path, commit, clone_dir, gh_token, logger) if not is_local else repo_path
    repo_dir = os.path.join(os.getcwd(), repo_dir)

    if save_trajectories_path and not os.path.exists(save_trajectories_path):
        os.makedirs(save_trajectories_path)
        
    # Set up the tool kernel
    jupyter_executor = initialize_tools(repo_dir, db_path, index_path, language)
    logger.info("Initialized tools")    
    # Set up the navigator, executor and generator agent (the system)
    summarizer = load_summarizer()
    
    user_proxy = UserProxyAgent(
        name="Admin",
        system_message="A human admin. Interact with the planner to discuss the plan to resolve a codebase-related query.",
        human_input_mode="ALWAYS",
        code_execution_config=False,
        default_auto_reply="",
        max_consecutive_auto_reply=0
    )
    
    navigator = load_agent_navigator(
        llm_configs["nav"],
        jupyter_executor,
        system_nav,
        summarizer
    )
    
    editor = load_agent_editor(
        llm_configs["edit"],
        jupyter_executor,
        system_edit,
        summarizer
    )
    
    executor = load_agent_executor(
        llm_configs["exec"],
        jupyter_executor,
        system_exec,
        summarizer
    )
         
    planner = load_agent_planner(
        system_plan,
        llm_configs["plan"]
    )
    
    manager = load_manager(
        user_proxy=user_proxy,
        planner=planner,
        navigator=navigator,
        editor=editor,
        executor=executor,
        llm_config=llm_configs
    )
        
    return manager, user_proxy, repo_dir

class RepoPilot:
    def __init__(
        self,
        repo_path,
        commit="str",
        language="python",
        clone_dir="data/repos",
        save_trajectories_path=DEFAULT_TRAJECTORIES_PATH,
        llm_configs = DEFAULT_LLM_CONFIGS,
        verbose = DEFAULT_VERBOSE_LEVEL,
    ):
        self.repo_path = repo_path
        self.language = language
        self.system, self.user_proxy, repo_dir = Setup(
            self.repo_path,
            commit,
            language=language,
            clone_dir=clone_dir,
            save_trajectories_path=save_trajectories_path,
            llm_configs=llm_configs,
        )
        self.repo_dir = repo_dir

    def query_codebase(self, query):
        return self.user_proxy.initiate_chat(
            self.system, message=query
        )