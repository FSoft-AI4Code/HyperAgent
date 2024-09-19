import docker
from datasets import load_dataset
from hyperagent.tasks.base import BaseTask, Result
from hyperagent.utils import extract_patch
from swebench.harness.docker_build import build_instance_images

class SWEBench(BaseTask):
    def __init__(self, logdir, split, _type="patch", **kwargs):
        self.max_repetitions = kwargs.get("max_repetitions", 3) 
        self.task_template = """You need to identify the cause of the following github issue, collect the relevant information, and provide a solution. 
        Github Issue: ```{issue}```"""
        
        self.logdir = logdir
        self.dataset = load_dataset("princeton-nlp/SWE-bench_Verified")[split]

        client = docker.from_env()

        successful, failed = build_instance_images(
            client=client,
            dataset=self.dataset,
            force_rebuild=False,
            max_workers=12,
        )

        self.images = {specs.instance_id: specs.instance_image_key for specs in successful}
        self.dataset = self.dataset.filter(lambda x: x["instance_id"] in [specs.instance_id for specs in successful])
        self.setup_scripts = ["\n".join(["#!/bin/bash", "set -euxo pipefail"] + specs.env_script_list) + "\n" for specs in successful]

    
    def construct_prompt(self, idx):
        instance = self.dataset[idx]
        return self.task_template.format(issue=instance["problem_statement"])

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, idx):
        repo = self.dataset[idx]["repo"]
        commit = self.dataset[idx]["base_commit"]
        instance_id = self.dataset[idx]["instance_id"]

        repo_link = f"https://github.com/{repo}"
        return repo_link, commit, instance_id, self.images[instance_id]

    def run(self, system, idx) -> Result:
        prompt = self.construct_prompt(idx)
        system.query_codebase(prompt)
        prediction_patch = extract_patch(system.repo_dir)
        return prediction_patch
    

    def validate(self, proposed_patch, idx: int):
        pass

if __name__ == "__main__":
    task = SWEBench("logs", "test")
    task.run()