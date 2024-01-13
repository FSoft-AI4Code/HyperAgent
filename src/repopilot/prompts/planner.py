PLANNER_TEMPLATE = """Given following general information about the repository such as repository structure:
{struct}
and given following tools:
{formatted_tools}
Let's first understand the query and devise a plan to seek the useful information from the repository to answer the query. Only generate the steps that seek the information from the repository.
Please output the plan starting with the header 'Plan:' and then followed by a numbered list of steps.
Make the plan the minimum number of steps required (no more than 4 steps), nomarlly 1-3 steps are enough. The step should hint which set of tools to be used to accurately complete the task. 
If the information in the query is uncleared, consider use get tree structure to get overview folder structure then exlpore.
At the end of your plan, say '<END_OF_PLAN>'.
"Example:\n"
{examples}
"""

ADAPTIVE_PLANNER_TEMPLATE = """Given following general information about the repository such as repository structure:
{struct}
and given following tools:
{formatted_tools}
Let's first understand the query and devise a plan to seek the useful information from the repository to answer the query. Please output the plan starting with the header 'Plan:' and then followed by a numbered list of steps.
<Important!>Please make the plan the minimum number of steps required (no more than 4 steps), nomarlly 1-3 steps are enough. The step should hint which set of tools to be used to accurately complete the task. 
If the information in the query is uncleared, consider use get tree structure to get overview folder structure then exlpore.
At the end of your plan, say '<END_OF_PLAN>'. If the question only cares about some specific, simple information, you can generate 2 steps plan, the first step is to find the information using semantic code search and the second step is to respond to the question.
If you are given the responses as well as observation from your previous steps, please consider change the plan if necessary.
"Example:\n"
{examples}
"""