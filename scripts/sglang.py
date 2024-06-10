"""
Usage:
export ANTHROPIC_API_KEY=sk-******
python3 anthropic_example_chat.py
"""
import re
import scripts.sglang as sgl
from scripts.sglang import user, system, assistant
from repopilot.tools.tools import *
from langchain.agents.tools import InvalidTool
from repopilot.prompts.navigator import PREFIX, SUFFIX
from repopilot.agents.plan_seeking import FORMAT_INSTRUCTIONS
from repopilot.build import initialize_tools
from repopilot.utils import print_text
from repopilot.langchain_parsers.struct_parser import StructuredChatOutputParser
from langchain_core.agents import AgentFinish

index_path = "data/indexes"
repo_dir = "data/repos/django"
db_path = "data/indexes"

nav_tool_cls = [CodeSearchTool, GoToDefinitionTool, FindAllReferencesTool, GetAllSymbolsTool, GetTreeStructureTool, OpenFileTool]
nav_tools, gen_tools, exec_tools = initialize_tools(repo_dir, db_path, index_path, "python")

tool_strings = []

for tool in nav_tools:
    args_schema = re.sub("}", "}}", re.sub("{", "{{", str(tool.args)))
    tool_strings.append(f"{tool.name}: {tool.description}, args: {args_schema}")
formatted_tools = "\n".join(tool_strings)

@sgl.function
def ReAct(s, query, parser, max_iterations=10, color="pink", name_to_tool_map=None):
    iter = 0
    prompt = "\n\n".join([PREFIX, formatted_tools, FORMAT_INSTRUCTIONS, SUFFIX])
    s += prompt
    s += f"\nQuery: {query}\n"
    while not (iter >= max_iterations):
        s += sgl.gen("action", max_tokens=1024, stop=["\nObservation:", "Observation:"])
        
        agent_action = parser.parse(s.text().split("Thought:")[-1])
        
        if isinstance(agent_action, AgentFinish):
            break 
        else:
            if agent_action.tool in name_to_tool_map:
                tool = name_to_tool_map[agent_action.tool]
                observation = tool.run(
                    agent_action.tool_input,
                    verbose=False,
                )
            else:
                observation = InvalidTool().run(
                    {
                        "requested_tool_name": agent_action.tool,
                        "available_tool_names": list(name_to_tool_map.keys()),
                    },
                    verbose=False,
                )        
            s += "\nObservation: "  + str(observation) + "\n"   
        iter += 1
    
def nav_agent(query, max_iterations=10, name_to_tool_map=None):
    parser = StructuredChatOutputParser()
    state = ReAct.run(
        query=query, parser=parser, max_iterations=max_iterations, name_to_tool_map=name_to_tool_map
    )
    trace_str = state.text()
    response = trace_str.split("Final Answer:")[-1]
    return response, trace_str

if __name__ == "__main__":
    backend = sgl.Anthropic("claude-3-haiku-20240307")
    sgl.set_default_backend(backend)

    print("\n========== single ==========\n")
    
    query = "Give me the definition of URLValidator"
    name_to_tool_map = {tool.name: tool for tool in nav_tools} 
    response, trace_str = nav_agent(query, name_to_tool_map=name_to_tool_map)
    print_text(response, "pink")
    