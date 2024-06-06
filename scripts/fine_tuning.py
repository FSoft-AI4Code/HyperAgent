from datasets import Dataset
import glob
import os
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,HfArgumentParser,TrainingArguments,pipeline, logging
import transformers
from peft import LoraConfig, PeftModel, prepare_model_for_kbit_training, get_peft_model
import json
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer

def get_data():
    data_folder = "data/agent_trajectories/nav"
    all_json_files = glob.glob(os.path.join(data_folder, "**/*.json"), recursive=True)
    system = []
    chat = []
    responses = []
    for file in all_json_files:
        with open(file, "r") as f:
            data = json.load(f)
        system.append(data["system_prompt"])
        chat.append(data["human_message"])
        responses.append(data["system_response"]) 
    
    def create_text_row(system_instruction, input, output):
        text_row = f"""<s>[INST] <</SYS>>\\nSystem: {system_instruction}\\n<</SYS>>\\n\\nHuman: {input}[/INST] \nAssistant: \n{output}</s>"""
        return text_row

    with open("data/repopilot_traces.jsonl", "w") as f:
        for prompt, input, output in zip(system, chat, responses):
            object = {
                "text": create_text_row(prompt, input, output)
            }
            json.dump(object, f)
            f.write("\n")
                
    train_dataset = Dataset.from_dict({
        "text": [create_text_row(system_instruction, input, output) for system_instruction, input, output in zip(system, chat, responses)]
    })
    return train_dataset
    
def main():
    base_model_id = ""
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        load_in_4bit=True,
        quantization_config=bnb_config,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    
    base_model.config.use_cache = False # silence the warnings. Please re-enable for inference!
    base_model.config.pretraining_tp = 1
    base_model.gradient_checkpointing_enable()

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_model_id, trust_remote_code=True)
    tokenizer.padding_side = 'right'
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.add_eos_token = True


    project = "repopilot"
    # base_model_name = "mistral"
    base_model_name = "codellama"
    run_name = base_model_name + "_" + project
    output_dir = "model/" + run_name

    model = prepare_model_for_kbit_training(base_model)
    peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.1,
        r=64,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj","gate_proj"]
    )
    model = get_peft_model(model, peft_config)
    
    #Hyperparamter
    training_arguments = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=1,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=1,
        optim="paged_adamw_32bit",
        save_steps=25,
        logging_steps=25,
        learning_rate=2e-4,
        weight_decay=0.001,
        fp16=False,
        bf16=False,
        max_grad_norm=0.3,
        max_steps=-1,
        warmup_ratio=0.03,
        group_by_length=True,
        lr_scheduler_type="constant",
        report_to="wandb"
    )

    # Initialize the SFTTrainer for fine-tuning
    # Setting sft parameters
    trainer = SFTTrainer(
        model=model,
        train_dataset=get_data(),
        peft_config=peft_config,
        max_seq_length= None,
        dataset_text_field="text",
        tokenizer=tokenizer,
        args=training_arguments,
        packing= False,
    )
    trainer.train()
    model.save_pretrained(output_dir)

if __name__ == "__main__":
    main()