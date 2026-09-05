<img width="842" height="692" alt="langfude" src="https://github.com/user-attachments/assets/5fc742e0-1d29-4f80-aadc-438ff54f7b37" />
<img width="1226" height="575" alt="Screenshot 2026-09-05 150022" src="https://github.com/user-attachments/assets/63963f4c-c6e8-4ef9-909c-13f4234f57c1" />
<img width="1213" height="650" alt="Screenshot 2026-09-05 150205" src="https://github.com/user-attachments/assets/fade5ad8-f71a-4d94-9dc4-c83f908a4c0a" />
<img width="1228" height="512" alt="Screenshot 2026-09-05 150350" src="https://github.com/user-attachments/assets/2716ee31-9cb3-485c-8013-0b7be79fb4e6" />
<img width="1229" height="427" alt="Screenshot 2026-09-05 150555" src="https://github.com/user-attachments/assets/fe7144c9-420f-4a89-9938-77a4be1f29a6" />
<img width="857" height="647" alt="langfuse2" src="https://github.com/user-attachments/assets/40b16c94-446d-4b05-913e-14948c6c4975" />


# Agent Ticket Triage Pipeline

An AI-powered pipeline that automatically triages incoming support tickets, enriches them with customer context, retrieves relevant knowledge base articles, generates grounded responses, and either auto-responds or queues a draft for human review.

Built as a production-grade portfolio project demonstrating orchestration, RAG, guardrails, observability, and async processing — not a demo.

---

## What It Does

A customer submits a support ticket in Jira. The pipeline:

1. **Parses** the ticket to extract intent, product area, and key details (LLM)
2. **Enriches** with customer data from HubSpot CRM — name, company, plan tier, ticket history (API call)
3. **Retrieves** relevant help articles from a vector database using RAG (embedding search)
4. **Classifies** the ticket into one of three routes using deterministic rules (no LLM)
5. **Generates** a grounded response using only the retrieved docs as source (LLM)
6. **Checks** the response against guardrails — hallucination, PII, prompt injection
7. **Gates** the decision — auto-post only if all checks pass, otherwise queue for human review
8. **Posts** the response back to Jira as a comment

One-shot per ticket. Read + respond only — no account mutations, no refunds, no deletions.

---

## Architecture

```
Customer → Jira (webhook) → FastAPI → Redis Queue → Worker
                                                      ↓
                                    Parse → Enrich → Retrieve → Classify
                                                                   ↓
                                                              ┌────┴────┐
                                                         AUTO/REVIEW  ESCALATE
                                                              ↓         ↓
                                                          Generate    Post
                                                              ↓      (context only)
                                                           Gate
                                                              ↓
                                                            Post
                                                              ↓
                                                         Log (Langfuse)
```

### What Uses the LLM vs What Doesn't

| Node     | LLM? | What Does the Work                     |
|----------|-------|----------------------------------------|
| Parse    | Yes   | Intent extraction from free-text       |
| Enrich   | No    | HubSpot REST API call                  |
| Retrieve | No    | Embedding model + Chroma vector search |
| Classify | No    | Deterministic rules table              |
| Generate | Yes   | Response drafting with structured output|
| Gate     | No    | If/else decision logic                 |
| Post     | No    | Jira REST API call                     |

Only 2 of 7 nodes use the LLM. Everything that can be deterministic is deterministic.

### Routing Logic

| Route         | When                                              | What Happens                                    |
|---------------|---------------------------------------------------|------------------------------------------------|
| AUTO_RESPOND  | Simple question + docs found + high confidence    | Response posted directly to Jira               |
| HUMAN_REVIEW  | Billing dispute, VIP customer, low confidence     | Draft posted as internal note for agent review |
| ESCALATE      | Account deletion, legal threat, unknown intent    | Context posted, no response generated          |

---

## Tech Stack

| Component      | Tool                      | Cost   |
|----------------|---------------------------|--------|
| Orchestrator   | LangGraph                 | Free   |
| LLM            | Ollama (qwen2.5-coder:7b) | Free   |
| Vector DB      | Chroma (local)            | Free   |
| Embeddings     | all-MiniLM-L6-v2          | Free   |
| Helpdesk       | Jira Cloud Free           | Free   |
| CRM            | HubSpot Free              | Free   |
| Queue          | Redis (Docker)            | Free   |
| Observability  | Langfuse Cloud            | Free   |
| Web Framework  | FastAPI                   | Free   |
| Tunnel         | localtunnel               | Free   |

---

## Project Structure

```
agent-ticket-triage-pipeline/
├── app/
│   ├── main.py                 # FastAPI webhook receiver
│   ├── orchestrator.py         # LangGraph state machine — wires all nodes
│   ├── config.py               # Central config — all env vars, thresholds
│   ├── queue.py                # Redis queue — push/pull jobs
│   ├── worker.py               # Background worker — pulls from Redis, runs pipeline
│   ├── observability.py        # Langfuse tracing
│   │
│   ├── nodes/                  # Each pipeline step is an independent node
│   │   ├── parse.py            # Extract intent from ticket (LLM)
│   │   ├── enrich.py           # Fetch customer data from HubSpot
│   │   ├── retrieve.py         # RAG search over Chroma vector DB
│   │   ├── classify.py         # Rules-based routing
│   │   ├── generate.py         # Draft response + guardrail checks (LLM)
│   │   ├── gate.py             # Final decision: auto-post vs review
│   │   └── post.py             # Post comment to Jira
│   │
│   ├── guardrails/             # Safety checks
│   │   ├── input_sanitizer.py  # Prompt injection detection
│   │   ├── output_validator.py # Hallucination check
│   │   └── pii_filter.py       # PII redaction
│   │
│   ├── models/
│   │   └── schemas.py          # All Pydantic models
│   │
│   └── config/
│       ├── routing_rules.yaml  # Classification rules
│       └── prompts.yaml        # LLM prompt templates
│
├── knowledge_base/
│   └── docs/                   # CloudDash help articles (RAG source)
│
├── scripts/
│   ├── seed_jira.py            # Generate fake tickets → push to Jira
│   ├── seed_hubspot.py         # Generate fake customers → push to HubSpot
│   ├── seed_knowledge_base.py  # Generate help articles
│   └── build_vectorstore.py    # Chunk + embed docs → load into Chroma
│
├── eval/
│   ├── golden_dataset.json     # Test tickets with correct responses
│   ├── run_eval.py             # Score pipeline against golden set
│   └── metrics.py              # Accuracy, hallucination rate
│
├── tests/                      # Unit tests per node
├── .env.example                # API keys template
├── .gitignore
├── requirements.txt
├── docker-compose.yml          # Redis
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.11+
- Docker (for Redis)
- Ollama
- Node.js (for localtunnel)

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/agent-ticket-triage-pipeline.git
cd agent-ticket-triage-pipeline
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
cp .env.example .env
```

Fill in your `.env`:

```
# LLM
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5-coder:7b
OLLAMA_BASE_URL=http://localhost:11434

# Jira
JIRA_BASE_URL=https://yoursite.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-token
JIRA_PROJECT_KEY=KAN

# HubSpot
HUBSPOT_ACCESS_TOKEN=your-hubspot-token

# Langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-your-key
LANGFUSE_SECRET_KEY=sk-lf-your-key
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. Start Services

```bash
# Start Ollama
ollama serve

# Pull the model
ollama pull qwen2.5-coder:7b

# Start Redis
docker run -d --name redis -p 6379:6379 redis
```

### 4. Seed Data

```bash
# Generate help articles
python -m scripts.seed_knowledge_base

# Build vector store
python -m scripts.build_vectorstore

# Push fake customers to HubSpot
python -m scripts.seed_hubspot

# Push fake tickets to Jira
python -m scripts.seed_jira
```

### 5. Run the Pipeline

Four terminals:

```bash
# Terminal 1: LLM
ollama serve

# Terminal 2: API server
uvicorn app.main:app --reload --port 8000

# Terminal 3: Tunnel (exposes localhost to Jira webhook)
npx localtunnel --port 8000 --subdomain tickettriage

# Terminal 4: Background worker
python -m app.worker
```

### 6. Configure Jira Webhook

Go to `https://yoursite.atlassian.net/plugins/servlet/webhooks`

- **URL:** `https://tickettriage.loca.lt/webhook/jira`
- **Events:** Issue → created
- **Save**

### 7. Test

Create a ticket in Jira:
- **Summary:** `I was charged twice this month`
- **Description:** `Customer: priya.sharma@acmecorp.com` followed by `I checked my bank statement and I see two charges of $49.99 from CloudDash for August.`
- **Priority:** High

Watch Terminal 4 for pipeline logs. Check Langfuse for the trace. Check the Jira ticket for the AI comment.

---

## Guardrails

### Input Sanitizer (Parse Node)
Detects prompt injection patterns in ticket descriptions — "ignore previous instructions", "you are now", etc. If detected, ticket routes to ESCALATE.

### Hallucination Check (Generate Node)
Verifies every claim in the generated response traces back to a retrieved doc chunk. Prices or details not found in source docs are flagged.

### PII Filter (Generate Node)
Scans the response for credit card numbers, SSNs, and long account IDs before posting. If found, response is flagged for human review.

### Prompt Injection Detection (Generate Node)
Checks if the response contains action language ("refund approved", "account deleted") that indicates the LLM was hijacked by injected instructions in the ticket body.

If any guardrail fails, Gate overrides to QUEUED_FOR_REVIEW — never auto-posts a flagged response.

---

## Observability

Every pipeline run is traced in Langfuse with nested spans per node:

- **Parse:** input ticket, output intent + confidence
- **Enrich:** input email, output customer tier + history
- **Retrieve:** input query, output chunks found + sources
- **Classify:** input signals, output route + reason
- **Generate:** input context, output response + guardrail results
- **Gate:** output decision
- **Post:** output posted status + comment ID

Each trace includes: total latency, per-node latencies, LLM token usage, and guardrail pass/fail. Any run can be fully replayed from the Langfuse dashboard.

---

## Failure Modes & Fallbacks

| Failure                     | Fallback                                              |
|-----------------------------|-------------------------------------------------------|
| Jira webhook fires twice    | Idempotency check on ticket_id in Redis               |
| HubSpot API down            | enrichment_status: failed, pipeline continues          |
| No relevant docs found      | retrieval_confident: false → ESCALATE                 |
| LLM returns invalid JSON    | Retry once → still fails → intent: unknown → ESCALATE |
| LLM hallucinates            | Hallucination guardrail catches → HUMAN_REVIEW        |
| Jira comment API fails      | Retry 3x with exponential backoff                     |
| LLM times out               | Fallback response + ESCALATE                          |
| Prompt injection in ticket  | Input sanitizer catches → ESCALATE                    |
| Redis down                  | Worker retries connection on timeout                   |

---

## Design Decisions

**Why only 2 of 7 nodes use the LLM:**
LLMs are expensive, slow, and non-deterministic. Everything that CAN be deterministic IS deterministic. Routing decisions are rules, not vibes.

**Why one-shot, not conversational:**
Conversational AI is dramatically harder — context tracking, turn management, and failure modes multiply per turn. One-shot handles 60-70% of support tickets. Conversation is a v2 feature.

**Why read + respond only:**
The pipeline never processes refunds, deletes accounts, or modifies subscriptions. Worst case if the AI is wrong: a customer gets a slightly off response. Nobody loses money.

**Why Gate exists separately from Classify:**
Classify is optimistic ("this should be auto-respondable"). Gate is the safety net ("was the actual output good enough?"). Both must agree for auto-post.

**Why Redis queue:**
Jira webhooks timeout after ~10 seconds. The pipeline takes 30-60 seconds. The queue decouples the webhook (respond instantly) from processing (run in background).

---

## Production Deployment

This project runs locally. Here's what the production deployment would look like:

```
LOCAL (what I built)              PRODUCTION (what I'd deploy)
──────────────────────            ────────────────────────────
FastAPI on localhost              AWS Lambda / Cloud Run
localtunnel                       API Gateway with fixed URL + auth
Chroma in-process                 Qdrant Cloud / self-hosted
Redis in Docker                   AWS Elasticache / managed Redis
Ollama local LLM                  Claude API / GPT-4o
.env file                         AWS Secrets Manager / Vault
Langfuse Cloud                    Langfuse self-hosted / Datadog
pytest                            GitHub Actions CI eval gate
Manual trigger                    Jira webhook with signature verification
```

### Additional Production Considerations

- **Webhook signature verification:** Validate incoming webhooks are actually from Jira, not spoofed
- **PII/data boundary:** Customer ticket content crosses network boundary to LLM — requires DPA with LLM provider, or self-hosted model
- **Model fallback:** If primary LLM is down, fall back to secondary model or degrade gracefully
- **Canary rollout:** Enable for one Jira project first, expand after accuracy is proven
- **Feature flags:** Kill switch to disable auto-responses per category without code deploy
- **Slack routing:** Escalated and human-review tickets should route to Slack/Teams, not post to Jira as internal notes

---

## Future Scope

- **Slack integration:** Route escalated/review tickets to a Slack channel instead of Jira internal notes
- **Eval pipeline:** Golden dataset of 100 tickets with correct responses, CI gate that blocks PRs with accuracy regressions
- **Better embedding model:** Replace all-MiniLM-L6-v2 with a larger model for improved retrieval accuracy
- **Conversation support:** Handle follow-up replies on the same ticket with context from previous responses
- **Write actions:** v2 could add low-risk write operations (auto-categorize tickets) after accuracy is proven
- **Cost tracking:** Per-ticket cost tracking in Langfuse for budget monitoring

---

## License

MIT
