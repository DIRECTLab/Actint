# Load model directly
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

print("Loading Mistral model and tokenizer...")
try:
    tokenizer = AutoTokenizer.from_pretrained("mistralai/Mistral-7B-v0.1")
    model = AutoModelForCausalLM.from_pretrained("mistralai/Mistral-7B-v0.1")
    print("✓ Model loaded successfully")
except Exception as e:
    print(f"✗ Error loading model: {e}")
    raise

# Make a simple request
prompt = "What is the capital of France?"
print(f"\nPrompt: {prompt}")

try:
    inputs = tokenizer(prompt, return_tensors="pt")
    print("✓ Tokenization successful")
    
    # Generate response
    outputs = model.generate(
        inputs['input_ids'],
        max_length=100,
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


