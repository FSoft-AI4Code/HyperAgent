from datasets import load_dataset

dataset = load_dataset("princeton-nlp/SWE-bench_Lite")["test"]
dataset = dataset.filter(lambda x: "django" not in x["repo"])
dataset = dataset.select(range(1,100))
dataset.to_json("task_instances.jsonl")