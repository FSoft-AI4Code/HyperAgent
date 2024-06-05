import os

DEFAULT_GH_TOKEN = os.environ.get("GITHUB_TOKEN", None)
DEFAULT_DEVICES = "0"
DEFAULT_CLONE_DIR = "data/repos"
SEMANTIC_CODE_SEARCH_DB_PATH = "/tmp/semantic_code_search_repopilot/"
ZOEKT_CODE_SEARCH_INDEX_PATH = "/tmp/zoekt_code_search_repopilot/"
DEFAULT_WORKDIR_CLI = "/tmp/repopilot/"
DEFAULT_PLANNER_TYPE = "static"
DEFAULT_VLLM_PORT = 5200
DEFAULT_LANGUAGE = "python"
DEFAULT_VERBOSE_LEVEL = 1
DEFAULT_TRAJECTORIES_PATH = "/datadrive5/huypn16/RepoPilot/data/agent_trajectories"
DO_NOT_SUMMARIZED_KEYS = ["python", "code_snippet"]

DEFAULT_LLM_CONFIGS = {
    "planner": {
        "model_name": "gemini-1.5-pro-latest",
        "is_local": False,
    },
    "navigator": {
        "model_name": "claude-3-haiku-20240307",
        "is_local": False,
    },
    "generator": {
        "model_name": "gemini-1.5-pro-latest",
        "is_local": False,
    },
    "executor": {
        "model_name": "claude-3-haiku-20240307",
        "is_local": False,
    }
}
