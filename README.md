    
<p align="center">
    <br>
    <img src="assets/hyperagent-logo-zip-file/svg/logo-no-background.svg" width="600"/>
    <br>
<p>
<div align="center">
    
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT) [![Python 3.8](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/release/python-380/) [![arXiv](https://img.shields.io/badge/📝-Paper-red)](paper/main.pdf)

    
# Generalist Software Engineering Agents to Solve Coding Tasks at Scale

 </div>   
    
## Overview

HyperAgent is a generalist multi-agent system designed to tackle a wide spectrum of software engineering (SE) tasks across various programming languages. Unlike existing LLM-based software agents that typically specialize in specific tasks, HyperAgent mimics human developers' workflows to address diverse SE challenges. Comprising four specialized agents (Planner, Navigator, Code Editor, and Executor), it manages the full lifecycle of SE tasks from conception to verification. 

HyperAgent demonstrates state-of-the-art performance in:

- GitHub issue resolution ([SWE-Bench-Python](https://www.swebench.com/))
- Repository-level code generation ([RepoExec-Python](https://github.com/FSoft-AI4Code/RepoExec))
- Fault localization and program repair ([Defects4J-Java](https://github.com/rjust/defects4j))

Notably, HyperAgent is designed to handle a codebase written in a wide range of programming languages. We currently support Python and Java and plan to expand to other languages on other tasks/benchmarks in the future. We believe we are the first software engineering agent designed to handle a variety of software engineering tasks across multiple programming languages.

### Key Features
- Generalizability: Easily adapts to various tasks with minimal configuration changes.
- Efficiency: Optimized agents manage processes of varying complexity using appropriate LLM capabilities.
- Scalability: Built to handle large-scale, real-world software engineering scenarios effectively.
- Multi-task Proficiency: Excels in GitHub issue resolution, code generation, fault localization, and program repair. existing development workflow with its Python API, allowing for flexible and powerful code interactions.

## Evaluation Results
### Github Issue Resolution on SWE-Bench
| **Method**                    | **Verified (%)** | **Lite (%)** | **Avg Time (s)** | **Avg Cost ($)** |
|--------------------------------|------------------|--------------|------------------|------------------|
| AutoCodeRover + GPT-4o         | 28.80            | 22.7         | 720              | 0.68             |
| SWE-Agent + Claude 3.5 Sonnet  | 33.60            | 23.00        | --               | 1.79             |
| SWE-Agent + GPT-4o             | 23.20            | 18.33        | --               | 2.55             |
| Agentless + GPT-4o             | 33.20            | 24.30        | --               | 0.34             |
| RAG + Claude 3 Opus            | 7.00             | 4.33         | --               | --               |
| HyperAgent-Lite-1              | 27.33            | 21.67        | 132              | 0.45             |
| HyperAgent-Lite-2              | 16.00            | 11.00        | 108              | 0.76             |
| HyperAgent-Full-1              | 31.00            | 24.67        | 320              | 1.82             |
| HyperAgent-Full-2              | **31.40**        | **25.00**    | 210              | 2.01             |
| HyperAgent-Full-3              | --               | --           | --               | --               |

Performance comparison on SWE-Bench datasets. Verified (%) and Lite (%) columns show the percentage of resolved instances (out of 500 for Verified, 300 for Lite). Avg Time is in seconds, and Avg Cost is in US​.

### Repository-Level Code Generation on RepoExec:

| Model                       | Context Used   | Pass@1   | Pass@5   | Cost ($) |
|-----------------------------|----------------|----------|----------|----------|
| **CodeLlama-34b-Python**     | Full           | **42.93%** | 49.54%  | --       |
| CodeLlama-13b-Python         | Full           | 38.65%   | 43.24%   | --       |
| StarCoder                    | Full           | 28.08%   | 33.95%   | --       |
|-----------------------------|----------------|----------|----------|----------|
| WizardLM2 + RAG              | Auto-retrieved | 33.00%   | 49.16%   | 0.04     |
| GPT-3.5-Turbo + RAG          | Auto-retrieved | 24.16%   | 35.00%   | 0.02     |
| WizardLM2 + Sparse RAG       | Auto-retrieved | 34.16%   | 51.23%   | 0.05     |
| GPT-3.5-Turbo + Sparse RAG   | Auto-retrieved | 25.00%   | 35.16%   | 0.03     |
| **HyperAgent-Lite-3**     | Auto-retrieved | 38.33%   | **53.33%** | 0.18     |

RepoExec Results Comparison: HyperAgent-Lite-3 achieves comparable or superior performance to models provided with full context, particularly in Pass@5 (53.33%). It outperforms RAG-based models, demonstrating effective automatic context retrieval from codebases. This highlights the potential of end-to-end solutions like \methodnamews in real-world scenarios where manual context provision is impractical.

### Fault Localization on Defects4J
| Method            | Acc@1        | Cost ($) |
|-------------------|--------------|----------|
| Ochiai            | 20.25%       | --       |
| DeepFL            | 33.90%       | --       |
| Dstar             | 33.90%       | --       |
| Grace             | 49.36%       | --       |
| AutoFL            | 51.00%       | --       |
| **HyperAgent-Lite-1** | **59.70%**   | 0.18     |

Comparison of Acc@1 across Different Fault Localization Methods on the Defects4J dataset. \methodnamews-Lite-1 significantly outperforms all baselines, achieving 59.70% accuracy on this widely-used benchmark. It surpasses the next best method, AutoFL, by 8.7 percentage points, and more than doubles the performance of traditional methods like Dstar and Ochiai. This demonstrates the effectiveness of \methodnamews's approach in precisely locating faults on the first attempt in real-world Java projects, potentially reducing debugging time and effort for developers.

### Program Repair on Defects4J

| Project           | Bugs | Plausible (HyperAgent) | Correct (HyperAgent) | Correct (RepairAgent) | Correct (ITER) | Correct (SelfAPR) |
|-------------------|------|------------------------|-----------------------|-----------------------|----------------|-------------------|
| Chart             | 26   | 20                     | 14                    | 11                    | 10             | 7                 |
| Cli               | 39   | 18                     | 10                    | 8                     | 6              | 8                 |
| Closure           | 174  | 30                     | 24                    | 27                    | 18             | 20                |
| Codec             | 18   | 12                     | 9                     | 9                     | 3              | 8                 |
| Collections       | 4    | 1                      | 1                     | 1                     | 0              | 1                 |
| Compress          | 47   | 12                     | 9                     | 10                    | 4              | 7                 |
| Csv               | 16   | 8                      | 7                     | 6                     | 2              | 1                 |
| Gson              | 18   | 5                      | 4                     | 3                     | 0              | 1                 |
| JacksonCore       | 26   | 6                      | 6                     | 5                     | 3              | 3                 |
| Jacksondatabind   | 112  | 21                     | 14                    | 11                    | 0              | 8                 |
| JacksonXml        | 6    | 1                      | 1                     | 1                     | 0              | 1                 |
| Jsoup             | 93   | 26                     | 24                    | 18                    | 0              | 6                 |
| JxPath            | 22   | 3                      | 2                     | 0                     | 0              | 1                 |
| Lang              | 63   | 24                     | 19                    | 17                    | 0              | 10                |
| Math              | 106  | 36                     | 32                    | 29                    | 0              | 22                |
| Mockito           | 38   | 20                     | 12                    | 6                     | 0              | 3                 |
| Time              | 26   | 6                      | 4                     | 2                     | 2              | 3                 |
|-------------------|------|------------------------|-----------------------|-----------------------|----------------|-------------------|
| Defects4Jv1.2     | 395  | 119                    | 82                    | 74                    | 57             | 64                |
| Defects4Jv2       | 440  | 130                    | 110                   | 90                    | --             | 46                |
|-------------------|------|------------------------|-----------------------|-----------------------|----------------|-------------------|
| **Total**         | **835** | **249**              | **192**               | **164**               | **57**         | **110**           |
| **Percentage**    |      | **(29.8%)**            | **(22.9%)**           | **(19.64%)**          | **(6.82%)**    | **(13.17%)**      |

Results on Defects4J dataset comparing HyperAgent with other repair tools. The table includes the number of bugs, and for HyperAgent, both plausible and correct fixes. For RepairAgent, ITER, and SelfAPR, only the number of correct fixes is shown. Note that ITER does not have results for Defects4Jv2. HyperAgent achieves the best performance with 249 plausible fixes and 192 correct fixes (highlighted in blue).

## Architecture
<p align="center">
    <br>
    <img src="assets/method_overview.png" width="950"/>
    <br>
<p>

## Installation and Usage

( Code will be updated very soon, stay tuned !)

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
