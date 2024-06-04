from langchain_anthropic import AnthropicLLM
from langchain_community.chat_models.openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI
from langchain_together import ChatTogether
from langchain_community.llms.vllm import VLLM

import os
from repopilot.tools import *

def setup_llm(llm_config):
    #setup llm for planner
    
    model_name = llm_config["model_name"]
    
    if llm_config["is_local"]:
        llm = VLLM(
            model=model_name,
            trust_remote_code=True,
            tensor_parallel_size=1  
        )
    elif "gpt" in model_name:
        llm = ChatOpenAI(temperature=0, model="gpt-4-1106-preview", openai_api_key=os.environ["OPENAI_API_KEY"])
    elif "gpt_azure" in model_name:
        llm = AzureChatOpenAI(temperature=0, openai_api_version="2023-07-01-preview", azure_deployment="aic-ai4code-research")
    elif "gemini" in model_name:
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest")
    elif "together" in model_name:
        llm = ChatTogether(model="meta-llama/Llama-3-70b-chat-hf", api_key=os.environ["TOGETHER_API_KEY"])
    elif "claude" in model_name:
        llm = AnthropicLLM(model=model_name)
    else:
        raise ValueError(f"Unknown model {llm_config['planner']['model']}")
    
    return llm

def setup_llms(llm_configs):
    llm_plan = setup_llm(llm_configs["planner"])
    llm_nav = setup_llm(llm_configs["navigator"])
    llm_gen = setup_llm(llm_configs["generator"])
    llm_exec = setup_llm(llm_configs["executor"])
    return llm_nav, llm_gen, llm_exec, llm_plan

def initialize_tools(repo_dir, db_path, index_path, language):
    nav_tool_cls = [CodeSearchTool, GoToDefinitionTool, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool, OpenFileTool]
    gen_tool_cls = [EditorTool, OpenFileToolForGenerator, FindAllReferencesTool, GoToDefinitionTool, GetTreeStructureTool]
    exec_tool_cls = [BashExecutorTool]
    navigator_tools = []
    generator_tools = []
    executor_tools = []
    for tool_class in nav_tool_cls:
        if issubclass(tool_class, SemanticCodeSearchTool):
            if db_path is None:
                navigator_tools.append(tool_class(repo_dir, language=language, build=True))
            else:
                navigator_tools.append(tool_class(repo_dir, language=language, db_path=db_path, build=False))
        elif issubclass(tool_class, CodeSearchTool):
            navigator_tools.append(tool_class(repo_dir, language=language, index_path=index_path, build=True))
        else:
            navigator_tools.append(tool_class(repo_dir, language=language))

    for tool_class in gen_tool_cls:
        generator_tools.append(tool_class(repo_dir, language=language))
        
    for tool_class in exec_tool_cls:
        executor_tools.append(tool_class(repo_dir))
    return navigator_tools, generator_tools, executor_tools