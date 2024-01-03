import os

DEFAULT_GH_TOKEN = os.environ.get("GITHUB_TOKEN", None)
# DEFAULT_LOCAL_AGENT = "FPTAI4Code/Mixtral-RepoPilot-v1"
DEFAULT_LOCAL_AGENT = "model/mistral-7B"
DEFAULT_DEVICES = "0"
DEFAULT_CLONE_DIR = "data/repos"
SEMANTIC_CODE_SEARCH_DB_PATH = "/tmp/semantic_code_search_repopilot/"
ZOEKT_CODE_SEARCH_INDEX_PATH = "/tmp/zoekt_code_search_repopilot/"
DEFAULT_WORKDIR_CLI = "/tmp/repopilot/"
DEFAULT_PLANNER_TYPE = "adaptive"
DEFAULT_VLLM_PORT = 5200
DEFAULT_LANGUAGE = "python"