from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

MODEL_NAME = "google/gemma-3-4b-it"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.bfloat16,
    device_map="auto"
)