    
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
### SWE-Bench
<p align="center">
    <br>
    <img src="assets/swe-bench.png" width="950"/>
    <br>
<p>
    
## Architecture
<p align="center">
    <br>
    <img src="assets/method_overview.png" width="950"/>
    <br>
<p>

