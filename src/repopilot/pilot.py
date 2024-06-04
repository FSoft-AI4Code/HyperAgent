import subprocess
import os
import warnings
from typing import Optional
from repopilot.utils import clone_repo, check_local_or_remote, setup_logger
from repopilot.agents.planner import load_chat_planner
from repopilot.agents.plan_seeking import load_agent_navigator, PlanSeeking, load_agent_generator, load_agent_executor, load_summarizer
from repopilot.prompts import navigator as navigator_prompt
from repopilot.prompts import generator as generator_prompt
from repopilot.prompts import executor as executor_prompt
from repopilot.build import setup_llms, initialize_tools
from repopilot.constants import DEFAULT_VERBOSE_LEVEL, DEFAULT_LLM_CONFIGS
        
warnings.filterwarnings("ignore", category=DeprecationWarning)
logger = setup_logger()

def Setup(
    repo_path: str,
    commit: str,
    language: str = "python",
    clone_dir: str = "data/repos",
    save_trajectories_path: Optional[str] = None,
    db_path: Optional[str] = None,  
    index_path: Optional[str] = "data/indexes",
    llm_configs: Optional[dict] = None,
    verbose: int = DEFAULT_VERBOSE_LEVEL,
) -> PlanSeeking:
    
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
        save_trajectories_path=save_trajectories_path
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
        verbose=verbose
    )
    
    summarizer = load_summarizer()
    
    agent_strings = [f"{agent.name}: {agent.description}" for agent in [navigator, generator, executor]]
    formatted_agents = "\n".join(agent_strings)
    struct = subprocess.check_output(["tree", "-L","2", "-d", repo_dir]).decode("utf-8")
    planner_input = {
        # "examples": examples,
        "formatted_agents": formatted_agents,
        "struct": struct,
    }
    planner = load_chat_planner(
        llm=llm_plan,
        **planner_input
    )

    system = PlanSeeking(
        planner=planner,
        navigator=navigator,
        executor=executor,
        generator=generator,
        summarizer=summarizer,
        repo_dir=repo_dir,
        verbose=DEFAULT_VERBOSE_LEVEL
    )
    return system

class RepoPilot:
    def __init__(
        self,
        repo_path,
        commit=None,
        language="python",
        clone_dir="data/repos",
        save_trajectories_path=None,
        llm_configs = DEFAULT_LLM_CONFIGS,
        verbose = DEFAULT_VERBOSE_LEVEL,
    ):
        self.repo_path = repo_path
        self.language = language
        self.system = Setup(
            self.repo_path,
            commit,
            language=language,
            clone_dir=clone_dir,
            save_trajectories_path=save_trajectories_path,
            llm_configs=llm_configs,
            verbose=verbose
        )

    def query_codebase(self, query):
        result = self.system.run(query)
        return result