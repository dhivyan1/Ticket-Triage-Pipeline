import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")


def get_llm():
    if LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0,
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")


def test_connection():
    print(f"Provider: {LLM_PROVIDER}")

    # 1. Initialize
    try:
        llm = get_llm()
        print("LLM initialized successfully")
    except Exception as e:
        print(f"Failed to initialize LLM: {e}")
        return

    # 2. Simple text response
    try:
        response = llm.invoke("Say 'hello' and nothing else.")
        print(f"Simple test passed: {response.content}")
    except Exception as e:
        print(f"Simple test failed: {e}")
        return

    # 3. Structured output (critical for ITRE — your pipeline depends on this)
    try:
        from pydantic import BaseModel, Field

        class TicketParse(BaseModel):
            intent: str = Field(description="The customer's intent")
            product_area: str = Field(description="Which product area this relates to")
            urgency: str = Field(description="low, medium, or high")

        structured_llm = llm.with_structured_output(TicketParse)

        result = structured_llm.invoke(
            "Customer ticket: 'I was charged twice on my June invoice, please fix this ASAP'"
        )
        print(f"Structured output test passed:")
        print(f"  intent: {result.intent}")
        print(f"  product_area: {result.product_area}")
        print(f"  urgency: {result.urgency}")
    except Exception as e:
        print(f"Structured output test failed: {e}")
        print("This is critical — ITRE needs structured output to work.")
        return

    print("\nAll tests passed. LLM is ready for ITRE.")


if __name__ == "__main__":
    test_connection()


