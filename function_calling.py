import openai
import json
from datasets import load_dataset
from tools import search_preliminary_inside_project

openai.api_key = "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"
dataset = load_dataset("princeton-nlp/SWE-bench")
bug_report_example = dataset["test"][1000]["problem_statement"]
example_names = "[sca, plt.sca, pyplot.py, SubFigure, axarr]"

def run_preliminary_search(bug_report, repo_dir):
    # Step 1: send the conversation and available functions to GPT
    messages = [
        {"role": "system", "content": "I'm a codebase search agent. I'm responsible to find the most relevant materials in the codebase to help you"},
        {"role": "user", "content": f"""Given a github issue, finding the most relevant variable names, function names, class names that can be used to resolve the github issue.
        Bug report: {bug_report_example}
        Names to search: {example_names}
        Bug report: {bug_report}
        Names to search: """}]
    functions = [
        {
            "name": "search_preliminary_inside_project",
            "description": "Getting all matched identifiers (variable, function, class name) from a python repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "names": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                        "description": "The names of the identifiers to search",
                    },
                },
                "required": ["names"],
            }
        },
        {
            "name": "go_to_definition",
            "description": "Getting the definition of an identifier",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the identifier to search",
                    },
                },
                "required": ["name"],
            
            }
        }
    ]
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        functions=functions,
        function_call="auto",  # auto is default, but we'll be explicit
    )
    print(response)
    response_message = response["choices"][0]["message"]

    # Step 2: check if GPT wanted to call a function
    if response_message.get("function_call"):
        # Step 3: call the function
        # Note: the JSON response may not always be valid; be sure to handle errors
        available_functions = {
            "search_preliminary_inside_project": search_preliminary_inside_project,
        }  # only one function in this example, but you can have multiple
        function_name = response_message["function_call"]["name"]
        function_to_call = available_functions[function_name]
        function_args = json.loads(response_message["function_call"]["arguments"])
        function_response = function_to_call(
            names=function_args.get("names"),
            repo_path=repo_dir,
        )
        return function_response

# preliminary_results = run_preliminary_search(sample_instance["problem_statement"], repo_dir)
# print(preliminary_results)