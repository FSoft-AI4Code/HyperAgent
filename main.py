import sys
sys.path.append("/datadrive05/huypn16/focalcoder/")
from SWE_bench.inference.make_datasets.bm25_retrieval import clone_repo, ContextManager
import os
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.text_splitter import Language
from langchain.document_loaders.generic import GenericLoader
from langchain.document_loaders.parsers import LanguageParser
from langchain.agents import Tool
from langchain.chat_models import ChatOpenAI
from tools import GoToDefinitionTool, CodeSearchTool, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool, OpenFileTool
from utils import clone_repo
from langchain_experimental.plan_and_execute import (
    load_chat_planner,
)
from agents import load_agent_executor, PlanSeeking
from langchain.callbacks import get_openai_callback
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
import re

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
        suffixes=[".py"],
        parser=LanguageParser(language=Language.PYTHON, parser_threshold=500),
    )
    
    documents = loader.load()
    texts = python_splitter.split_documents(documents)
    db = Chroma.from_documents(texts, OpenAIEmbeddings())
    
    def semantic_code_search(query):
        retrieved_docs = db.similarity_search(query, k=3)
        return [doc.page_content for doc in retrieved_docs]
    
    ## Repo dir
    repo_dir = os.path.join("/datadrive05/huypn16/focalcoder", repo_dir)
    
    ## Setup tools and tool string 
    tools = [CodeSearchTool(repo_dir), GoToDefinitionTool(repo_dir), FindAllReferencesTool(repo_dir), Tool(
            name="Semantic Code Search",
            func=semantic_code_search,
            description="useful for when the query is a sentance, semantic and vague. If exact search such as code search failed after multiple tries, try this",
        ), GetAllSymbolsTool(repo_dir), GetTreeStructureTool(repo_dir), OpenFileTool(repo_dir)]
    
    tool_strings = []
    for tool in tools:
        args_schema = re.sub("}", "}}}}", re.sub("{", "{{{{", str(tool.args)))
        tool_strings.append(f"{tool.name}: {tool.description}, args: {args_schema}")
    formatted_tools = "\n".join(tool_strings)
    
    struct = open("struct.txt", "r").read()
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
        "2. Find the usage of the function using find_all_references tool\n or find in the test cases or documentation" 
        "3. Given the above steps taken, please respond to the users original question.\n"
        "<END_OF_PLAN>\n"
    )
    
    ## Set up the LLM 
    llm = ChatOpenAI(temperature=0, model="gpt-4-1106-preview", openai_api_key="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")

    ## Set up the planner agent 
    llm_plan = ChatOpenAI(temperature=0, model="gpt-4", openai_api_key="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")
    planner = load_chat_planner(llm_plan, system_prompt=planner_prompt)
    
    ## Set up the executor and planner agent (the system)
    executor = load_agent_executor(llm, tools, suffix, prefix, verbose=True, include_task_in_prompt=True)
    agent = PlanSeeking(planner=planner, executor=executor, verbose=True)
    
    return agent

if __name__ == "__main__":
    logger.info("Start!")
    # repo = input("Enter your repo name here: ")
    # commit = input("Enter your commit hash here: ")
    repo = "langchain-ai/langchain"
    commit = ""
    agent = Setup(repo, commit)
    
    logger.info("Setup done!")
    # question = input("Enter your question about your repository: ")
    # question = "what are the main components of the backend of danswer and how it works, be very specific (roles of the main classes for each component and their relationship)"
    question = """
    How to add memory to SQLDatabaseChain? 
    I want to create a chain to make query against my database. Also I want to add memory to this chain.
    Example of dialogue I want to see:

    Query: Who is an owner of website with domain domain.com?
    Answer: Boba Bobovich
    Query: Tell me his email Answer:
    Boba Bobovich's email is boba@boba.com

    I have this code:

    import os
    from langchain import OpenAI, SQLDatabase, SQLDatabaseChain, PromptTemplate
    from langchain.memory import ConversationBufferMemory

    memory = ConversationBufferMemory()
    db = SQLDatabase.from_uri(os.getenv("DB_URI"))
    llm = OpenAI(temperature=0, verbose=True)
    db_chain = SQLDatabaseChain.from_llm(llm, db, verbose=True, memory=memory)

    db_chain.run("Who is owner of the website with domain https://damon.name")
    db_chain.run("Tell me his email")
    print(memory.load_memory_variables({}))

    It gives:

    > Entering new  chain...
    Who is owner of the website with domain https://damon.name
    SQLQuery:SELECT first_name, last_name FROM owners JOIN websites ON owners.id = websites.owner_id WHERE domain = 'https://damon.name' LIMIT 5;
    SQLResult: [('Geo', 'Mertz')]
    Answer:Geo Mertz is the owner of the website with domain https://damon.name.
    > Finished chain.

    > Entering new  chain...
    Tell me his email
    SQLQuery:SELECT email FROM owners WHERE first_name = 'Westley' AND last_name = 'Waters'
    SQLResult: [('Ken70@hotmail.com',)]
    Answer:Westley Waters' email is Ken70@hotmail.com.
    > Finished chain.
    {'history': "Human: Who is owner of the website with domain https://damon.name\nAI: Geo Mertz is the owner of the website with domain https://damon.name.\nHuman: Tell me his email\nAI: Westley Waters' email is Ken70@hotmail.com."}

    Well, it saves context to memory but chain doesn't use it to give a proper answer (wrong email). How to fix it?

    Also I don't want to use an agent because I want to manage to do this with a simple chain first. Tell me if it's impossible with simple chain."""
    
    with get_openai_callback() as cb:
        agent.run(question)
        print(f"Total Tokens: {cb.total_tokens}")
        print(f"Prompt Tokens: {cb.prompt_tokens}")
        print(f"Completion Tokens: {cb.completion_tokens}")
        print(f"Total Cost (USD): ${cb.total_cost}")