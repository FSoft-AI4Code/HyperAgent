from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI
from langchain_together import ChatTogether
from langchain_mistralai.chat_models import ChatMistralAI
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
    elif "gpt_azure" in model_name:
        model_name = model_name.replace("gpt_azure/", "")
        llm = AzureChatOpenAI(temperature=0, api_version=os.environ["API_VERSION"], azure_endpoint=os.environ["AZURE_ENDPOINT_GPT4"], api_key=os.environ["OPENAI_API_KEY"], azure_deployment="codevista-openai-eastuse-gpt4o")
    elif "gpt" in model_name:
        llm = ChatOpenAI(temperature=0, model=model_name, openai_api_key=os.environ["OPENAI_API_KEY"])
    elif "gemini" in model_name:
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
    elif "together" in model_name:
        llm = ChatTogether(model=model_name.replace("together/", ""), api_key=os.environ["TOGETHER_API_KEY"], temperature=0)
    elif "claude" in model_name:
        llm = ChatAnthropic(model=model_name)
    elif "mistral" in model_name:
        model_name = model_name.replace("mistral/", "")
        llm = ChatMistralAI(model=model_name, api_key=os.environ["MISTRAL_API_KEY"], temperature=0)
    elif "vllm" in model_name:
        model_name = model_name.replace("vllm/", "")
        llm = VLLM(model=model_name, trust_remote_code=True, tensor_parallel_size=2)
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