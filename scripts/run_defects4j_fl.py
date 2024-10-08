from hyperagent import HyperAgent
from argparse import ArgumentParser
from hyperagent.tasks.fault_localization import FaultLocalization
from hyperagent.constants import D4J_FOLDER
import os
import yaml

def load_yaml_config(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
    return config

def main():
    config = {
        "name": "claude",
        "nav": [{
            "model": "claude-3-haiku-20240307",
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
        "type": "pred"
    }
    
    task = FaultLocalization("results/defects4j_fl", "test", max_repetitions=1, max_num_tests=2, defects4j=D4J_FOLDER)
    result_list = []
    for idx in range(len(task)):
        repo_dir = task[idx]
        pilot = HyperAgent(
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
