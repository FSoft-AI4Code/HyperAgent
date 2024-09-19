from huggingface_hub import HfApi

api = HfApi()

api.upload_file(

    path_or_fileobj="data/data_instruct_nav.json",

    path_in_repo="data_instruct_nav.json",

    repo_id="huypn16/MetaGent-Nav-Instruct-LoRA",

    repo_type="model",

)