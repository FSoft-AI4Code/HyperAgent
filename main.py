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
    repo = "aura-nw/cw-ics721"
    # repo = "huggingface/tokenizers"
    commit = ""
    language = "rust"
    # question = input("Enter your question about your repository: ")
    question = "what is the main flow of the project?"
    # question = "what is UnigramTrainer's role in the tokenizers repo?"
    #TODO: add a check for a local repo execution
    pilot = RepoPilot(repo, commit=commit, openai_api_key=api_key, local=False, language=language, clone_dir="data/repos")
    logger.info("Setup done!")
    
    with get_openai_callback() as cb:
        pilot.query_codebase(question)
        print(f"Total Tokens: {cb.total_tokens}")
        print(f"Prompt Tokens: {cb.prompt_tokens}")
        print(f"Completion Tokens: {cb.completion_tokens}")
        print(f"Total Cost (USD): ${cb.total_cost}")