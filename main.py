import logging
from hyperagent import HyperAgent
from argparse import ArgumentParser

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger('hyperagent').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def parse():
    args = ArgumentParser()
    args.add_argument("--repo", type=str, required=True)
    args.add_argument("--commit", type=str, default="")
    args.add_argument("--language", type=str, default="python")
    args.add_argument("--prompt", type=str, default="How to add new memory efficient fine-tuning technique to the project?")
    return args.parse_args()
    
if __name__ == "__main__":
    logger.info("Start!")
    args = parse()
    pilot = HyperAgent(args.repo, commit=args.commit, language=args.language, clone_dir="data/repos")
    logger.info("Setup done!")
    
    print(pilot.query_codebase(args.question))