import logging
from hyperagent import HyperAgent

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
    repo = input("Please provide a valid folder path or GitHub URL: ")
    commit = input("Please provide a commit: (default: HEAD if enter)")
    language = input("Please provide a programming language: (default: python if enter)")
    question = input("Please provide a question: ")
    pilot = HyperAgent(repo, commit=commit, language=language, clone_dir="data/repos")
    logger.info("Setup done!")
    
    print(pilot.query_codebase(question))