from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

def args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter_dir", type=str, required=True)
    parser.add_argument("--full_model_dir", type=str, required=True)
    parser.add_argument("--base_model_path_or_name", type=str, required=True)
    return parser.parse_args()

def main():
    script_args = args()
    model_for_merge = AutoModelForCausalLM.from_pretrained(
            script_args.base_model_path_or_name,
            torch_dtype=torch.float16,
        )
    tokenizer = AutoTokenizer.from_pretrained(script_args.base_model_path_or_name, trust_remote_code=True)
    full_model = PeftModel.from_pretrained(model_for_merge,
                                        model_id=script_args.adapter_dir,
                                        )
    full_model = full_model.base_model.merge_and_unload()  
    full_model.save_pretrained(script_args.full_model_dir)
    tokenizer.save_pretrained(script_args.full_model_dir)
    
if __name__ == "__main__":
    main()