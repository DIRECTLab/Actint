from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import time
import torch
import sys
from transformers import AutoTokenizer, AutoModelForCausalLM

model_name = "Qwen/Qwen3.5-9B"
ml_models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading {model_name} on {device}...")
    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if device == "cuda":
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto"
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(model_name)
        
    model.eval()
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model.config.pad_token_id = tokenizer.pad_token_id
    
    ml_models["model"] = model
    ml_models["tokenizer"] = tokenizer
    ml_models["device"] = next(model.parameters()).device
    print("Model loaded successfully!")
    yield
    # Cleanup on exit
    ml_models.clear()

app = FastAPI(lifespan=lifespan)

@app.get("/test/")
def test():
    return {"message": "Hello World"}

# Define request/response structures matching hugingface_hub's text_generation parameters
class GenerateParameters(BaseModel):
    max_new_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    do_sample: Optional[bool] = True

class GenerateRequest(BaseModel):
    inputs: str
    parameters: Optional[GenerateParameters] = Field(default_factory=GenerateParameters)

class GenerateResponse(BaseModel):
    generated_text: str

@app.post("/", response_model=List[GenerateResponse])
@app.post("/generate", response_model=List[GenerateResponse])
async def generate(request: GenerateRequest):
    print(f"Request Incoming:\n{request}", file=sys.stderr)
    model = ml_models["model"]
    tokenizer = ml_models["tokenizer"]
    device = ml_models["device"]
    
    inputs = tokenizer(request.inputs, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    gen_kwargs = {
        "pad_token_id": tokenizer.pad_token_id,
        "max_new_tokens": request.parameters.max_new_tokens,
    }
    
    if request.parameters.do_sample:
        gen_kwargs["do_sample"] = True
        if request.parameters.temperature is not None:
            gen_kwargs["temperature"] = request.parameters.temperature
        if request.parameters.top_p is not None:
            gen_kwargs["top_p"] = request.parameters.top_p
            
    with torch.inference_mode():
        outputs = model.generate(**inputs, **gen_kwargs)
        
    input_length = inputs['input_ids'].shape[1]
    generated_tokens = outputs[0][input_length:]
    output_text = tokenizer.decode(generated_tokens, skip_special_tokens=False)
    
    return [{"generated_text": output_text}]

class ChatCompletionRequest(BaseModel):
    model: str = "default"
    messages: List[Dict[str, Any]]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False
    tools: Optional[List[Dict[str, Any]]] = None

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    # print(f"Completions Request:\n{json.dumps(request)}")
    model = ml_models["model"]
    tokenizer = ml_models["tokenizer"]
    device = ml_models["device"]
    
    # Format the prompt using the model's chat template
    prompt = tokenizer.apply_chat_template(
        request.messages,
        tokenize=False,
        tools=request.tools,
        add_generation_prompt=True
    )
    
    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    gen_kwargs = {
        "pad_token_id": tokenizer.pad_token_id,
        "max_new_tokens": request.max_tokens if request.max_tokens else 2048,
    }
    
    if request.temperature is not None and request.temperature > 0:
        gen_kwargs["do_sample"] = True
        gen_kwargs["temperature"] = request.temperature
        if request.top_p is not None:
            gen_kwargs["top_p"] = request.top_p
    else:
        gen_kwargs["do_sample"] = False
            
    with torch.inference_mode():
        outputs = model.generate(**inputs, **gen_kwargs)
        
    input_length = inputs['input_ids'].shape[1]
    generated_tokens = outputs[0][input_length:]
    output_text = tokenizer.decode(generated_tokens, skip_special_tokens=False)
    
    response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": output_text,
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": input_length,
            "completion_tokens": len(generated_tokens),
            "total_tokens": input_length + len(generated_tokens)
        }
    }
    return response