import re
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import sys


async def run_agent():
    # 1. Start the FastMCP server process
    server_params = StdioServerParameters(
        command="python",
        args=["actint/src/actint/tests/mcp/server.py"] # Path to your FastMCP server
    )

    model_name = "Qwen/Qwen3.5-9B"
    # model_name = "unsloth/Meta-Llama-3.1-8B-Instruct"

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 2. Ask the server what tools it has
            tools_response = await session.list_tools()

            print(f"Tool response:\n{tools_response}", file=sys.stderr)
            
            # Format these tools into a schema your LLM understands (Hugging Face / OpenAI format)
            llm_tools = []
            for tool in tools_response.tools:
                llm_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })
            
            # 3. Prepare the conversation but don't format the prompt until we load the tokenizer
            # system_prompt = f"You are a helpful assistant. You have access to the following tools:\n{json.dumps(llm_tools, indent=2)}\n\nIf you need to use a tool, reply ONLY with a JSON object in this format: {{\"name\": \"tool_name\", \"arguments\": {{\"arg1\": \"value\"}}}}. NEVER include ANY other text before or after the JSON object."
            system_prompt = f"You are a helpful assistant."
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "What is the weather in Logan, Utah?"}
            ]
            
            try:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                # All prints go to stderr because stdio is being used to communicate with the MCP server
                print(f"Using device: {device}", file=sys.stderr)

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
                print("✓ Model loaded successfully", file=sys.stderr)
            except Exception as e:
                print(f"✗ Error loading model: {e}", file=sys.stderr)
                raise
            try:
                # Format using apply_chat_template
                prompt = tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    tools=llm_tools,
                    add_generation_prompt=True
                )
                
                print(f"Formatted Prompt:\n{prompt}", file=sys.stderr)
                
                inputs = tokenizer(prompt, return_tensors="pt")
                model_device = next(model.parameters()).device
                inputs = {key: value.to(model_device) for key, value in inputs.items()}
                print("✓ Tokenization successful", file=sys.stderr)

                if tokenizer.pad_token_id is None:
                    tokenizer.pad_token = tokenizer.eos_token
                model.config.pad_token_id = tokenizer.pad_token_id
                
                # Generate response
                with torch.inference_mode():
                    outputs = model.generate(
                        inputs['input_ids'],
                        attention_mask=inputs['attention_mask'],
                        pad_token_id=tokenizer.pad_token_id,
                        max_new_tokens=2048,
                        temperature=0.7,
                        top_p=0.9,
                        do_sample=True
                    )
                print("✓ Generation successful", file=sys.stderr)
                
                # Decode and print response
                # model.generate returns the input tokens followed by the generated tokens.
                # We need to slice off the input tokens to get just the response.
                input_length = inputs['input_ids'].shape[1]
                generated_tokens = outputs[0][input_length:]
                llm_response_text = tokenizer.decode(generated_tokens, skip_special_tokens=False)
                
                print(f"\nResponse:\n{llm_response_text}", file=sys.stderr)
                print("\n✓ Script completed successfully", file=sys.stderr)
                
            except Exception as e:
                print(f"✗ Error during inference: {e}", file=sys.stderr)
                raise


            
            # Mocking the LLM response for this example:
            # llm_response_text = '{"name": "get_weather", "arguments": {"location": "Paris"}}'
            
            # 4. Execute the tool if the LLM asked for one
            # Find all <tool_call> blocks using regex
            tool_blocks = re.findall(r'<tool_call>(.*?)</tool_call>', llm_response_text, re.DOTALL)
            
            for block in tool_blocks:
                func_match = re.search(r'<function=([^>]+)>', block)
                if func_match:
                    func_name = func_match.group(1).strip()
                    
                    params = {}
                    param_matches = re.finditer(r'<parameter=([^>]+)>(.*?)</parameter>', block, re.DOTALL)
                    for p in param_matches:
                        params[p.group(1).strip()] = p.group(2).strip()
                        
                    call_data = {"name": func_name, "arguments": params}
                    
                    print(f"LLM requested tool: {call_data['name']}", file=sys.stderr)
                    
                    # Ask MCP to run it
                    result = await session.call_tool(
                        call_data["name"], 
                        arguments=call_data["arguments"]
                    )
                    
                    print(f"Tool Result: {result.content}", file=sys.stderr)
                
                # 5. Feed this result BACK to the LLM so it can answer the user
                # final_prompt = prompt + "\nTool output: " + str(result.content) + "\nNow answer the user."
                # -> Run LLM generation again to get the final conversational answer...

if __name__ == "__main__":
    asyncio.run(run_agent())