from openai import OpenAI
from repopilot.utils import truncate_tokens, truncate_tokens_hf
import os

class LLM:
    def __init__(self, config):
        if config["model"].startswith("local:"):
            openai_api_key = "aca586edef32c3f95ed93a70830fe9fb0c38c3f408de8054370c501db0c65268"
            openai_api_base = "https://api.together.xyz"

            self.client = OpenAI(
                api_key=openai_api_key,
                base_url=openai_api_base,
            )
        else:
            if "openai_api_key" in config:
                openai_api_key = config["openai_api_key"]
            elif "OPENAI_API_KEY" in os.environ:
                openai_api_key = os.environ.get["OPENAI_API_KEY"]
            else:
                assert False, "OpenAI API key not found"
            
            self.client = OpenAI(
                api_key=openai_api_key,
            )
        self.system_prompt = config["system_prompt"]
        self.config = config
        
    def __call__(self, prompt: str):
        if not self.config["model"].startswith("local:"):
            prompt = truncate_tokens(prompt, encoding_name=self.config["model"], max_length=self.config["max_tokens"])
        else:
            prompt = truncate_tokens_hf(prompt, encoding_name=self.config["model"].split("local:")[0])
        response = self.client.chat.completions.create(
            temperature=0,
            model=self.config["model"].split("local:")[-1] if self.config["model"].startswith("local:") else self.config["model"],
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ]
        )
        return response.choices[0].message.content