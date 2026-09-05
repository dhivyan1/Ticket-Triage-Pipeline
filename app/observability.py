"""
OBSERVABILITY MODULE (Langfuse v4)

Uses the new v4 API: get_client() + start_as_current_observation() context managers.

Every pipeline run creates a root span with nested child spans for each node.
View traces at: https://cloud.langfuse.com

Usage:
  from app.observability import get_langfuse
  langfuse = get_langfuse()
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Force env vars from config if not set
from app.config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST

os.environ.setdefault("LANGFUSE_PUBLIC_KEY", LANGFUSE_PUBLIC_KEY)
os.environ.setdefault("LANGFUSE_SECRET_KEY", LANGFUSE_SECRET_KEY)
os.environ.setdefault("LANGFUSE_HOST", LANGFUSE_HOST)

from langfuse import get_client



def get_langfuse():
    """Get Langfuse client. Uses environment variables for auth:
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
    """
    return get_client()


# ─── Standalone test ──────────────────────────────────────

if __name__ == "__main__":
    print("Testing Langfuse v4 connection...\n")

    langfuse = get_langfuse()

    # Create a root span (this is the "trace" in v4)
    with langfuse.start_as_current_observation(
        as_type="span",
        name="pipeline-test",
    ) as root:
        root.update(
            input={"ticket": "TEST-001", "subject": "Test trace"},
            metadata={"test": True},
        )

        # Nested span: parse
        with langfuse.start_as_current_observation(
            as_type="span",
            name="parse",
        ) as parse_span:
            parse_span.update(
                input={"subject": "Test ticket"},
                output={"intent": "how_to", "confidence": 0.92},
            )

        # Nested span: enrich
        with langfuse.start_as_current_observation(
            as_type="span",
            name="enrich",
        ) as enrich_span:
            enrich_span.update(
                input={"email": "test@test.com"},
                output={"customer": "Test User", "tier": "pro"},
            )

        # Nested generation: LLM call
        with langfuse.start_as_current_observation(
            as_type="generation",
            name="parse-llm",
            model="qwen2.5:7b",
        ) as gen:
            gen.update(
                input="Extract intent from: Test ticket",
                output='{"intent": "how_to"}',
            )

        root.update(output={"decision": "AUTO_POST", "posted": True})

    langfuse.flush()
    print("Test trace sent to Langfuse!")
    print("Check: https://cloud.langfuse.com → your project → Traces")