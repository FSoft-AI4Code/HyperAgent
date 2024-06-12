import subprocess
import os
import warnings
from typing import Optional
from repopilot.utils import clone_repo, check_local_or_remote, setup_logger
from repopilot.agents.plan_seeking import load_agent_navigator, load_agent_generator, load_agent_executor, load_summarizer, load_agent_planner
from repopilot.prompts import navigator as navigator_prompt
from repopilot.prompts import generator as generator_prompt
from repopilot.prompts import executor as executor_prompt
from repopilot.prompts import planner as planner_prompt
from repopilot.build import setup_llms, initialize_tools, initialize_agents
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
    verbose: int = DEFAULT_VERBOSE_LEVEL,
):
    
    # initialize the github repository
    gh_token = os.environ.get("GITHUB_TOKEN", None)
    is_local, repo_path = check_local_or_remote(repo_path)
    repo_dir = clone_repo(repo_path, commit, clone_dir, gh_token, logger) if not is_local else repo_path
    repo_dir = os.path.join(os.getcwd(), repo_dir)

    if save_trajectories_path and not os.path.exists(save_trajectories_path):
        os.makedirs(save_trajectories_path)
        
    # Set up the tools
    nav_tools, gen_tools, exec_tools = initialize_tools(repo_dir, db_path, index_path, language)
    logger.info("Initialized tools")
    # Set up the LLM
    llm_nav, llm_gen, llm_exec, llm_plan = setup_llms(llm_configs)
    logger.info("Initialized LLMs")
    
    # Set up the navigator, executor and generator agent (the system)
    navigator = load_agent_navigator(
        llm_nav,
        nav_tools,
        navigator_prompt.PREFIX,
        navigator_prompt.SUFFIX,
        verbose=verbose,
        include_task_in_prompt=False,
    )
    
    generator = load_agent_generator(
        llm_gen,
        gen_tools,
        generator_prompt.PREFIX,
        generator_prompt.SUFFIX,
        verbose=verbose
    )
    
    executor = load_agent_executor(
        llm_exec,
        exec_tools,
        executor_prompt.PREFIX,
        executor_prompt.SUFFIX,
        verbose=verbose,
        commit_hash=commit
    )
    
    summarizer = load_summarizer()
    
    agents = initialize_agents(navigator, generator, executor, summarizer, repo_dir)
    agents = agents[:2]
        
    planner = load_agent_planner(
        llm_plan,
        agents,
        planner_prompt.PREFIX,
        planner_prompt.SUFFIX,
        verbose=verbose
    )
    
    struct = subprocess.check_output(["tree", "-L","2", "-d", repo_dir]).decode("utf-8")
    planner_input = {
        "struct": struct,
    }
    
    return planner, repo_dir, planner_input

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
        self.system, repo_dir, self.planner_input = Setup(
            self.repo_path,
            commit,
            language=language,
            clone_dir=clone_dir,
            save_trajectories_path=save_trajectories_path,
            llm_configs=llm_configs,
            verbose=verbose
        )
        self.repo_dir = repo_dir

    def query_codebase(self, query):
        self.planner_input["current_step"] = query
        result = self.system.step(self.planner_input)
        return result[0].response