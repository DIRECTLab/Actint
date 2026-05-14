from .model import model, tokenizer
from .queue import gpu_queue

import torch
from transformers import StoppingCriteria, StoppingCriteriaList


class StopOnTokens(StoppingCriteria):
    def __init__(self, stop_token_ids: list[list[int]]):
        self.stop_token_ids = stop_token_ids

    def __call__(self, input_ids, scores, **kwargs):
        for stop_ids in self.stop_token_ids:
            if len(input_ids[0]) >= len(stop_ids):
                if input_ids[0][-len(stop_ids):].tolist() == stop_ids:
                    return True
        return False


async def generate(prompt: str, max_tokens: int = 50):
    async def _infer():
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        input_len = inputs["input_ids"].shape[-1]

        stop_string = "</final>"
        stop_token_ids = [
            tokenizer.encode(stop_string, add_special_tokens=False)
        ]
        stopping_criteria = StoppingCriteriaList([StopOnTokens(stop_token_ids)])

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                do_sample=False,
                repetition_penalty=1.1,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
                stopping_criteria=stopping_criteria,
            )

        generated_ids = output[0][input_len:]
        text = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        return text.replace("</final>", "").strip()

    return await gpu_queue.run(_infer)