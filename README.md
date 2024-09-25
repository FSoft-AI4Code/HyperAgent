    
<p align="center">
    <br>
    <img src="assets/hyperagent-logo-zip-file/svg/logo-no-background.svg" width="600"/>
    <br>
<p>
<div align="center">
 


[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT) [![Python 3.10](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-380/) [![arXiv](https://img.shields.io/badge/📝-Paper-red)](paper/main.pdf)

    
# Generalist Software Engineering Agents to Solve Coding Tasks at Scale

<!-- 
[![Code License](https://img.shields.io/badge/Code%20License-Apache_2.0-green.svg)](https://github.com/bdqnghi/CodeTF_personal/blob/main/LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) -->
 </div>   
    
## Overview

HyperAgent is a generalist multi-agent system designed to tackle a wide spectrum of software engineering (SE) tasks across various programming languages. Unlike existing LLM-based software agents that typically specialize in specific tasks, HyperAgent mimics human developers' workflows to address diverse SE challenges. Comprising four specialized agents (Planner, Navigator, Code Editor, and Executor), it manages the full lifecycle of SE tasks from conception to verification. 

HyperAgent demonstrates state-of-the-art performance in:

- GitHub issue resolution ([SWE-Bench-Python](https://www.swebench.com/)): 31.4% on Resolved Rate on SWE-Bench Verified and 25% on SWE-Bench Lite.
- Repository-level code generation ([RepoExec-Python](https://github.com/FSoft-AI4Code/RepoExec)): 53.3% on Pass@5.
- Fault localization and program repair ([Defects4J-Java](https://github.com/rjust/defects4j)): 249 bugs fixed.

Notably, HyperAgent is designed to handle a codebase written in a wide range of programming languages. We currently support Python and Java and plan to expand to other languages on other tasks/benchmarks in the future. We believe we are the first software engineering agent designed to handle a variety of software engineering tasks across multiple programming languages.

### Key Features
- Generalizability: Easily adapts to various tasks with minimal configuration changes.
- Efficiency: Optimized agents manage processes of varying complexity using appropriate LLM capabilities.
- Scalability: Built to handle large-scale, real-world software engineering scenarios effectively.
- Multi-task Proficiency: Excels in GitHub issue resolution, code generation, fault localization, and program repair. existing development workflow with its Python API, allowing for flexible and powerful code interactions.

## Architecture
<p align="center">
    <br>
    <img src="assets/method_overview.png" width="950"/>
    <br>
<p>

## Installation and Usage
HyperAgent uses Zoekt for code search. Please install Zoekt before installing HyperAgent. Zoekt requires latest Go installation, please follow the instructions [here](https://www.linuxedo.com/2021/10/install-latest-golang-on-linux.html) to install Go.

```bash
go get github.com/sourcegraph/zoekt/

# Install Zoekt Index
go install github.com/sourcegraph/zoekt/cmd/zoekt-index
# Install Zoekt Web Server
go install github.com/sourcegraph/zoekt/cmd/zoekt-webserver
```
We also need to install universal-ctags for semantic code search. Please follow the instructions [here](https://github.com/sourcegraph/sourcegraph/blob/main/doc/dev/how-to/zoekt_local_dev.md#install-ctags). Remember to set the environment variable of CTAGS `CTAGS_COMMAND=universal-ctags`. 

After installing Zoekt and universal-ctags, we can install HyperAgent by running the following commands, notes that it's a must to create a new conda environment before installing HyperAgent named hyperagent, since the Executor uses jupyter kernel named hyperagent to execute the code:
```bash
conda create -n hyperagent python=3.10
pip3 install -e .
```

### Quick Test
To test the hyperagent with general prompt, you can run the following command:
```bash
python3 main.py --repo "your/path/to/repo" --commit "commit_hash" --language "python" --clone_dir "data/repos" --prompt "I want to create an FastAPI app to handle GET request from OpenAI API"
```
### General usage
```python
from hyperagent import HyperAgent
pilot = HyperAgent(repo, commit=commit, language=language, clone_dir="data/repos")
```
with `repo` is the repository URL, `commit` is the commit hash, `language` is the programming language of the repository, and `clone_dir` is the directory to store the cloned repository. You also can configure the agents by setting the `config` parameter. 

Hyperagent supports 2 modes: patch and predict. In the patch mode, the agent will generate a patch for the given task. In the predict mode, the agent will predict the next token for the given task (for example, repoQA or fault location).

```python
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
```

HyperAgent is a software generalist agent, therefore it can be used to solve various software engineering tasks. We provide a few examples of how to use HyperAgent to solve different tasks in the `scripts` folder. This is easily configured via an input template prompt for each task.

For example, in `src/hyperagent/tasks/github_issue_resolution.py`, we provide a script to resolve GitHub issues using HyperAgent. The script will prompt the user to input the issue title and description, and then HyperAgent will generate a patch to resolve the issue. 
```python
def run(self, system, idx) -> Result:
      prompt = self.construct_prompt(idx)
      system.query_codebase(prompt)
      prediction_patch = extract_patch(system.repo_dir)
      return prediction_patch
```

If you want to use HyperAgent to solve other tasks and systematically evaluate the results, you can create a new task class and implement the `run` method. The `run` method should return the result of the task. 

## Reproduce Evaluation Results
To reproduce the results, please follow the instructions in the `scripts` folder. We provide the scripts to reproduce the results on SWE-Bench, RepoExec, and Defects4J datasets.

### SWE-Bench
```bash
python3 scripts/run_swe_bench.py --split "test"
```

### Fault Localization
```bash
python3 scripts/run_defects4j_fl.py
```

### Program Repair
```bash
python3 scripts/run_defects4j_apr.py
```

###

# Citing HyperAgent

If you're using HyperAgent in your research or applications, please cite using this BibTeX:
```bibtex
@article{huy2024hyperagent,
  title={HyperAgent: Generalist Software Engineering Agents to Solve Coding Tasks at Scale},
  author={Phan, Huy Nhat and Nguyen, Phong X and Bui, Nghi DQ},
  journal={arXiv preprint arXiv:2406.11912},
  year={2024}
}
```

# Contact us
If you have any questions, comments or suggestions, please do not hesitate to contact us.
- Website: [fpt-aicenter](https://www.fpt-aicenter.com/ai-residency/)
- Email: bdqnghi@gmail.com

# License
[MIT License](LICENSE)
