from transformers import AutoTokenizer, AutoModelForCausalLM
from datasets import load_dataset

dataset = load_dataset("princeton-nlp/SWE-bench")

tokenizer = AutoTokenizer.from_pretrained("princeton-nlp/SWE-Llama-13b",)
model = AutoModelForCausalLM.from_pretrained("princeton-nlp/SWE-Llama-13b").cuda()

print(dataset["train"][0])
import ipdb; ipdb.set_trace()