import os

DEFAULT_GH_TOKEN = os.environ.get("GITHUB_TOKEN", None)
DEFAULT_DEVICES = "0"
DEFAULT_CLONE_DIR = "data/repos"
SEMANTIC_CODE_SEARCH_DB_PATH = "/tmp/semantic_code_search_repopilot/"
ZOEKT_CODE_SEARCH_INDEX_PATH = "/tmp/zoekt_code_search_repopilot/"
DEFAULT_PATCHES_DIR = "/tmp/repopilot/patches/"
DEFAULT_WORKDIR_CLI = "/tmp/repopilot/"
DEFAULT_PLANNER_TYPE = "static"
DEFAULT_VLLM_PORT = 5200
DEFAULT_LANGUAGE = "python"
DEFAULT_VERBOSE_LEVEL = 1
DEFAULT_TRAJECTORIES_PATH = "/datadrive5/huypn16/RepoPilot/data/agent_trajectories/nav"
DO_NOT_SUMMARIZED_KEYS = ["python", "code_snippet"]

DEFAULT_LLM_CONFIGS = {
    "planner": {
        # "model_name": "vllm/dreamgen/WizardLM-2-8x22B",
        # "model_name": "accounts/fireworks/models/qwen2-72b-instruct",
        "model_name": "together/Qwen/Qwen2-72B-Instruct",
        # "model_name": "MaziyarPanahi/WizardLM-2-8x22B-AWQ",
        # "is_local": True,
        "is_local": False
    },
    "navigator": {
        "model_name": "claude-3-haiku-20240307",
        "is_local": False,
    },
    "generator": {
        # "model_name": "Qwen/Qwen2-72B-Instruct",
        "model_name": "claude-3-haiku-20240307",
        "is_local": False,
    },
    "executor": {
        "model_name": "together/Qwen/Qwen2-72B-Instruct",
        "is_local": False,
    }
}