from datasets import load_dataset
import json
import tqdm 

output_file = "outputs/gpt4o.jsonl"

data = []
with open(output_file, "r") as f:
    lines = f.readlines()
    for line in tqdm.tqdm(lines):
        try:
            pred = json.loads('{' + '"model_patch' + line.split("model_patch")[1])
            if pred["model_patch"] == "":
                continue
            data.append(pred)
        except:
            continue
# File path for the output JSON file

output_file = 'convert_preds_gpt4o.json'

instance_ids = [instance["instance_id"] for instance in data]

# Writing the list to a JSON file as a JSON array
with open(output_file, 'w') as file:
    json.dump(data, file, indent=4)

dataset = load_dataset("princeton-nlp/SWE-bench_Lite")["test"]
dataset = dataset.filter(lambda x: x["instance_id"] in instance_ids)
# dataset = dataset.select(range(1,186))
dataset.to_json("task_instances.jsonl")