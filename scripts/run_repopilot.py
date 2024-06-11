from repopilot import RepoPilot
from datasets import load_dataset
from argparse import ArgumentParser
from repopilot.utils import extract_patch
import json
import os

template = "You need to identify the cause of the following github issue, collect the relevant information, and provide a solution. Github Issue: ```{issue}```"

def inference_per_instance(instance, output_folder, model_nick_name="repopilot-gpt4o"):
    print(instance["problem_statement"])
    base_commit = instance["base_commit"]
    repo = instance["repo"]
    output_dict = {}
    
    repo_link = f"https://github.com/{repo}"
    pilot = RepoPilot(
        repo_path=repo_link,
        commit=base_commit,
        language="python",
        clone_dir="/datadrive5/huypn16/RepoPilot/evaluation_benchmark/SWE-bench/data/repos_gpt4o",
        verbose=2
    )
    system_input = template.format(issue=instance["problem_statement"])
    # try:
    full_output = pilot.query_codebase({"input": system_input, "previous_steps": []})
    output_dict["full_output"] = full_output
    # except Exception as e:
    #     print(e)
    
    patch = extract_patch(pilot.repo_dir)
    output_dict["model_patch"] = patch
    output_dict["instance_id"] = instance["instance_id"]
    output_dict["model_name_or_path"] = "repopilot"

    output_file = os.path.join(output_folder, f"{model_nick_name}.jsonl")

    with open(output_file, "a+") as f:
        print(json.dumps(output_dict), file=f, flush=True)
        
    # Clean up
    os.system(f"rm -rf {pilot.repo_dir}")
    os.system(f"conda env remove --name {model_nick_name}")

def get_args():
    parser = ArgumentParser()
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument("--output_folder", type=str, default="outputs/")
    return parser.parse_args()

def main():
    args = get_args()
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite")[args.split]
    for instance in dataset:
        inference_per_instance(instance, args.output_folder)

if __name__ == "__main__":
    main()
