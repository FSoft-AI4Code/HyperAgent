    
<p align="center">
    <br>
    <img src="assets/hyperagent-logo-zip-file/svg/logo-no-background.svg" width="600"/>
    <br>
<p>
<div align="center">
  <a href="https://opensource.org/license/apache-2-0/">
  <img alt="license" src="https://img.shields.io/badge/License-Apache%202.0-green.svg"/>
  </a>
   <a href="https://www.python.org/downloads/release/python-3100/">
  <img alt="python" src="https://img.shields.io/badge/python-3.10+-green.svg"/>
  </a> 

<a href="paper/main.pdf">Technical Report</a>



    
# HyperAgent: Generalist Software Agents to Solve Coding Tasks at Scale

<!-- 
[![Code License](https://img.shields.io/badge/Code%20License-Apache_2.0-green.svg)](https://github.com/bdqnghi/CodeTF_personal/blob/main/LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) -->
 </div>   
    
## Overview

HyperAgent is a generalist multi-agent system designed to tackle a wide spectrum of software engineering (SE) tasks across various programming languages. Unlike existing LLM-based software agents that typically specialize in specific tasks, HyperAgent mimics human developers' workflows to address diverse SE challenges. Comprising four specialized agents (Planner, Navigator, Code Editor, and Executor), it manages the full lifecycle of SE tasks from conception to verification. 

HyperAgent demonstrates state-of-the-art performance in:

- GitHub issue resolution ([SWE-Bench-Python](https://www.swebench.com/))
- Repository-level code generation ([RepoExec-Python](https://github.com/FSoft-AI4Code/RepoExec))
- Fault localization and program repair ([Defects4J-Java](https://github.com/rjust/defects4j))

Notably, HyperAgent is designed to handle a codebase written in a wide range of programming languages. We currently support Python and Java and plan to expand to other languages on other tasks/benchmarks in the future.

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

*Performance comparison on SWE-Bench datasets. Verified (%) and Lite (%) columns show the percentage of resolved instances (out of 500 for Verified, 300 for Lite). Avg Time is in seconds, and Avg Cost is in US​⬤

### Fault Localization on Defects4J

### Program Repair on Defects4J
    
## Architecture
<p align="center">
    <br>
    <img src="assets/method_overview.png" width="950"/>
    <br>
<p>

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
