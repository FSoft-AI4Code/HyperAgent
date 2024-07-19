from repopilot import RepoPilot
from datasets import load_dataset
from argparse import ArgumentParser
from repopilot.tasks.automated_program_repair import AutomatedProgramRepair

import os
import yaml

def load_yaml_config(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def get_args():
    parser = ArgumentParser()
    parser.add_argument("--split", type=str, default="test")
    parser.add_argument("--config", type=str, default="configs/gpt4o.yaml")
    return parser.parse_args()

def main():
    args = get_args()
    # config = load_yaml_config(args.config)
    
    config = {
        "name": "claude",
        "nav": [{
            "model": "claude-3-haiku-20240307",
            # "model": "claude-3-5-sonnet-20240620",
            "api_type": os.environ.get("ANTHROPIC_API_KEY"),
            "stop_sequences": ["\nObservation:"],
            "base_url": "https://api.anthropic.com",
            "api_type": "anthropic",
        }],
        "edit": [{
            "model": "claude-3-5-sonnet-20240620",
            "api_type": os.environ.get("ANTHROPIC_API_KEY"),
            "stop_sequences": ["\nObservation:"],
            "price": [0.003, 0.015],
            "base_url": "https://api.anthropic.com",
            "api_type": "anthropic",
        }],
        "exec": [{
            "model": "claude-3-haiku-20240307",
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
    
    task = AutomatedProgramRepair(logdir="results/defects4j_apr", split="test", max_repetitions=1, max_num_tests=2, defects4j="/datadrive5/huypn16/defects4j")
    result_list = []
    for idx in range(1, 25):
        repo_dir = task[idx]
        pilot = RepoPilot(
            repo_path=repo_dir,
            commit="",
            language="java",
            llm_configs=config,
            verbose=2,
        )
        result = task.run(pilot, idx)
        result_list.append(result)
        performance_table = task.report(result_list)
        print(performance_table)
    
if __name__ == "__main__":
    main()
