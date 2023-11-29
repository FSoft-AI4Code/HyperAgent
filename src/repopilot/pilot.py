import subprocess
import os
import logging
from langchain.chat_models import ChatOpenAI
from repopilot.tools import GoToDefinitionTool, CodeSearchTool, SemanticCodeSearchTool, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool, OpenFileTool
from repopilot.utils import clone_repo
from langchain_experimental.plan_and_execute import (
    load_chat_planner,
)
from repopilot.agents.plan_seeking import load_agent_executor, PlanSeeking
import re

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger('pylsp').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def Setup(repo, commit, openai_api_key, local=True, language="python", clone_dir="data/repos"):
    gh_token = os.environ.get("GITHUB_TOKEN", None)
    repo_dir = repo if local else clone_repo(repo, commit, clone_dir, gh_token, logger) 
    ## Repo dir
    repo_dir = os.path.join(os.getcwd(), repo_dir)
    
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
    prefix = "You are an expert in programming, you're so good at code navigation inside large repository. Try to combine different tools to seek related information to the query inside the project. Some good combinations of tools could be tree explore files -> find symbols of each file inside the directory. Semantic search -> exact code search -> go to definition and etc. If you know exactly the name of the symbol, you can use CodeSearchTool or if you know the line and the name of the symbol, you can use GoToDefinition tool. Try to avoid using open file tool frequently (use the get all symbols instead). Respond to the human as helpfully and accurately as possible. Consider use other tools if the results returned is not cleared enough or failed for the query. You have access to the following tools:"
    planner_prompt = (
        "Given following general information about the repository such as repository structure"
        f"{struct}\n"
        "and given following tools:\n"
        f"{formatted_tools}\n"
        "Let's first understand the query and devise a plan to seek the useful information from the repository to answer the query."
        " Please output the plan starting with the header 'Plan:' "
        "and then followed by a numbered list of steps. "
        "<Important!>Please make the plan the minimum number of steps required (no more than 4 steps), nomarlly 2-3 steps are enough. The step should hint which tools to be used"
        "to accurately complete the task. If the task is a question, "
        "the final step should almost always be 'Given the above steps taken, "
        "please respond to the users original question'. "
        "At the end of your plan, say '<END_OF_PLAN>'"
        "If the question only cares about some specific, simple information, you can generate 2 steps plan, the first step is to find the information using semantic code search and the second step is to respond to the question."
        "Example:\n"
        "Question: how to subclass and define a custom spherical coordinate frame?\n"
        "Plan:\n"
        "1. Finding related functions and classes related to spherical coordinate frame, possibly in some folders or files in the project, likely to be in astropy/coordinate/spherical.py \n"
        "2. Find its usage in the codebase and use it as a template to define a custom spherical coordinate frame with possible custom methods or fields\n"
        "3. Given the above steps taken, please respond to the users original question.\n"
        "<END_OF_PLAN>\n"
        "Example 2:\n"
        "Question: how to use Kernel1D class\n"
        "Plan:\n"
        "1. Find the Kernel1D class in the codebase, use code search tool or explore directory and find that class among possible symbols.\n"
        "2. When found, find its usage in the code and use it as a template to use the class. You can find the reference of the class in test cases using find_all_references tool\n"
        "3. Given the above steps taken, please respond to the users original question.\n"
        "<END_OF_PLAN>\n"
        "Example 3:\n"
        "Question: What are the main components of the backend of danswer and how it works, be specific (roles of main classes and functions for each component). Describe the high level flow of the backend as well.\n"
        "Plan:\n"
        "1. Identify where is backend components inside the repository. Then identify the main classes and functions. This could be done by looking at the files in each directory and understanding their purpose."
        "2. Understand the role of each main class and functions. This could be done by reading the code and any associated documentation or comments."
        "3. Choose the main classes and functions that relevant then find their usage crossover to find the high level flow of the backend. This can be used with go-to-definition and find_all_references\n"
        "4. Given the above steps taken, please respond to the users original question.\n"
        "<END_OF_PLAN>\n"
        "Example 4:\n"
        "Question: what is the purpose of the MPC.get_observations function?\n"
        "Plan:\n"
        "1. Find the MPC.get_observations function using Code Search tool, if the results are too vauge, consider using Semantic Code Search tool\n If the results are not cleared enough, you can navigate the directory using the tree structure tool to find the related files (possibly astroquery/mpc) then use get all symbols tool to find the function"
        "2. Given the above steps taken, please respond to the users original question.\n"
        "<END_OF_PLAN>\n"
        "Example 5:\n"
        "Question: what does UnigramVisitor do in the textanalysis repo?\n"
        "Plan:\n"
        "1. Find the UnigramVisitor class using Code Search tool, if the results are too vauge, consider using Semantic Code Search tool\n If the results are not cleared enough, you can navigate the directory using the tree structure tool to find the related files (possibly textanalysis/visitor) then use get all symbols tool to find the class"
        "2. Given the above steps taken, please respond to the users original question.\n"
        "<END_OF_PLAN>\n"
    )
    
    ## Set up the LLM 
    llm = ChatOpenAI(temperature=0, model="gpt-4-1106-preview", openai_api_key=openai_api_key)

    ## Set up the planner agent 
    llm_plan = ChatOpenAI(temperature=0, model="gpt-4", openai_api_key=openai_api_key)
    planner = load_chat_planner(llm_plan, system_prompt=planner_prompt)
    
    ## Set up the executor and planner agent (the system)
    executor = load_agent_executor(llm, tools, suffix, prefix, verbose=True, include_task_in_prompt=True)
    system = PlanSeeking(planner=planner, executor=executor, verbose=True)
    
    return system

class RepoPilot:
    def __init__(self, local_path, openai_api_key=None, local=True, commit=None, language="python", clone_dir="data/repos"):
        self.local_path = local_path
        self.openai_api_key = openai_api_key
        self.language = language
        openai_api_key = os.environ.get("OPENAI_API_KEY", None)
        if openai_api_key is None:
            raise ValueError("Please provide an OpenAI API key.")
        self.system = Setup(self.local_path, commit, openai_api_key, local=local, language=language, clone_dir=clone_dir)
    
    def query_codebase(self, query):
        result = self.system.run(query)
        return result