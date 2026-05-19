from smolagents import Model
from llama_cpp import Llama


class LlamaCppModel(Model):
    def __init__(self, model_path: str):
        self.llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1,
            n_ctx=4096,
        )

    def generate(self, messages, stop=None, max_new_tokens=512, temperature=0.7, top_p=0.9, **kwargs):
        prompt = self._format_messages(messages)

        output = self.llm(
            prompt,
            max_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            repeat_penalty=1.1,
            stop=stop or [],
        )

        return output["choices"][0]["text"]

    def _format_messages(self, messages):
        prompt = ""

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "user":
                prompt += f"<|user|>\n{content}\n"
            elif role == "assistant":
                prompt += f"<|assistant|>\n{content}\n"
            elif role == "system":
                prompt += f"<|system|>\n{content}\n"

        prompt += "<|assistant|>\n"
        return prompt