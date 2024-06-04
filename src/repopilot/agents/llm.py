from openai import OpenAI
from openai import AzureOpenAI
from repopilot.utils import truncate_tokens, truncate_tokens_hf
import os

endpoint = os.getenv("AZURE_ENDPOINT")
api_version = os.getenv("AZURE_API_VERSION")
api_key = os.getenv("AZURE_API_KEY")
model_name = os.getenv("AZURE_MODEL_NAME")

class LLM:
    def __init__(self, config):
        self.client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key
        )
        self.system_prompt = config["system_prompt"]
        self.config = config

    def __call__(self, prompt: str):
        prompt = truncate_tokens(prompt, encoding_name="gpt-4", max_length=self.config["max_tokens"])
        response = self.client.chat.completions.create(
            temperature=0,
            model=model_name,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ]
        )
        return response.choices[0].message.content
    
    