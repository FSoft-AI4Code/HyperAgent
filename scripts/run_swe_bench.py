from hyperagent import HyperAgent
from argparse import ArgumentParser
from hyperagent.tasks.github_issue_resolve import SWEBench
import json
import os
import json
import subprocess

def get_args():
    parser = ArgumentParser()
    parser.add_argument("--split", type=str, default="verified")
    parser.add_argument("--output_folder", type=str, default="outputs/")
    parser.add_argument("--model_nick_name", type=str, default="claude-mini")
    return parser.parse_args()

def main():
    args = get_args()

    subprocess.run(["sudo", "rm", "-rf", "data/repos"])
    subprocess.run(["sudo", "mkdir", "-p", "data/repos"])
    subprocess.run(["sudo", "chmod", "777", "data/repos"])

    config = {
        "name": "claude",
        "nav": [{
            "model": "claude-3-haiku-20240307",
            "api_key": os.environ.get("ANTHROPIC_API_KEY"),
            "stop_sequences": ["\nObservation:"],
            "base_url": "https://api.anthropic.com",
            "api_type": "anthropic",
        }],
        "edit": [{
            "model": "claude-3-5-sonnet-20240620",
            "api_key": os.environ.get("ANTHROPIC_API_KEY"),
            "stop_sequences": ["\nObservation:"],
            "price": [0.003, 0.015],
            "base_url": "https://api.anthropic.com",
            "api_type": "anthropic",
        }],
        "exec": [{
            "model": "claude-3-5-sonnet-20240620",
            "api_type": os.environ.get("ANTHROPIC_API_KEY"),
            "stop_sequences": ["\nObservation:"],
            "price": [0.003, 0.015],
            "base_url": "https://api.anthropic.com",
            "api_type": "anthropic",
        }],
        "plan": [{
            "model": "claude-3-5-sonnet-20240620",
            "api_type": os.environ.get("ANTHROPIC_API_KEY"),
            "price": [0.003, 0.015],
            "base_url": "https://api.anthropic.com",
            "api_type": "anthropic",
        }],
        "type": "patch"
    }
    
    task = SWEBench(logdir="results/swe_bench", split=args.split)
    for idx in range(len(task)):
        repo_link, commit, instance_id, image_name = task[idx]
        success = False
        retry = 0
        while success != True:
            pilot = HyperAgent(
                repo_path=repo_link,
                commit=commit,
                language="python",
                clone_dir="data/repos",
                llm_configs=config,
                image_name=image_name,
                verbose=1
            )
            try:
                patch = task.run(pilot, idx)
            except Exception as e:
                print(e)
                patch = ""
            if len(patch) > 0:
                success = True
            retry += 1

            if retry > 3:
                break

        output_dict = {}

        output_dict["model_patch"] = patch
        output_dict["instance_id"] = instance_id
        output_dict["model_name_or_path"] = "hyperagent"

        output_file = os.path.join(args.output_folder, f"{args.model_nick_name}.jsonl")
        with open(output_file, "a+") as f:
            json.dump(output_dict, f)
            f.write("\n")

if __name__ == "__main__":
    main()