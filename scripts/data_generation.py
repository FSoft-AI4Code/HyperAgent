from hyperagent import HyperAgent

import os
import logging
from hyperagent import HyperAgent
from langchain.callbacks.manager import get_openai_callback
from langchain.utilities.portkey import Portkey

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger('codetext').setLevel(logging.WARNING)
logging.getLogger('hyperagent').setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("multilspy").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Start!")
    api_key = os.environ.get("OPENAI_API_KEY")
    # repo = "aura-nw/cw-ics721"
    repo = "huggingface/peft"
    # repo = "TempleRAIL/drl_vo_nav"
    commit = "ee6f6dcee70b6e3626518816e8f0116c7083fe6f"
    language = "python"
    # question = input("Enter your question about your repository: ")
    # question = "what is the main flow of the project?"
    question = """How to add new memory efficient fine-tuning technique to the project?"""
    #TODO: add a check for a local repo execution
    pilot = HyperAgent(repo, commit=commit, openai_api_key=api_key, local=False, language=language, clone_dir="data/repos", save_trajectories_path=f"data/trajectories/{language}/feature_rq/{repo}")
    logger.info("Setup done!")
    
    with get_openai_callback() as cb:
        pilot.query_codebase(question)
        print(f"Total Tokens: {cb.total_tokens}")
        print(f"Prompt Tokens: {cb.prompt_tokens}")
        print(f"Completion Tokens: {cb.completion_tokens}")
        print(f"Total Cost (USD): ${cb.total_cost}")