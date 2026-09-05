"""
PIPELINE METRICS DASHBOARD

Run:
  streamlit run dashboard.py
"""

import json
import os
import streamlit as st
import pandas as pd

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "pipeline.jsonl")
FEEDBACK_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "feedback.jsonl")
MISSING_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "missing_articles.jsonl")


def load_jsonl(filepath) -> list[dict]:
    if not os.path.exists(filepath):
        return []
    entries = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def main():
    st.set_page_config(
        page_title="Agent Ticket Triage Pipeline",
        page_icon="🎫",
        layout="wide",
    )

    st.title("🎫 Agent Ticket Triage Pipeline — Dashboard")
    st.caption("Real-time metrics from pipeline runs")

    # Load data
    pipeline_logs = load_jsonl(LOG_FILE)
    feedback_logs = load_jsonl(FEEDBACK_FILE)
    missing_logs = load_jsonl(MISSING_FILE)

    df = pd.DataFrame(pipeline_logs) if pipeline_logs else pd.DataFrame()
    fb_df = pd.DataFrame(feedback_logs) if feedback_logs else pd.DataFrame()
    missing_df = pd.DataFrame(missing_logs) if missing_logs else pd.DataFrame()

    if df.empty:
        st.warning("No pipeline runs yet. Create tickets in Jira to generate data.")
        return

    # ─── Top-level metrics ────────────────────────────────

    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)

    total_runs = len(df)
    auto_posted = len(df[df["decision"] == "AUTO_POST"])
    queued = len(df[df["decision"] == "QUEUED_FOR_REVIEW"])
    escalated = len(df[df["decision"] == "ESCALATED"])
    auto_rate = (auto_posted / total_runs * 100) if total_runs > 0 else 0

    col1.metric("Total Runs", total_runs)
    col2.metric("Auto-Posted", auto_posted)
    col3.metric("Queued for Review", queued)
    col4.metric("Escalated", escalated)
    col5.metric("Auto-Resolve Rate", f"{auto_rate:.1f}%")

    # ─── Latency metrics ─────────────────────────────────

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    avg_latency = df["total_latency_ms"].mean() / 1000
    p95_latency = df["total_latency_ms"].quantile(0.95) / 1000
    min_latency = df["total_latency_ms"].min() / 1000

    col1.metric("Avg Latency", f"{avg_latency:.1f}s")
    col2.metric("P95 Latency", f"{p95_latency:.1f}s")
    col3.metric("Fastest Run", f"{min_latency:.1f}s")

    # ─── Route distribution ──────────────────────────────

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Route Distribution")
        route_counts = df["route"].value_counts()
        st.bar_chart(route_counts)

    with col2:
        st.subheader("Gate Decision Distribution")
        decision_counts = df["decision"].value_counts()
        st.bar_chart(decision_counts)

    # ─── Intent breakdown ────────────────────────────────

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Tickets by Intent")
        intent_counts = df["intent"].value_counts()
        st.bar_chart(intent_counts)

    with col2:
        st.subheader("Tickets by Account Tier")
        tier_counts = df["account_tier"].value_counts()
        st.bar_chart(tier_counts)

    # ─── Guardrail stats ─────────────────────────────────

    st.markdown("---")
    st.subheader("Guardrail Results")

    col1, col2, col3, col4 = st.columns(4)

    guardrail_pass_rate = (df["guardrails_passed"].sum() / total_runs * 100) if total_runs > 0 else 0
    hallucination_count = df["hallucination_detected"].sum()
    pii_count = df["pii_detected"].sum()
    injection_count = df["injection_detected"].sum()

    col1.metric("Pass Rate", f"{guardrail_pass_rate:.1f}%")
    col2.metric("Hallucinations", int(hallucination_count))
    col3.metric("PII Detections", int(pii_count))
    col4.metric("Injections", int(injection_count))

    # ─── Per-node latency ────────────────────────────────

    st.markdown("---")
    st.subheader("Average Latency by Node")

    node_names = ["parse", "enrich", "retrieve", "classify", "generate", "gate", "post"]
    node_latencies = {}

    for node in node_names:
        latencies = []
        for _, row in df.iterrows():
            tl = row.get("tool_latencies", {})
            if isinstance(tl, dict) and node in tl:
                latencies.append(tl[node])
        if latencies:
            node_latencies[node] = sum(latencies) / len(latencies) / 1000

    if node_latencies:
        node_df = pd.DataFrame({
            "Node": list(node_latencies.keys()),
            "Avg Latency (s)": list(node_latencies.values()),
        }).set_index("Node")
        st.bar_chart(node_df)

    # ─── Retrieval stats ─────────────────────────────────

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Retrieval Confidence")
        retrieval_confident_rate = (df["retrieval_confident"].sum() / total_runs * 100) if total_runs > 0 else 0
        st.metric("Docs Found Rate", f"{retrieval_confident_rate:.1f}%")
        avg_chunks = df["chunks_found"].mean()
        st.metric("Avg Chunks per Query", f"{avg_chunks:.1f}")

    with col2:
        st.subheader("Enrichment Status")
        enrichment_counts = df["enrichment_status"].value_counts()
        st.bar_chart(enrichment_counts)

    # ─── Agent Feedback ──────────────────────────────────

    st.markdown("---")
    st.subheader("🗣️ Agent Feedback")

    if fb_df.empty:
        st.info("No feedback yet. Agents can submit feedback via POST /feedback")
    else:
        col1, col2, col3, col4 = st.columns(4)

        fb_total = len(fb_df)
        fb_approved = len(fb_df[fb_df["action"] == "approved"])
        fb_edited = len(fb_df[fb_df["action"] == "edited"])
        fb_rejected = len(fb_df[fb_df["action"] == "rejected"])
        fb_approval_rate = ((fb_approved + fb_edited) / fb_total * 100) if fb_total > 0 else 0

        col1.metric("Total Reviews", fb_total)
        col2.metric("Approved", fb_approved)
        col3.metric("Edited", fb_edited)
        col4.metric("Rejected", fb_rejected)

        st.metric("Approval Rate (approved + edited)", f"{fb_approval_rate:.1f}%")

        # Show recent feedback
        st.subheader("Recent Feedback")
        display_cols = ["timestamp", "ticket_key", "action", "agent_notes"]
        available = [c for c in display_cols if c in fb_df.columns]
        st.dataframe(
            fb_df[available].sort_values("timestamp", ascending=False).head(10),
            use_container_width=True,
            hide_index=True,
        )

    # ─── Missing KB Articles ─────────────────────────────

    st.markdown("---")
    st.subheader("📝 Missing Knowledge Base Articles")
    st.caption("Topics where retrieval failed — write articles for these to improve auto-resolve rate")

    if missing_df.empty:
        st.success("No retrieval failures logged yet.")
    else:
        # Count by product area
        area_counts = missing_df["product_area"].value_counts()
        st.bar_chart(area_counts)

        # Show details
        st.subheader("Recent Retrieval Failures")
        display_cols = ["timestamp", "ticket_key", "subject", "product_area", "query"]
        available = [c for c in display_cols if c in missing_df.columns]
        st.dataframe(
            missing_df[available].sort_values("timestamp", ascending=False).head(10),
            use_container_width=True,
            hide_index=True,
        )

    # ─── Recent runs table ───────────────────────────────

    st.markdown("---")
    st.subheader("Recent Pipeline Runs")

    display_cols = [
        "timestamp", "ticket_key", "subject", "intent",
        "account_tier", "route", "decision", "posted",
        "total_latency_ms", "guardrails_passed",
    ]

    available_cols = [c for c in display_cols if c in df.columns]
    recent = df[available_cols].sort_values("timestamp", ascending=False).head(20)

    st.dataframe(
        recent,
        use_container_width=True,
        hide_index=True,
    )

    # ─── Refresh ─────────────────────────────────────────

    st.markdown("---")
    if st.button("🔄 Refresh"):
        st.rerun()


if __name__ == "__main__":
    main()