from typing import Any
from openai import OpenAI, AzureOpenAI
from vllm import LLM as vLLM
# from vertexvista.utils import truncate_tokens
from groq import Groq
import os


class LLM:
    def __init__(self, config):
        self.system_prompt = config["system_prompt"]
        self.config = config
    
    def __call__(self, *args: Any, **kwds: Any) -> Any:
        pass

class GroqLLM(LLM):
    def __init__(self, config):
        super().__init__(config)
        self.client = Groq(
            api_key=os.environ["GROQ_API_KEY"],
        )
    
    def __call__(self, prompt: str):
        response = self.client.chat.completions.create(
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            model = self.config["model"],
        )
        return response.choices[0].message.content


class LocalLLM(LLM):
    def __init__(self, config):
        super().__init__(config)
        openai_api_key = os.environ["TOGETHER_API_KEY"]
        openai_api_base = "https://api.together.xyz"

        self.client = OpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base,
        )

    def __call__(self, prompt: str):
        # prompt = truncate_tokens_hf(prompt, encoding_name=self.config["model"])
        response = self.client.chat.completions.create(
            temperature=0,
            model=self.config["model"],
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=None
        )
        return response.choices[0].message.content
    

class OpenAILLM(LLM):
    def __init__(self, config):
        super().__init__(config)
        if "openai_api_key" in config:
            openai_api_key = config["openai_api_key"]
        elif "OPENAI_API_KEY" in os.environ:
            openai_api_key = os.environ["OPENAI_API_KEY"]
        else:
            assert False, "OpenAI API key not found"
        self.client = OpenAI(
            api_key=openai_api_key,
        )

    def __call__(self, prompt: str):
        # The line `prompt = truncate_tokens(prompt, encoding_name=self.config["model"],
        # max_length=self.config["max_tokens"])` is calling a function named `truncate_tokens` with
        # three arguments: `prompt`, `encoding_name`, and `max_length`. This function is likely used
        # to truncate the input `prompt` to a specified maximum length based on the model being used
        # and the maximum tokens allowed.
        # prompt = truncate_tokens(prompt, encoding_name=self.config["model"], max_length=self.config["max_tokens"])
        response = self.client.chat.completions.create(
            temperature=0,
            model=self.config["model"],
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ]
        )
        return response.choices[0].message.content


class AzureLLM(LLM):
    def __init__(self, config):
        super().__init__(config)
        if "openai_api_key" in config:
            openai_api_key = config["openai_api_key"]
        elif "OPENAI_API_KEY" in os.environ:
            openai_api_key = os.environ["OPENAI_API_KEY"]
        else:
            assert False, "OpenAI API key not found"

        self.client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_ENDPOINT_GPT35"] if "gpt35" in self.config["model"] else os.environ["AZURE_ENDPOINT_GPT4"],
            api_key=openai_api_key,
            api_version=os.environ["API_VERSION"],
            azure_deployment="ai4code-research-gpt4o"
        )

    def __call__(self, prompt: str):
        # prompt = truncate_tokens(prompt, encoding_name=self.config["model"], max_length=self.config["max_tokens"])
        response = self.client.chat.completions.create(
            temperature=0,
            model=self.config["model"],
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ]
        )
        return response.choices[0].message.content

class VLLM(LLM):
    def __init__(self, config):
        super().__init__(config)
        self.client = vLLM(
            model = config["model"], 
            tensor_parallel_size = 2,
        )
        self.system_prompt = config["system_prompt"]
    
    def __call__(self, prompt: str):
        composed_prompt = f"{self.system_prompt} {prompt}"
        response = self.client.generate(composed_prompt)
        return response[0].outputs[0].text
    
    
if __name__ == "__main__":
    config = {
        "model": "gradientai/Llama-3-8B-Instruct-Gradient-1048k",
        "system_prompt": "Being an helpful AI, I will help you with your queries. Please ask me anything."
    }
    llm = VLLM(config)
    llm("How to create a new column in pandas dataframe?")