    
<p align="center">
    <br>
    <img src="assets/logo_1.svg" width="500"/>
    <br>
<p>
<div align="center">
  <a href="https://opensource.org/license/apache-2-0/">
  <img alt="license" src="https://img.shields.io/badge/License-Apache%202.0-green.svg"/>
  </a>
   <a href="https://www.python.org/downloads/release/python-380/">
  <img alt="python" src="https://img.shields.io/badge/python-3.8+-yellow.svg"/>
  </a> 


    
# RepoPilot: A Multi-Agent Library to Explore Your Codebase

<!-- 
[![Code License](https://img.shields.io/badge/Code%20License-Apache_2.0-green.svg)](https://github.com/bdqnghi/CodeTF_personal/blob/main/LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) -->
 </div>   
    
## Table of Contents
  - [Introduction](#introduction)
  - [Installation](#installation-guide)
  - [Getting Started](#getting-started)
  - [Ethical and Responsible Use](#ethical-and-responsible-use) 
  - [License](#license)

## Overview

RepoPilot is a multi-agent system based on Large Language Models (LLMs) designed to assist developers in navigating and understanding codebases. It serves as a next-generation coding assistant, offering insights and actions based on the analysis of the entire code repository.

**RepoPilot Demo:**

[![Video](https://img.youtube.com/vi/JB_j6fWHwSw/0.jpg)](https://youtu.be/JB_j6fWHwSw)

## Installation
RepoPilot uses Zoekt for code search. Please install Zoekt before installing RepoPilot. Zoekt requires latest Go installation, please follow the instructions [here](https://www.linuxedo.com/2021/10/install-latest-golang-on-linux.html) to install Go.

```bash
go get github.com/sourcegraph/zoekt/

# Install Zoekt Index
go get github.com/sourcegraph/zoekt/cmd/zoekt-index
go install github.com/sourcegraph/zoekt/cmd/zoekt-index
# Install Zoekt Web Server
go get github.com/sourcegraph/zoekt/cmd/zoekt-webserver
go install github.com/sourcegraph/zoekt/cmd/zoekt-webserver
```
We also need to install universal-ctags for semantic code search. Please follow the instructions [here](https://github.com/sourcegraph/sourcegraph/blob/main/doc/dev/how-to/zoekt_local_dev.md#install-ctags). Remember to set the environment variable of CTAGS `CTAGS_COMMAND=universal-ctags`.

## Key Features

- **Codebase Exploration**: Enables developers to query about specific features or components within a codebase (e.g., asking about the login feature in a repository).
- **Impact Analysis**: Assesses the potential impact of changes in the codebase, providing a holistic view of how modifications may affect the overall project.
- **Actionable Insight**s: Provides recommendations and executes predefined actions based on the analysis of queries and codebase status.

## Use Cases

- **Feature Inquiry and Analysis**: Developers can inquire about specific features (e.g., authentication systems, API integrations) within the codebase, and RepoPilot provides detailed insights and suggestions for improvement or modification.
- **Code Impact Assessment**: Before implementing changes, developers can assess how these changes might impact the entire repository, including dependencies, performance, and potential bugs.
- **Automated Code Navigation**: Assists in navigating complex codebases, making it easier for developers to understand and work with large and complex projects.

### Example Usages

```python
# Importing the RepoPilot library
import repopilot

# Initialize RepoPilot with the path to your code repository
repo_path = "/path/to/your/codebase"
rp = repopilot.RepoPilot(repo_path)

# Example 1: Natural Language Query about a Feature
# User asks about the login feature in a conversational manner
query = "Please explain how the login features work in this codebase."
login_feature_explanation = rp.query_codebase(query)
print("Login Feature Explanation:")
print(login_feature_explanation)

# Example 2: Impact of Changes in Natural Language
# User asks about the impact of a specific change
change_query = "What would be the impact if I refactor the authentication module?"
change_impact = rp.query_codebase(change_query)
print("Impact of Refactoring Authentication Module:")
print(change_impact)

# Example 3: Code Improvement Suggestions in Conversational Style
# User asks for general improvement suggestions
improvement_query = "How can I improve the code quality of the project?"
improvement_suggestions = rp.query_codebase(improvement_query)
print("Code Improvement Suggestions:")
print(improvement_suggestions)

# Example 4: Searching for Code Patterns using Natural Language
# User wants to find certain types of functions or methods
search_query = "Find all asynchronous functions in the codebase."
async_functions = rp.query_codebase(search_query)
print("Asynchronous Functions Found:")
print(async_functions)

# Example 5: Bug reproduction from Bug reports
# User wants to generate a fail-to-pass test case from a bug report
search_query = "Write a JUnit test case code in java that reproduce the failure behavior of the given bug report as following: {bug_report (in this case is Time 23 Defects4J)}."
bug_reproduction = rp.query_codebase(search_query)
print("Bug Reproduction:")
```

Here is an example of the output of the above code:

```bash
This test case checks that the forID method does not return "Asia/Tehran" when "MET" is passed as the time zone ID. It also asserts that the correct expected mapping should be "Europe/Paris". The test will fail with the current implementation, indicating the presence of the bug.

Here is a JUnit test case that reproduces the failure behavior described in the bug report:

```java
import org.apache.commons.cli.CommandLine;
import org.apache.commons.cli.Options;
import org.junit.Test;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;

public class CommandLineTest {

    @Test
    public void testHasOptionWithNullShouldNotThrowException() {
        CommandLine cmd = new CommandLine(new Options());
        assertFalse("hasOption should return false when passed a null argument", cmd.hasOption(null));
    }

    @Test
    public void testHasOptionWithNullShouldThrowNullPointerException() {
        CommandLine cmd = new CommandLine(new Options());
        assertThrows(NullPointerException.class, () -> cmd.hasOption(null));
    }
}
```


## Architecture
![RepoPilot Architecture](assets/repopilot.png)

RepoPilot is a multi-agent system that consists of three main components: the **Planning Agent**, the **Navigation Agent**, and the **Analysis Agent**. 
- **Planning Agent** is responsible for understanding the user's query and determining a draft plan of action. The planning agent is based on GPT-4 prompted with a query and general information about the codebase.

- **Navigation Agent** is responsible for navigating the codebase, finding relevant code snippets and storing high value information related to the query into the working memory. The navigation agent is implemented with ReAct-like architecture with dynamic backtracking as well as multi-languages language server protocol (mLSP) support to efficiently navigate inside the codebase (go-to-definition, find references, code search, semantic code search, etc).

- **Analysis Agent** is responsible for finally giving the user the insights and recommendations based on the query and the information stored in the working memory. The analysis agent is based on GPT-4 prompted with the query and the information stored in the working memory.


