"""
LLM Query module for AIS vessel intelligence.

Uses RAG pipeline to retrieve relevant vessel data, then generates
natural language responses using a local LLM. Integrates location
context tools to provide geographic context for vessel positions.
"""

from pathlib import Path
from typing import Optional

from actint.data_processing.rag import RAGPipeline, create_rag_pipeline
from actint.tools.lat_lon_context import (
    get_location_context,
    get_location_context_string,
    get_distance_between,
    TOOL_DEFINITIONS,
)


class VesselQueryLLM:
    """
    Query interface that combines RAG retrieval with LLM generation.
    
    For questions like "where is USS KIDD right now?", this:
    1. Uses RAG to retrieve relevant vessel/position data
    2. Enriches position data with geographic context (maritime region, nearest port, etc.)
    3. Formats a prompt with the retrieved context
    4. Generates a natural language response
    """
    
    def __init__(
        self,
        rag_pipeline: Optional[RAGPipeline] = None,
        model_name: str = "mistralai/Mistral-7B-v0.1",
        enrich_with_location_context: bool = True,
    ):
        self.rag = rag_pipeline or create_rag_pipeline()
        self.model_name = model_name
        self.enrich_with_location_context = enrich_with_location_context
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
    
    def _enrich_with_location_context(self, rag_result: dict) -> str:
        """
        Enrich RAG results with geographic context for each vessel position.
        
        Args:
            rag_result: Result from RAG pipeline with vessel matches
            
        Returns:
            Enriched context string with location information
        """
        enriched_parts = []

        match = rag_result.get("matches", [])[0] if rag_result.get("matches") else None
        
        vessel_name = match.get("info", {}).get("name", "Unknown Vessel")
        position = match.get("position")
        
        enriched_parts.append(f"=== {vessel_name} ===")
        
        # Add vessel info
        info = match.get("info", {})
        info_parts = []
        if info.get("type") and info.get("pennant"):
            info_parts.append(f"Designation: {info['type']}-{info['pennant']}")
        if info.get("class"):
            info_parts.append(f"Class: {info['class']}")
        if info.get("fleet"):
            info_parts.append(f"Fleet: {info['fleet']}")
        if info.get("home_base"):
            info_parts.append(f"Home Port: {info['home_base']}")
        
        if info_parts:
            enriched_parts.append("Vessel Info: " + ". ".join(info_parts))
        
        # Add position with location context
        if position:
            lat = position.get("lat")
            lon = position.get("lon")
            timestamp = position.get("timestamp", "Unknown")
            sog = position.get("sog")
            cog = position.get("cog")
            
            pos_parts = [f"Coordinates: {lat:.5f}°N, {abs(lon):.5f}°{'W' if lon < 0 else 'E'}"]
            pos_parts.append(f"Last Report: {timestamp}")
            
            if sog is not None:
                pos_parts.append(f"Speed: {sog:.1f} knots")
            if cog is not None:
                pos_parts.append(f"Course: {cog:.1f}°")
            
            enriched_parts.append("Position: " + ". ".join(pos_parts))
            
            # Get geographic context using location tool
            if lat is not None and lon is not None:
                loc_context = get_location_context(lat, lon)
                
                context_parts = []
                if loc_context.maritime_region:
                    context_parts.append(f"Maritime Region: {loc_context.maritime_region}")
                if loc_context.nearest_port and loc_context.distance_to_port_nm:
                    context_parts.append(f"Nearest Port: {loc_context.nearest_port} ({loc_context.distance_to_port_nm:.0f} nm)")
                if loc_context.position_description:
                    context_parts.append(f"Location: {loc_context.position_description}")
                if loc_context.nearest_waterway and loc_context.distance_to_waterway_nm:
                    if loc_context.distance_to_waterway_nm < 500:
                        context_parts.append(f"Near Waterway: {loc_context.nearest_waterway} ({loc_context.distance_to_waterway_nm:.0f} nm)")
                
                if context_parts:
                    enriched_parts.append("Geographic Context: " + ". ".join(context_parts))
        else:
            enriched_parts.append("Position: No recent position data available")
        
        enriched_parts.append("")  # Blank line between vessels
        
        return "\n".join(enriched_parts)
    
    def build_prompt(self, query: str, context: str) -> str:
        """
        Build a prompt for the LLM using retrieved context.
        """
        prompt = f"""You are a maritime intelligence assistant. Answer the user's question based on the provided vessel data. Use the geographic context to provide informative answers about vessel locations. Only provide the answer to the question, without repeating the question or the context.

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
        
        # Enrich with geographic context if enabled
        if self.enrich_with_location_context and rag_result.get("matches"):
            enriched_context = self._enrich_with_location_context(rag_result)
        else:
            enriched_context = rag_result["context"]
        
        result = {
            "question": question,
            "vessel_extracted": rag_result["vessel_name_extracted"],
            "matches_found": len(rag_result["matches"]),
            "context": enriched_context,
            "matches": rag_result["matches"],
        }
        
        if not use_llm:
            result["answer"] = enriched_context
            return result
        
        # Generate LLM response
        self._load_model()
        
        prompt = self.build_prompt(question, enriched_context)
        
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
    import argparse

    parser = argparse.ArgumentParser(description="AIS Vessel Query System with RAG and LLM")
    parser.add_argument("--with-llm", action="store_true", help="Generate answer using LLM (default: context only)")
    parser.add_argument("--no-location-context", action="store_true", help="Disable geographic context enrichment")
    parser.add_argument("--model", type=str, default="mistralai/Mistral-7B-v0.1", help="LLM model name")
    parser.add_argument("--query", type=str, help="Question to ask (overrides test queries)")
    parser.add_argument("--test", action="store_true", help="Run default test queries")
    args = parser.parse_args()

    test_queries = [
        "Where is USS KIDD right now?",
        "What is the position of USS MONTGOMERY?",
    ]

    if args.query:
        test_queries = [args.query]
    elif not args.test:
        test_queries = [input("Enter your vessel query: ")]

    print("=" * 60)
    print("Vessel Query System")
    print("=" * 60)

    # Context-only retrieval
    if not args.with_llm:
        print("\n--- Testing RAG Context Retrieval (no LLM) ---\n")
        for query in test_queries:
            print(f"Query: {query}")
            print("-" * 40)
            rag = create_rag_pipeline()
            context = rag.retrieve_context(query)
            print(context)
            print()
    else:
        print("\n--- Testing with LLM Generation ---\n")
        llm = VesselQueryLLM(model_name=args.model, enrich_with_location_context=not args.no_location_context)
        for query in test_queries:
            print(f"Query: {query}")
            print("-" * 40)
            result = llm.query(query)
            print("Context Used for Answer:")
            print(result["context"])
            print("\nGenerated Answer:")
            print("BEGIN ANSWER\n" + "=" * 60)
            print(f"Answer: {result['answer']}")
            print("END OF ANSWER \n" + "=" * 60 + "\n")
            print()
