import sys
sys.path.append("/datadrive05/huypn16/focalcoder/")
import os
import logging
from repopilot import RepoPilot
from langchain.callbacks.manager import get_openai_callback

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger('pylsp').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Start!")
    repo = input("Enter your repo name here: ")
    commit = input("Enter your commit hash here: ")
    question = input("Enter your question about your repository: ")
    pilot = RepoPilot(repo, commit, openai_api_key=None, local=True, language="python", clone_dir="data/repos")
    logger.info("Setup done!")
    
    while True:
        with get_openai_callback() as cb:
            pilot.query_codebase(question)
            print(f"Total Tokens: {cb.total_tokens}")
            print(f"Prompt Tokens: {cb.prompt_tokens}")
            print(f"Completion Tokens: {cb.completion_tokens}")
            print(f"Total Cost (USD): ${cb.total_cost}")