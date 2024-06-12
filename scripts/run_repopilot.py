from repopilot import RepoPilot
from datasets import load_dataset
from argparse import ArgumentParser
from repopilot.utils import extract_patch
import json
import os
import yaml
import signal

def load_yaml_config(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

template = "You need to identify the cause of the following github issue, collect the relevant information, and provide a solution. Github Issue: ```{issue}```"

def inference_per_instance(instance, output_folder, model_nick_name, llm_configs):
    print(instance["problem_statement"])
    base_commit = instance["base_commit"]
    repo = instance["repo"]
    output_dict = {}
    
    repo_link = f"https://github.com/{repo}"
    pilot = RepoPilot(
        repo_path=repo_link,
        commit=base_commit,
        language="python",
        clone_dir=f"data/repos_{model_nick_name}",
        llm_configs=llm_configs,
        verbose=2
    )
    
    # Define a handler for the timeout
    def handler(signum, frame):
        raise TimeoutError("Execution timed out")

    # Set the timeout duration in seconds
    timeout_duration = 350  # for example, 10 seconds

    # Set the signal handler and a timeout
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout_duration)
    
    system_input = template.format(issue=instance["problem_statement"])
    
    # try:
    full_output = pilot.query_codebase({"input": system_input, "previous_steps": []})
    output_dict["full_output"] = full_output
    # except TimeoutError as e:
    #     output_dict["full_output"] = "Timeout Error"
    #     print(e)
    # except Exception as e:
    #     output_dict["full_output"] = "Error"
    #     print(e)
    # finally:
    #     # Disable the alarm
    #     signal.alarm(0)
    patch = extract_patch(pilot.repo_dir)
    output_dict["model_patch"] = patch
    output_dict["instance_id"] = instance["instance_id"]
    output_dict["model_name_or_path"] = "repopilot"

    output_file = os.path.join(output_folder, f"{model_nick_name}.jsonl")
    # import ipdb; ipdb.set_trace()
    with open(output_file, "a+") as f:
        json.dump(output_dict, f)
        f.write("\n")
        
    # Clean up
    os.system(f"rm -rf {pilot.repo_dir}")
    os.system(f"conda env remove --name {model_nick_name}")

def get_args():
    parser = ArgumentParser()
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument("--output_folder", type=str, default="outputs/")
    parser.add_argument("--config", type=str, default="configs/gpt4o.yaml")
    return parser.parse_args()

def main():
    args = get_args()
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite")[args.split]
    config = load_yaml_config(args.config)
    dataset = dataset.filter(lambda x: "django" not in x["repo"])
    for instance in dataset.select(range(1,10)):
        inference_per_instance(instance, args.output_folder, config["name"], config)

if __name__ == "__main__":
    main()
