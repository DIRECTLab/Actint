"""
LLM Query module for AIS vessel intelligence.

Uses RAG pipeline to retrieve relevant vessel data, then generates
natural language responses using a local LLM.
"""

from pathlib import Path
from typing import Optional

from actint.data_processing.rag import RAGPipeline, create_rag_pipeline


class VesselQueryLLM:
    """
    Query interface that combines RAG retrieval with LLM generation.
    
    For questions like "where is USS KIDD right now?", this:
    1. Uses RAG to retrieve relevant vessel/position data
    2. Formats a prompt with the retrieved context
    3. Generates a natural language response
    """
    
    def __init__(
        self,
        rag_pipeline: Optional[RAGPipeline] = None,
        model_name: str = "mistralai/Mistral-7B-v0.1",
    ):
        self.rag = rag_pipeline or create_rag_pipeline()
        self.model_name = model_name
        self._model = None
        self._tokenizer = None
    
    def _load_model(self):
        """Lazy-load the LLM model and tokenizer."""
        if self._model is None:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            import torch
            
            print(f"Loading model: {self.model_name}...")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
            )
            print("Model loaded.")
    
    def build_prompt(self, query: str, context: str) -> str:
        """
        Build a prompt for the LLM using retrieved context.
        """
        prompt = f"""You are a maritime intelligence assistant. Answer the user's question based on the provided vessel data.

### Vessel Data:
{context}

### Question:
{query}

### Answer:
"""
        return prompt
    
    def query(
        self,
        question: str,
        use_llm: bool = True,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
    ) -> dict:
        """
        Answer a question about vessel locations.
        
        Args:
            question: Natural language question (e.g., "Where is USS KIDD?")
            use_llm: If True, generate LLM response. If False, return raw context.
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Dict with query info, context, and generated answer
        """
        # Retrieve context using RAG
        rag_result = self.rag.answer_location_query(question)
        
        result = {
            "question": question,
            "vessel_extracted": rag_result["vessel_name_extracted"],
            "matches_found": len(rag_result["matches"]),
            "context": rag_result["context"],
            "matches": rag_result["matches"],
        }
        
        if not use_llm:
            result["answer"] = rag_result["context"]
            return result
        
        # Generate LLM response
        self._load_model()
        
        prompt = self.build_prompt(question, rag_result["context"])
        
        inputs = self._tokenizer(prompt, return_tensors="pt")
        if hasattr(self._model, "device"):
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
        
        outputs = self._model.generate(
            inputs["input_ids"],
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            top_p=0.9,
            pad_token_id=self._tokenizer.eos_token_id,
        )
        
        # Decode only the new tokens (not the prompt)
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        answer = self._tokenizer.decode(generated, skip_special_tokens=True)
        
        result["answer"] = answer.strip()
        result["prompt"] = prompt
        
        return result
    
    def query_simple(self, question: str) -> str:
        """
        Simple query that returns just the answer string.
        """
        result = self.query(question, use_llm=True)
        return result.get("answer", "Unable to answer the question.")


def create_query_llm(
    model_name: str = "mistralai/Mistral-7B-v0.1",
) -> VesselQueryLLM:
    """Factory function to create a VesselQueryLLM instance."""
    return VesselQueryLLM(model_name=model_name)


# Quick context-only retrieval (no LLM needed)
def get_vessel_context(question: str) -> str:
    """
    Quick function to get RAG context without LLM generation.
    Useful for testing or when you want to use a different LLM.
    """
    rag = create_rag_pipeline()
    return rag.retrieve_context(question)


if __name__ == "__main__":
    import sys
    
    # Test queries
    test_queries = [
        "Where is USS KIDD right now?",
        "What is the position of USS MONTGOMERY?",
    ]
    
    if len(sys.argv) > 1:
        test_queries = [" ".join(sys.argv[1:])]
    
    print("=" * 60)
    print("Vessel Query System")
    print("=" * 60)
    
    # First, test with just RAG (no LLM)
    print("\n--- Testing RAG Context Retrieval (no LLM) ---\n")
    
    for query in test_queries:
        print(f"Query: {query}")
        print("-" * 40)
        context = get_vessel_context(query)
        print(context)
        print()
    
    # Optionally test with LLM (requires model download)
    if "--with-llm" in sys.argv:
        print("\n--- Testing with LLM Generation ---\n")
        
        llm = create_query_llm()
        
        for query in test_queries:
            print(f"Query: {query}")
            print("-" * 40)
            result = llm.query(query)
            print(f"Answer: {result['answer']}")
            print()
