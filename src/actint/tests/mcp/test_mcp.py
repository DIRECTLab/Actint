import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

print("Loading Qwen model and tokenizer...")
try:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2-7B-Instruct")

    if device == "cuda":
        model = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen2-7B",
            dtype=torch.float16,
            device_map="auto"
        )
    else:
        model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2-7B-Instruct")

    model.eval()
    print("✓ Model loaded successfully")
except Exception as e:
    print(f"✗ Error loading model: {e}")
    raise

# Make a simple request
prompt = "What is the capital of France?"
print(f"\nPrompt: {prompt}")

try:
    inputs = tokenizer(prompt, return_tensors="pt")
    model_device = next(model.parameters()).device
    inputs = {key: value.to(model_device) for key, value in inputs.items()}
    print("✓ Tokenization successful")

    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model.config.pad_token_id = tokenizer.pad_token_id
    
    # Generate response
    with torch.inference_mode():
        outputs = model.generate(
            inputs['input_ids'],
            attention_mask=inputs['attention_mask'],
            pad_token_id=tokenizer.pad_token_id,
            max_new_tokens=100,
            temperature=0.7,
            top_p=0.9,
            do_sample=True
        )
    print("✓ Generation successful")
    
    # Decode and print response
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"\nResponse:\n{response}")
    print("\n✓ Script completed successfully")
    
except Exception as e:
    print(f"✗ Error during inference: {e}")
    raise


