from typing import Any
from openai import OpenAI, AzureOpenAI
from transformers import AutoTokenizer, AutoConfig
from groq import Groq
import os

def truncate_tokens_hf(string: str, encoding_name: str) -> str:
    """Truncates a text string based on max number of tokens.

    Falls back to a char-based heuristic if the gated meta-llama tokenizer
    is unreachable (no HF token / license not accepted).
    """
    try:
        tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3-8B-Instruct")
        max_tokens = AutoConfig.from_pretrained("meta-llama/Meta-Llama-3-8B-Instruct").max_position_embeddings
        encoded_string = tokenizer.encode(string, return_tensors="pt")
        num_tokens = len(encoded_string[0])
        if num_tokens > max_tokens:
            string = tokenizer.decode(encoded_string[0][-max_tokens+1000:])
        return string
    except Exception:
        max_chars = 120000 * 4
        if len(string) > max_chars:
            string = string[-(max_chars - 4000):]
        return string

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
    """Together-AI-backed helper LLM.

    Falls back to DeepSeek when TOGETHER_API_KEY is not set but DEEPSEEK_API_KEY
    is. The config's model name is ignored in fallback mode (always deepseek-chat).
    """
    def __init__(self, config):
        super().__init__(config)
        if os.environ.get("TOGETHER_API_KEY"):
            self.client = OpenAI(api_key=os.environ["TOGETHER_API_KEY"], base_url="https://api.together.xyz")
            self._model = config["model"]
        elif os.environ.get("DEEPSEEK_API_KEY"):
            self.client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
            self._model = "deepseek-chat"
        else:
            raise EnvironmentError("Set TOGETHER_API_KEY or DEEPSEEK_API_KEY")

    def __call__(self, prompt: str):
        prompt = truncate_tokens_hf(prompt, encoding_name=self._model)
        response = self.client.chat.completions.create(
            temperature=0,
            model=self._model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
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
    """Azure-OpenAI-backed helper LLM.

    Falls back to DeepSeek when the Azure env vars aren't set but DEEPSEEK_API_KEY
    is. Config's model is ignored in fallback mode (always deepseek-chat).
    """
    def __init__(self, config):
        super().__init__(config)
        azure_ready = all(k in os.environ for k in ("API_VERSION",)) and (
            "AZURE_ENDPOINT_GPT35" in os.environ or "AZURE_ENDPOINT_GPT4" in os.environ
        )
        api_key = config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
        if azure_ready and api_key:
            self.client = AzureOpenAI(
                azure_endpoint=os.environ["AZURE_ENDPOINT_GPT35"] if "gpt35" in self.config["model"] else os.environ["AZURE_ENDPOINT_GPT4"],
                api_key=api_key,
                api_version=os.environ["API_VERSION"],
                azure_deployment="ai4code-research-gpt4o",
            )
            self._model = config["model"]
        elif os.environ.get("DEEPSEEK_API_KEY"):
            self.client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
            self._model = "deepseek-chat"
        else:
            raise EnvironmentError("Set Azure (OPENAI_API_KEY + AZURE_ENDPOINT_GPT4 + API_VERSION) or DEEPSEEK_API_KEY")

    def __call__(self, prompt: str):
        response = self.client.chat.completions.create(
            temperature=0,
            model=self._model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ]
        )
        return response.choices[0].message.content

class VLLM(LLM):
    def __init__(self, config):
        super().__init__(config)
        from vllm import LLM as vLLM
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