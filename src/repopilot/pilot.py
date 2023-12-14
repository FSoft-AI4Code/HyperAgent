import subprocess
import os
import logging
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from repopilot.tools import GoToDefinitionTool, CodeSearchTool, SemanticCodeSearchTool, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool, OpenFileTool
from repopilot.utils import clone_repo
from langchain_experimental.plan_and_execute import load_chat_planner
from repopilot.agents.plan_seeking import load_agent_executor, load_agent_analyzer, PlanSeeking
from repopilot.prompts.general_qa import example_qa
from langchain.llms import VLLM
from langchain_google_genai import ChatGoogleGenerativeAI
import re

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger('pylsp').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def Setup(repo, commit, openai_api_key, local=True, language="python", clone_dir="data/repos", examples=example_qa, save_trajectories_path=None):
    gh_token = os.environ.get("GITHUB_TOKEN", None)
    repo_dir = repo if local else clone_repo(repo, commit, clone_dir, gh_token, logger) 
    ## Repo dir
    repo_dir = os.path.join(os.getcwd(), repo_dir)
    if save_trajectories_path and not os.path.exists(save_trajectories_path):
        os.makedirs(save_trajectories_path)
    ## Setup tools and tool string 
    tools = []
    unitialized_tools = [CodeSearchTool, SemanticCodeSearchTool, GoToDefinitionTool, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool, OpenFileTool]
    
    ## Initialize tools
    for tool in unitialized_tools:
        tools.append(tool(repo_dir, language=language))
    
    print("Tools initialized!")
            
    tool_strings = []
    for tool in tools:
        args_schema = re.sub("}", "}}}}", re.sub("{", "{{{{", str(tool.args)))
        tool_strings.append(f"{tool.name}: {tool.description}, args: {args_schema}")
    formatted_tools = "\n".join(tool_strings)
    
    ## Get the repo structure
    struct = subprocess.check_output(["tree", "-L", "2", "-d", repo_dir]).decode("utf-8")
    suffix = "Begin! Reminder to ALWAYS respond with a valid json blob of a single action. Use tools if necessary. Respond directly if you have gathered enough information from the repository. Format is Action:```$JSON_BLOB```then Observation:."
    prefix = "You are an expert in programming, you're so good at code navigation inside large repository. Try to combine different tools to seek related information to the query inside the project. Some good combinations of tools could be get_folder_structure -> find symbols of each file inside the directory. Semantic search -> exact code search -> go to definition and etc. If you know exactly the name of the symbol, you can use code_search tool or if you know the line and the name of the symbol, you can use go_to_definition tool. Try to avoid using open_file tool frequently (use the get all symbols instead). Respond to the human as helpfully and accurately as possible. Consider use other tools if the results returned is not cleared enough or failed for the query. You have access to the following tools:"
    planner_prompt = f"""
        Given following general information about the repository such as repository structure
        {struct}
        and given following tools:
        "{formatted_tools}
        Let's first understand the query and devise a plan to seek the useful information from the repository to answer the query.
        Please output the plan starting with the header 'Plan:' and then followed by a numbered list of steps. "
        <Important!>Please make the plan the minimum number of steps required (no more than 4 steps), nomarlly 2-3 steps are enough. The step should hint which set of tools to be used to accurately complete the task. If the information in the query is uncleared, consider use get tree structure to get overview folder structure then exlpore.
        At the end of your plan, say '<END_OF_PLAN>'. If the question only cares about some specific, simple information, you can generate 2 steps plan, the first step is to find the information using semantic code search 
        and the second step is to respond to the question."
        "Example:\n"
        {examples}
    """
    
    suffix_analyzer = "Begin! Reminder to ALWAYS respond with a valid json blob of a single action. Use tools if necessary. Respond directly if you have gathered enough information from the repository. Format is Action:```$JSON_BLOB```then Observation:."
    prefix_analyzer = "You are an expert in responding the user's question with useful information and necessary code snippet. You will be provided with gathered information from the repository and the query. You can use the information to respond to the query. If you need more information, you can use the search tool to gather more detailed information about the object that is mentioned in the notes. Respond to the human as helpfully and detailed as much as possible. Please consider detail information from the current notes. You have access to following semantic search tool:"
    
    ## Set up the LLM 
    llm = ChatOpenAI(temperature=0, model="gpt-4-1106-preview", openai_api_key=openai_api_key)
    # llm = VLLM(model="deepseek-ai/deepseek-llm-67b-chat",
    #        trust_remote_code=True,  # mandatory for hf models
    #        max_new_tokens=1500,
    #        top_k=15,
    #        top_p=0.95,
    #        temperature=0.2,
    #        tensor_parallel_size=2 # for distributed inference
    # )
    # llm = ChatGoogleGenerativeAI(model="gemini-pro")

    ## Set up the planner agent 
    llm_plan = ChatOpenAI(temperature=0, model="gpt-4", openai_api_key=openai_api_key)
    
    llm_analyzer = ChatOpenAI(temperature=0, model="gpt-4-1106-preview")
    planner = load_chat_planner(llm_plan, system_prompt=planner_prompt)
    
    ## 
    vectorstore = Chroma("langchain_store", OpenAIEmbeddings())
    
    ## Set up the executor and planner agent (the system)
    executor = load_agent_executor(llm, tools, prefix, suffix, verbose=True, include_task_in_prompt=True, save_trajectories_path=save_trajectories_path)
    analyzer = load_agent_analyzer(llm_analyzer, prefix_analyzer, suffix_analyzer, vectorstore, verbose=True)
    system = PlanSeeking(planner=planner, executor=executor, analyzer=analyzer, vectorstore=vectorstore, verbose=True)
    
    return system

class RepoPilot:
    def __init__(self, local_path, openai_api_key=None, local=True, commit=None, language="python", clone_dir="data/repos", examples=example_qa, save_trajectories_path=None):
        self.local_path = local_path
        self.openai_api_key = openai_api_key
        self.language = language
        openai_api_key = os.environ.get("OPENAI_API_KEY", None)
        if openai_api_key is None:
            raise ValueError("Please provide an OpenAI API key.")
        self.system = Setup(self.local_path, commit, openai_api_key, local=local, language=language, clone_dir=clone_dir, examples=examples, save_trajectories_path=save_trajectories_path)
    
    def query_codebase(self, query):
        result = self.system.run(query)
        return result