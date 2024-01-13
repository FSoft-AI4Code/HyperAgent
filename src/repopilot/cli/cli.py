from typer import Typer, Argument, Option
from typing import Optional
from typing_extensions import Annotated
import subprocess
from appdirs import user_config_dir
import logging
import os
import threading
from pathlib import Path
from repopilot.cli.console import Console
from langchain_community.llms.vllm import VLLMOpenAI
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from repopilot.prompts import analyzer as analyzer_prompt
from repopilot.prompts import navigator as navigator_prompt
from repopilot.agents.plan_seeking import load_agent_navigator, load_agent_analyzer, PlanSeeking
from repopilot.agents.adaptive_plan_seeking import AdaptivePlanSeeking
from repopilot.agents.planner import load_chat_planner
from repopilot.utils import clone_repo, check_local_or_remote
from repopilot.tools import tool_classes, SemanticCodeSearchTool, CodeSearchTool
from repopilot.prompts.general_qa import example_qa
from repopilot.constants import DEFAULT_CLONE_DIR, SEMANTIC_CODE_SEARCH_DB_PATH, DEFAULT_DEVICES, DEFAULT_LOCAL_AGENT, DEFAULT_GH_TOKEN, DEFAULT_WORKDIR_CLI, ZOEKT_CODE_SEARCH_INDEX_PATH, DEFAULT_PLANNER_TYPE, DEFAULT_VLLM_PORT, DEFAULT_LANGUAGE
from repopilot.utils import save_infos_to_folder
import re
import json

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("chromadb").setLevel(logging.CRITICAL)
logging.getLogger('multilspy').setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)

app = Typer(add_completion=False)
setup_app = Typer()
query_app = Typer()
list_app = Typer()
config_app = Typer(add_completion=False, no_args_is_help=True)
config_dir = Path(user_config_dir("repopilot"))
console = Console(history_dir=config_dir / "history")

def read_key(console: Console):
    openai_api_key = os.environ.get("OPENAI_API_KEY", None)
    if openai_api_key is None:
        console.info("Please provide an OpenAI API key.")
        openai_api_key = console.prompt(
            "Please key in a valid OpenAI Key: ",
            is_password=True,
        )
    return openai_api_key

@setup_app.callback(invoke_without_command=True)
def setup(
    repo_path: Annotated[str, Argument(..., help="The path to the repository to set up.")],
    repository_name: Annotated[str, Option("--repository-name", help="The name of the repository.", prompt=True)],
    language: Annotated[Optional[str], Option(help="The programming language of the repository.", prompt=True)],
    commit: Annotated[str, Option("--commit", help="The commit to set up.")] = "", 
    local_agent: Annotated[Optional[str], Option("--local-agent", help="local agent path")]=DEFAULT_LOCAL_AGENT,
    devices: Annotated[Optional[str], Option("--devices", help="devices to use for inference")]=DEFAULT_DEVICES,
    clone_dir: Annotated[Optional[str], Option("--clone-dir", help="The directory to clone the repository to.")]=DEFAULT_CLONE_DIR,
    gh_token: Annotated[Optional[str], Option("--gh-token", help="The GitHub token to use for cloning private repositories.")]=DEFAULT_GH_TOKEN,
):  
    console.info("Setting up repo...")
    is_local, repo_path = check_local_or_remote(repo_path)
    repo_dir = clone_repo(repo_path, commit, clone_dir, gh_token, logger) if not is_local else repo_path
    repo_dir = os.path.join(os.getcwd(), repo_dir)
    console.info("Setting up LLM...")
    if local_agent != "None":
        def run_cmd():
            with open(os.devnull, 'w') as devnull:
                env = os.environ.copy()
                env["CUDA_VISIBLE_DEVICES"] = devices
                subprocess.run(["python", "-m", 
                                "vllm.entrypoints.openai.api_server", 
                                "--model", str(DEFAULT_LOCAL_AGENT), 
                                "--trust-remote-code", 
                                "--tensor-parallel-size", str(len(devices.split(","))), 
                                "--port", str(DEFAULT_VLLM_PORT)],
                            stdout=devnull, stderr=devnull, env=env)
        thread = threading.Thread(target=run_cmd)
        thread.daemon = True
        thread.start()

    console.info("Setting up tools...")
    tools = []
    for tool_class in tool_classes:
        if tool_class == SemanticCodeSearchTool:
            tools.append(tool_class(repo_dir, language=language, db_path=SEMANTIC_CODE_SEARCH_DB_PATH+repository_name, build=True))
        elif tool_class == CodeSearchTool:
            tools.append(tool_class(repo_dir, language=language, index_path=ZOEKT_CODE_SEARCH_INDEX_PATH+repository_name, build=True))

    necessary_infos = {
        "repo_dir": repo_dir,
        "local_agent": local_agent,
        "language": language,
    }
    save_infos_to_folder(necessary_infos, repository_name, DEFAULT_WORKDIR_CLI)
    console.info("Your repository is indexed!")

@list_app.callback(invoke_without_command=True)
def list():
    console.info("Listing repos...")
    for file in os.listdir(DEFAULT_WORKDIR_CLI):
        if file.endswith(".json"):
            console.info2(file[:-5])

@query_app.callback(invoke_without_command=True)
def query(
    repository_name: Annotated[str, Argument(..., help="The name of the repository to query.")],
    planner_type: Annotated[str, Option("--planner-type", help="The type of planner to use.")]=DEFAULT_PLANNER_TYPE,
    save_trajectories_path: Annotated[Optional[str], Option("--save-trajectories-path", help="The path to save the trajectories to.")]=None,
    type_agent: Annotated[Optional[str], Option("--type-agent", help="The type of agent to use.")]="gpt-4",
    verbose: Annotated[Optional[int], Option("--verbose", help="Verbose level")]=1,
):  
    tools = []
    openai_api_key = read_key(console)
    console.info("querying repo...")
    with open(os.path.join(DEFAULT_WORKDIR_CLI, repository_name+".json")) as f:
        necessary_infos = json.load(f)
    
    for tool_class in tool_classes:
        if tool_class == SemanticCodeSearchTool:
            tools.append(tool_class(necessary_infos["repo_dir"], language=necessary_infos["language"], db_path=SEMANTIC_CODE_SEARCH_DB_PATH+repository_name, build=False))
        elif tool_class == CodeSearchTool:
            tools.append(tool_class(necessary_infos["repo_dir"], language=necessary_infos["language"], index_path=ZOEKT_CODE_SEARCH_INDEX_PATH+repository_name, build=False))
        else:
            tools.append(tool_class(necessary_infos["repo_dir"], language=necessary_infos["language"]))
    
    tool_strings = [f"{tool.name}: {tool.description}, args: {re.sub('}', '}}}}', re.sub('{', '{{{{', str(tool.args)))}" for tool in tools]
    formatted_tools = "\n".join(tool_strings)

    struct = subprocess.check_output(["tree", "-L","2", "-d", necessary_infos["repo_dir"]]).decode("utf-8")
    if type_agent == "local":
        llm = VLLMOpenAI(
            openai_api_key="EMPTY",
            openai_api_base=f"http://localhost:{DEFAULT_VLLM_PORT}/v1",
            model_name=necessary_infos["local_agent"],
            max_tokens=3000,
            top_p=0.95,
            temperature=0.1,
        )
    else:
        llm = ChatOpenAI(temperature=0, model="gpt-4-1106-preview", openai_api_key=openai_api_key)
        
    planner_input = {
        "examples": example_qa,
        "formatted_tools": formatted_tools,
        "struct": struct,
    }
    llm_plan = ChatOpenAI(temperature=0, model="gpt-4", openai_api_key=openai_api_key)
    llm_analyzer = ChatOpenAI(temperature=0, model="gpt-4-1106-preview")
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
        verbose=verbose
    )
    while True:
        query = console.prompt("Your query: ")
        if query == "exit":
            break
        console.gap()
        response = system(query)
        response = response["output"].response
        console.info(response)
    
app.add_typer(setup_app, name="setup")
app.add_typer(query_app, name="query")
app.add_typer(list_app, name="list")