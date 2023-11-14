import sys
sys.path.append("/datadrive05/huypn16/focalcoder/")
from datasets import load_dataset
from pathlib import Path
from SWE_bench.inference.make_datasets.bm25_retrieval import clone_repo, ContextManager
from git import Repo
import os
import logging
import subprocess
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.text_splitter import Language
from langchain.document_loaders.generic import GenericLoader
from langchain.document_loaders.parsers import LanguageParser
from langchain.agents.react.base import DocstoreExplorer
from langchain.docstore.in_memory import InMemoryDocstore
from langchain.agents import AgentType, initialize_agent, Tool
from langchain.chat_models import ChatOpenAI
from tools import GoToDefinitionTool, CodeSearchTool, search_preliminary_inside_project, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool
from utils import clone_repo
from langchain_experimental.plan_and_execute import (
    load_chat_planner,
)
from agents import load_agent_executor, PlanSeeking
from langchain.callbacks import get_openai_callback

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger('pylsp').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def Setup(repo, commit):
    root_dir = "data/repos"
    gh_token = os.environ.get("GITHUB_TOKEN", None)
    repo_dir = clone_repo(repo, commit, root_dir, gh_token, logger)

    python_splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.PYTHON, chunk_size=1000, chunk_overlap=200
    )

    loader = GenericLoader.from_filesystem(
        repo_dir,
        glob="**/*",
        suffixes=[".py"],
        parser=LanguageParser(language=Language.PYTHON, parser_threshold=500),
    )
    
    documents = loader.load()
    texts = python_splitter.split_documents(documents)
    texts = {id: text for id, text in enumerate(texts)}
    docstore = InMemoryDocstore()
    docstore.add(texts)
    docstore = DocstoreExplorer(docstore)
    
    struct = open("struct.txt", "r").read()
    suffix = "Begin! Reminder to ALWAYS respond with a valid json blob of a single action. Use tools if necessary. Respond directly if you have gathered enough information from the repository. Format is Action:```$JSON_BLOB```then Observation:."
    prefix = "You are an expert in programming, you're so good at code navigation inside large repository. Try to combine different tools to navigate inside the project. Some good combinations of tools could be tree explore files -> find symbols of the files. Semantic search -> exact code search -> go to definition and etc. If you know exactly the name of the symbol, you can use CodeSearchTool or if you know the line and the name of the symbol, you can use GoToDefinition tool. Respond to the human as helpfully and accurately as possible. Consider use other tools if the results returned is not cleared enough or failed for the query. You have access to the following tools:"
    planner_prompt = (
        "Given following general information about the repository such as repository structure"
        f"{struct}"
        "Let's first understand the problem and devise a plan to solve the problem."
        " Please output the plan starting with the header 'Plan:' "
        "and then followed by a numbered list of steps. "
        "Important! Please make the plan with the minimum number of steps required, do not include a loop of steps."
        "to accurately complete the task. The steps should be detail enough,  the path of folder should be a relative path and correct"
        "If the task is a question, the final step should almost always be 'Given the above steps taken, please respond to the users original question'. "
        "At the end of your plan, say '<END_OF_PLAN>'"
        "Example:\n"
        "Question: how to subclass and define a custom spherical coordinate frame?\n"
        "Plan:\n"
        "1. Finding related functions and classes related to spherical coordinate frame, possibly in some folders in the project\n"
        "2. Find the key class of the spherical coordinate frame.\n"
        "3. Find the parent (base) class\n"
        "4. Find its usage in the code\n and use it as a template to define a custom spherical coordinate frame\n"
        "5. Given the above steps taken, please respond to the users original question.\n"
        "<END_OF_PLAN>\n"
    )
    
    ## Set up the LLM and tools
    repo_dir = os.path.join("/datadrive05/huypn16/focalcoder", repo_dir)
    llm = ChatOpenAI(temperature=0, model="gpt-4-1106-preview", openai_api_key="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")
    tools = [CodeSearchTool(repo_dir), GoToDefinitionTool(repo_dir), FindAllReferencesTool(repo_dir), Tool(
            name="Semantic Code Search",
            func=docstore.search,
            description="useful for when the query is a sentance, semantic and vague. If exact search such as code search failed after multiple tries, try this",
        ), GetAllSymbolsTool(repo_dir), GetTreeStructureTool(repo_dir)]
    
    ## Set up the planner agent 
    llm_plan = ChatOpenAI(temperature=0, model="gpt-4", openai_api_key="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")
    planner = load_chat_planner(llm_plan, system_prompt=planner_prompt)
    
    ## Set up the executor and planner agent (the system)
    executor = load_agent_executor(llm, tools, suffix, prefix, verbose=True)
    agent = PlanSeeking(planner=planner, executor=executor, verbose=True)
    
    return agent

if __name__ == "__main__":
    logger.info("Start!")
    repo = input("Enter your repo name here: ")
    commit = input("Enter your commit hash here: ")
    agent = Setup(repo, commit)
    
    logger.info("Setup done!")
    question = input("Enter your question about your repository: ")
    with get_openai_callback() as cb:
        agent.run(question)
        print(f"Total Tokens: {cb.total_tokens}")
        print(f"Prompt Tokens: {cb.prompt_tokens}")
        print(f"Completion Tokens: {cb.completion_tokens}")
        print(f"Total Cost (USD): ${cb.total_cost}")