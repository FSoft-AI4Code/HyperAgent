import os
import logging
from repopilot import RepoPilot
from langchain.callbacks.manager import get_openai_callback

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger('codetext').setLevel(logging.WARNING)
logging.getLogger('repopilot').setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("multilspy").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Start!")
    api_key = os.environ.get("OPENAI_API_KEY")
    repo = "TempleRAIL/drl_vo_nav"
    commit = ""
    language = "python"
    question = input("Enter your question about your repository: ")
    question = "The current input is the velocity and position of the pedestrians. I want leveraging past trajectory data to predict the future trajectory of the pedestrians. Then this is used as the input of the model. How can I modify the code?"
    #TODO: add a check for a local repo execution
    pilot = RepoPilot(repo, commit=commit, openai_api_key=api_key, local=False, language=language, clone_dir="data/repos")
    logger.info("Setup done!")
    
    with get_openai_callback() as cb:
        pilot.query_codebase(question)
        print(f"Total Tokens: {cb.total_tokens}")
        print(f"Prompt Tokens: {cb.prompt_tokens}")
        print(f"Completion Tokens: {cb.completion_tokens}")
        print(f"Total Cost (USD): ${cb.total_cost}")