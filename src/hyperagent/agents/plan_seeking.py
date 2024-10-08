from autogen import UserProxyAgent, AssistantAgent, GroupChat, GroupChatManager, Agent, ConversableAgent
from autogen.agentchat.contrib.society_of_mind_agent import SocietyOfMindAgent 
from hyperagent.agents.llms import LocalLLM
from hyperagent.utils import extract_patch
from hyperagent.prompts.utils import react_prompt_message, react_exec_prompt_message

def load_summarizer():
    config = {"model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "system_prompt": "You're a helpful assistant", "max_tokens": 128000}
    summarizer = LocalLLM(config)
    return summarizer

def load_agent_navigator(
    llm_config,
    jupyter_executor,
    sys_prompt,
    summarizer
):
    terminate_condition = lambda x: x.get("content", "").find("Final Answer:") > 0 or "_run" not in x.get("content", "")
    def response_preparer(self, messages):
        plain_messages = [message["content"] for message in messages]
        query = plain_messages[0].split("Query: ")[-1].strip()
        analysis = summarizer(f"Contexts: {' '.join(plain_messages[1:-1])}. Selectively choose the right context and answer the following `{query}`. You should remain the key code snippets.")
        analysis += plain_messages[-1].replace("Final Answer:", "")
        return analysis
    
    navigator_assistant = AssistantAgent(
        "Inner-Navigator-Assistant",
        system_message=sys_prompt,
        llm_config={"config_list": llm_config},
        human_input_mode="NEVER",
    )
    
    navigator_interpreter = UserProxyAgent(
        name="Navigator Interpreter",
        is_termination_msg=terminate_condition,
        llm_config=False,
        code_execution_config={
            "executor": jupyter_executor,
        },
        human_input_mode="NEVER",
        default_auto_reply="",
    )
    
    groupchat_nav = GroupChat(
        agents=[navigator_assistant, navigator_interpreter],
        messages=[],
        speaker_selection_method="round_robin", 
        allow_repeat_speaker=False,
        max_round=15,
    )
    
    manager_nav = GroupChatManager(
        groupchat=groupchat_nav,
        name="Navigator Manager",
        llm_config={"config_list": llm_config},
        max_consecutive_auto_reply=0
    )
    
    navigator = SocietyOfMindAgent(
        "Navigator",
        chat_manager=manager_nav,
        llm_config={"config_list": llm_config},
        response_preparer=response_preparer
    )
    
    navigator.register_hook(
        "process_last_received_message",
        lambda content: react_prompt_message(content),
    )
    return navigator

def load_agent_editor(
    llm_config,
    jupyter_executor,
    sys_prompt,
    repo_dir
):
    terminate_condition = lambda x: x.get("content", "").find("Final Answer:") > 0 or "_run" not in x.get("content", "")
    def response_preparer(self, messages):
        plain_messages = [message["content"] for message in messages]
        query = plain_messages[0].split("Query: ")[-1].strip()
        # analysis = summarizer(f"Summarize the analysis for following {query} in the codebase. Analysis: {' '.join(plain_messages[1:-1])}")
        analysis = f"Here is the current edit patch: {extract_patch(repo_dir)}"
        analysis += plain_messages[-1].replace("Final Answer:", "")
        return analysis
    
    editor_assistant = AssistantAgent(
        "Inner-Editor-Assistant",
        system_message=sys_prompt,
        llm_config={"config_list": llm_config},
        human_input_mode="NEVER",
    )
    
    editor_interpreter = UserProxyAgent(
        name="Editor Interpreter",
        is_termination_msg=terminate_condition,
        llm_config=False,
        code_execution_config={
            "executor": jupyter_executor,
        },
        human_input_mode="NEVER",
        default_auto_reply="",
    )
    
    groupchat_edit = GroupChat(
        agents=[editor_assistant, editor_interpreter],
        messages=[],
        speaker_selection_method="round_robin", 
        allow_repeat_speaker=False,
        max_round=15,
    )
    
    manager_edit = GroupChatManager(
        groupchat=groupchat_edit,
        name="Editor Manager",
        llm_config={"config_list": llm_config},
        max_consecutive_auto_reply=0
    )
    
    editor = SocietyOfMindAgent(
        "Editor",
        chat_manager=manager_edit,
        llm_config={"config_list": llm_config},
        response_preparer=response_preparer
    )
    
    editor.register_hook(
        "process_last_received_message",
        lambda content: react_prompt_message(content),
    )
    return editor

def load_agent_executor(
    llm_config,
    docker_executor,
    sys_prompt,
    summarizer
):
    terminate_condition = lambda x: x.get("content", "").find("Final Answer:") > 0
    def response_preparer(self, messages):
        plain_messages = [message["content"] for message in messages]
        query = plain_messages[0].split("Query: ")[-1].strip()
        analysis = ""
        analysis = summarizer(f"Summarize the bash code execution for following {query} in the codebase, notes that give the key observations. Execution: {' '.join(plain_messages[1:-1])}")
        analysis += plain_messages[-1].replace("Final Answer:", "")
        return plain_messages[-1].replace("Final Answer:", "")
    
    executor_assistant = AssistantAgent(
        "Inner-Executor-Assistant",
        system_message=sys_prompt,
        llm_config={"config_list": llm_config},
        human_input_mode="NEVER",
    )
    
    executor_interpreter = UserProxyAgent(
        name="Executor Interpreter",
        is_termination_msg=terminate_condition,
        llm_config=False,
        code_execution_config={
            "executor": docker_executor,
        },
        human_input_mode="NEVER",
        default_auto_reply="",
    )
    
    groupchat_exec = GroupChat(
        agents=[executor_assistant, executor_interpreter],
        messages=[],
        speaker_selection_method="round_robin", 
        allow_repeat_speaker=False,
        max_round=15,
    )
    
    manager_exec = GroupChatManager(
        groupchat=groupchat_exec,
        name="Executor Manager",
        llm_config={"config_list": llm_config},
        max_consecutive_auto_reply=0
    )
    
    executor = SocietyOfMindAgent(
        "Executor",
        chat_manager=manager_exec,
        llm_config={"config_list": llm_config},
        response_preparer=response_preparer
    )
    
    executor.register_hook(
        "process_last_received_message",
        lambda content: react_exec_prompt_message(content),
    )
    return executor

def load_agent_planner(system_plan, llm_config):
    
    planner = ConversableAgent(
        "Planner",
        system_message=system_plan,
        llm_config={"config_list": llm_config},
        code_execution_config=False,
        human_input_mode="NEVER",
    )
    
    return planner

def load_manager(user_proxy, planner, navigator, editor, executor, llm_config):
    
    def custom_speaker_selection_func(last_speaker: Agent, groupchat: GroupChat):
        """Define a customized speaker selection function.
        A recommended way is to define a transition for each speaker in the groupchat.

        Returns:
            Return an `Agent` class or a string from ['auto', 'manual', 'random', 'round_robin'] to select a default method to use.
        """
        messages = groupchat.messages
        if llm_config["type"] == "patch":
            if last_speaker is user_proxy:
                return planner
            elif "Navigator" in messages[-1]["content"] and last_speaker == planner:
                return navigator
            elif "Editor" in messages[-1]["content"] and last_speaker == planner:
                return editor
            elif "Executor" in messages[-1]["content"] and last_speaker == planner:
                return executor
            else:
                return planner
        else:
            if last_speaker is user_proxy:
                return planner
            elif "Navigator" in messages[-1]["content"] and last_speaker == planner:
                return navigator
            elif "Executor" in messages[-1]["content"] and last_speaker == planner:
                return executor
            else:
                return planner
            
    groupchat = GroupChat(agents=[navigator, editor, executor, planner], messages=[], max_round=20, speaker_selection_method=custom_speaker_selection_func)
    
    def stop_condition(msg):
        if "Final Answer"in msg["content"]:
            return True
        elif all([agent_name not in msg["content"] for agent_name in ["Navigator", "Editor", "Executor"]]) and msg["name"] == "Planner":
            return True
        else:
            return False
    manager = GroupChatManager(name="hyperagent", groupchat=groupchat, llm_config={"config_list": llm_config["plan"]}, is_termination_msg=lambda msg: stop_condition(msg))
    return manager