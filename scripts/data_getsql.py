import sqlite3
import ast
import pickle
import tqdm
from transformers import AutoTokenizer
import json

# Path to your SQLite database file
db_path = '.cache/41/cache.db'
connection = sqlite3.connect(db_path)

# Create a cursor object to interact with the database
cursor = connection.cursor()

# Example query: Get all tables in the database
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

tables = cursor.fetchall()
print("Tables in the database:", tables)
cursor.execute("SELECT * FROM Cache;")
rows = cursor.fetchall()
data = []

for row in tqdm.tqdm(rows):
    append_flag = False
    completion = pickle.loads(row[11]).choices[0].message
    prompt_messages = [message for message in ast.literal_eval(row[1])["messages"]]
    for message in prompt_messages:
        if "name" in message.keys():
            if "Navigator Interpreter" == message["name"]:
                append_flag = True
    
    if append_flag:
        messages = [message["content"] for message in prompt_messages]

        def map_role(index: int):
            if index == 0:
                return "system"
            elif index % 2 == 1:
                return "user"
            else:
                return "assistant"

        convo_messages = [{"role": map_role(i), "content": message} for i, message in enumerate(messages) if "exit code: 1" not in message]
        
        data.append(
            {
                "messages": convo_messages,
            }
        )

with open("data/data_instruct_nav.json", "w") as f:
    json.dump(data, f, indent=4)
print('Total data:', len(data))
# tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3-8B-Instruct")

# prompt_lens = []
# completion_lens = []
# for data_point in tqdm.tqdm(data):
#     prompt_length = len(tokenizer.encode(" ".join(data_point["prompt"])))
#     completion_length = len(tokenizer.encode(data_point["completion"]))
#     prompt_lens.append(prompt_length)
#     completion_lens.append(completion_length)

# #common stats
# print("Prompt length stats:")
# print("Min:", min(prompt_lens))
# print("Max:", max(prompt_lens))
# print("Mean:", sum(prompt_lens) / len(prompt_lens))
# print("Median:", sorted(prompt_lens)[len(prompt_lens) // 2])
# print("Prompt length stats:")
# print("Min:", min(completion_lens))
# print("Max:", max(completion_lens))
# print("Mean:", sum(completion_lens) / len(completion_lens))
# print("Median:", sorted(completion_lens)[len(completion_lens) // 2])

# print("Total tokens:", sum(prompt_lens) + sum(completion_lens))

# Close the cursor and connection
cursor.close()
connection.close()