"""
Pydantic schemas for the Agent Ticket Triage Pipeline.

Every node reads from and writes to PipelineState.
Each section maps to one node's output.
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


# ─── Enums ───────────────────────────────────────────────

class Intent(str, Enum):
    """Ticket intent categories. Extend as needed."""
    HOW_TO = "how_to"
    FEATURE_QUESTION = "feature_question"
    BILLING_FAQ = "billing_faq"
    BILLING_DISPUTE = "billing_dispute"
    REFUND_REQUEST = "refund_request"
    BUG_REPORT_KNOWN = "bug_report_known"
    BUG_REPORT_UNKNOWN = "bug_report_unknown"
    ACCOUNT_DELETION = "account_deletion"
    LEGAL_THREAT = "legal_threat"
    UNKNOWN = "unknown"


class AccountTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    UNKNOWN = "unknown"


class Route(str, Enum):
    AUTO_RESPOND = "AUTO_RESPOND"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    ESCALATE = "ESCALATE"


class GateDecision(str, Enum):
    AUTO_POST = "AUTO_POST"
    QUEUED_FOR_REVIEW = "QUEUED_FOR_REVIEW"
    ESCALATED = "ESCALATED"


class EnrichmentStatus(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    FAILED = "failed"


# ─── Node Output Schemas ─────────────────────────────────

class TicketInput(BaseModel):
    """Raw ticket data from Jira webhook. Set once at trigger, never modified."""
    ticket_id: str
    ticket_key: str                           # e.g. "SUP-1234"
    raw_subject: str
    raw_description: str
    reporter_email: str
    priority: str                             # from Jira field: "Low", "Medium", "High", "Critical"
    labels: list[str] = Field(default_factory=list)
    triggered_at: datetime = Field(default_factory=datetime.utcnow)


class ParsedTicket(BaseModel):
    """Output of the PARSE node. LLM extracts these from the ticket text."""
    intent: Intent
    sub_intent: str                           # e.g. "charged_twice", "export_pdf"
    product_area: str                         # e.g. "billing", "export", "authentication"
    key_details: str                          # extracted specifics from description
    parse_confidence: float = Field(ge=0, le=1)


class CustomerInfo(BaseModel):
    """Output of the ENRICH node. Fetched from HubSpot CRM."""
    customer_name: str = "Unknown"
    company: str = "Unknown"
    account_tier: AccountTier = AccountTier.UNKNOWN
    subscription_status: str = "unknown"      # "active", "churned", "trial"
    past_ticket_count: int = 0
    signup_date: Optional[str] = None
    enrichment_status: EnrichmentStatus = EnrichmentStatus.FAILED


class RetrievedChunk(BaseModel):
    """A single document chunk returned from vector search."""
    source: str
    content: str
    score: float = Field(ge=0)


class RetrievalResult(BaseModel):
    """Output of the RETRIEVE node. RAG search results from Chroma."""
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    retrieval_confident: bool = False         # any chunk above threshold?
    query_used: str = ""                      # what search query was built


class ClassifyResult(BaseModel):
    """Output of the CLASSIFY node. Deterministic rules, no LLM."""
    route: Route
    route_reason: str                         # human-readable: "billing_dispute requires human sign-off"


class GeneratedResponse(BaseModel):
    """Output of the GENERATE node. LLM drafts this with structured output."""
    response_text: str
    sources_used: list[str] = Field(default_factory=list)  # which doc chunks were cited
    confidence: float = Field(ge=0, le=1)
    suggested_category: str = ""              # for Jira labeling
    needs_human_review: bool = False          # flipped true by guardrails


class GuardrailResult(BaseModel):
    """Output of guardrail checks run on the generated response."""
    schema_valid: bool = True
    hallucination_detected: bool = False
    pii_detected: bool = False
    injection_detected: bool = False
    guardrail_notes: str = ""                 # explanation if any check failed

    @property
    def all_passed(self) -> bool:
        return (
            self.schema_valid
            and not self.hallucination_detected
            and not self.pii_detected
            and not self.injection_detected
        )


class GateResult(BaseModel):
    """Output of the GATE node. Final decision before posting."""
    decision: GateDecision
    reviewer: Optional[str] = None            # who it was routed to (if human review)


class PostResult(BaseModel):
    """Output of the POST node. Jira API response."""
    posted: bool = False
    jira_comment_id: Optional[str] = None
    post_error: Optional[str] = None


class PipelineMeta(BaseModel):
    """Output of the LOG node. Observability data."""
    total_latency_ms: int = 0
    tool_latencies: dict[str, int] = Field(default_factory=dict)    # per-node timing in ms
    llm_tokens_used: dict[str, dict] = Field(default_factory=dict)  # {"parse": {"input": 420, "output": 85}}
    cost_usd: float = 0.0
    trace_id: str = ""


# ─── Full Pipeline State ─────────────────────────────────

class PipelineState(BaseModel):
    """
    The single state object that flows through every LangGraph node.
    Each node reads what it needs and writes its section.
    No node modifies another node's output.
    """
    # Set at trigger
    input: TicketInput

    # Written by each node (Optional because they start empty)
    parsed: Optional[ParsedTicket] = None
    customer: Optional[CustomerInfo] = None
    retrieval: Optional[RetrievalResult] = None
    classification: Optional[ClassifyResult] = None
    generation: Optional[GeneratedResponse] = None
    guardrails: Optional[GuardrailResult] = None
    gate: Optional[GateResult] = None
    post: Optional[PostResult] = None
    meta: Optional[PipelineMeta] = Field(default_factory=PipelineMeta)