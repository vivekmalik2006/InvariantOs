"""
InvariantOS Dashboard — Member 4 (Streamlit)

Pages:
  1. Rule Graph     — filterable table + rule connections
  2. Analyze a PR   — paste or select a diff, analyze with live progress
  3. Result         — rendered summary_markdown with verdict badge

Calls the FastAPI orchestrator at http://localhost:8000.
"""
import time
import json
from pathlib import Path

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = "http://localhost:8000"

# Pre-seeded diffs for the one-click demo
_SEEDED_DIFF_PATH = Path(__file__).parent.parent / "demo-repo" / "seeded-diff.patch"
_BUGGY_DIFF = """\
diff --git a/src/shipments.js b/src/shipments.js
--- a/src/shipments.js
+++ b/src/shipments.js
@@ -22,7 +22,9 @@ const { decrementInventory } = require('./inventory');
  */
 async function shipmentJob(order) {
   // RULE-001: guard — only PAID orders may be shipped
-  if (order.status === 'PAID') {
+  // BUG: widened condition allows CANCELLED orders through
+  if (order.status !== 'CANCELLED') {
     return await createShipment(order);
   }
"""

_FIXED_DIFF = """\
diff --git a/src/shipments.js b/src/shipments.js
--- a/src/shipments.js
+++ b/src/shipments.js
@@ -22,7 +22,7 @@ const { decrementInventory } = require('./inventory');
  */
 async function shipmentJob(order) {
   // RULE-001: guard — only PAID orders may be shipped
-  if (order.status !== 'CANCELLED') {
+  if (order.status === 'PAID') {
     return await createShipment(order);
   }
"""

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="InvariantOS",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("🛡️ InvariantOS")
st.sidebar.markdown("*Hidden Business-Rule Guardian*")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    ["🗂️ Rule Graph", "🔍 Analyze a PR", "📊 Result"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.caption(f"API: `{API_BASE}`")

# Health check indicator
try:
    health = requests.get(f"{API_BASE}/api/health", timeout=2)
    if health.ok:
        st.sidebar.success("✅ Orchestrator online")
    else:
        st.sidebar.warning("⚠️ Orchestrator responding but not healthy")
except Exception:
    st.sidebar.error("❌ Orchestrator offline — start with `uvicorn orchestrator.main:app`")


# ===========================================================================
# Page 1 — Rule Graph
# ===========================================================================
if page == "🗂️ Rule Graph":
    st.title("🗂️ Behavioral Contract Graph")
    st.markdown(
        "The mined business rules InvariantOS will defend. "
        "Every PR analyzed is checked against this graph."
    )

    # Fetch rules
    try:
        resp = requests.get(f"{API_BASE}/api/rules", timeout=5)
        resp.raise_for_status()
        rules_data = resp.json().get("rules", [])
    except Exception as e:
        st.error(f"Failed to load rules from API: {e}")
        rules_data = []

    if not rules_data:
        st.info("No rules loaded yet. Use the **Re-mine Rules** button below to extract rules from demo-repo.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        categories = sorted({r["category"] for r in rules_data})
        severities  = sorted({r["severity"]  for r in rules_data})
        all_tags    = sorted({t for r in rules_data for t in r.get("tags", [])})

        with col1:
            sel_cat = st.multiselect("Category", categories, default=categories)
        with col2:
            sel_sev = st.multiselect("Severity", severities, default=severities)
        with col3:
            sel_tag = st.multiselect("Tag", all_tags)

        filtered = [
            r for r in rules_data
            if r["category"] in sel_cat
            and r["severity"] in sel_sev
            and (not sel_tag or any(t in r.get("tags", []) for t in sel_tag))
        ]

        st.markdown(f"**Showing {len(filtered)} of {len(rules_data)} rules**")
        st.markdown("---")

        for rule in filtered:
            sev_color = {
                "critical": "🔴",
                "high":     "🟠",
                "medium":   "🟡",
                "low":      "🟢",
            }.get(rule["severity"], "⚪")

            with st.expander(f"{sev_color} **{rule['id']}** — {rule['statement']}", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Category:** `{rule['category']}`")
                    st.markdown(f"**Severity:** `{rule['severity']}`")
                    if rule.get("tags"):
                        st.markdown(f"**Tags:** {', '.join(f'`{t}`' for t in rule['tags'])}")
                with c2:
                    if rule.get("related_functions"):
                        st.markdown("**Functions:**")
                        for fn in rule["related_functions"]:
                            st.markdown(f"  - `{fn}()`")
                    if rule.get("related_entities"):
                        st.markdown(f"**Entities:** {', '.join(rule['related_entities'])}")
                if rule.get("source_refs"):
                    st.markdown("**Source refs:**")
                    for ref in rule["source_refs"]:
                        st.markdown(f"  - `{ref['file']}:{ref['lines']}`")

    st.markdown("---")
    if st.button("🔄 Re-mine Rules from demo-repo"):
        with st.spinner("Mining rules from demo-repo..."):
            try:
                r = requests.post(f"{API_BASE}/api/rules/extract", json={"repo_path": "demo-repo"}, timeout=120)
                r.raise_for_status()
                count = len(r.json().get("rules", []))
                st.success(f"✅ Mined {count} rules from demo-repo. Refresh the page to see them.")
            except Exception as e:
                st.error(f"Rule mining failed: {e}")


# ===========================================================================
# Page 2 — Analyze a PR
# ===========================================================================
elif page == "🔍 Analyze a PR":
    st.title("🔍 Analyze a Pull Request")
    st.markdown(
        "Paste a raw unified diff below, or use the one-click demo buttons to load the "
        "seeded buggy or fixed diff."
    )

    # One-click demo buttons
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🐛 Load Buggy Diff", help="The seeded bug: status !== CANCELLED"):
            st.session_state["diff_text"] = _BUGGY_DIFF
            st.session_state["selected_branch"] = "feature/cancel-status-bug"
    with col2:
        if st.button("✅ Load Fixed Diff", help="The fix: status === PAID"):
            st.session_state["diff_text"] = _FIXED_DIFF
            st.session_state["selected_branch"] = "main"
    with col3:
        patch_file = _SEEDED_DIFF_PATH
        if patch_file.exists():
            if st.button("📄 Load from seeded-diff.patch"):
                st.session_state["diff_text"] = patch_file.read_text(encoding="utf-8")
                st.session_state["selected_branch"] = "feature/cancel-status-bug"

    diff_text = st.text_area(
        "Diff (raw unified diff format)",
        value=st.session_state.get("diff_text", ""),
        height=280,
        key="diff_input",
        placeholder="Paste a git diff here, or click a demo button above...",
    )

    branch = st.text_input(
        "Branch name (optional)",
        value=st.session_state.get("selected_branch", ""),
        placeholder="feature/my-branch",
    )

    st.markdown("---")
    analyze_clicked = st.button("🚀 Analyze", type="primary", disabled=not diff_text.strip())

    if analyze_clicked and diff_text.strip():
        # Animated progress display — keeps the parallel-subagents story visible on camera
        progress_steps = [
            ("🗺️ Mapping impact...",          0.15),
            ("📋 Validating contracts...",    0.35),
            ("🔒 Checking security & access...", 0.55),
            ("🧪 Checking test coverage...", 0.75),
            ("📝 Generating report...",       0.90),
        ]

        status_placeholder = st.empty()
        progress_bar       = st.progress(0)

        for label, pct in progress_steps:
            with status_placeholder.container():
                st.info(label)
            progress_bar.progress(pct)
            time.sleep(1.0)  # keep steps visible for video

        # Real API call
        with status_placeholder.container():
            st.info("⏳ Waiting for orchestrator response...")
        try:
            payload = {"diff": diff_text}
            if branch.strip():
                payload["branch"] = branch.strip()

            resp = requests.post(f"{API_BASE}/api/analyze", json=payload, timeout=120)
            resp.raise_for_status()
            report = resp.json()

            progress_bar.progress(1.0)
            status_placeholder.success("✅ Analysis complete!")

            # Store for Result page
            st.session_state["last_report"] = report
            st.session_state["result_ready"] = True

            # Quick verdict summary inline
            verdict = report.get("final_verdict", "UNKNOWN")
            if verdict == "BLOCK":
                st.error(f"🛑 **{report['final_verdict_label']}**")
            elif verdict == "SAFE":
                st.success(f"✅ **{report['final_verdict_label']}**")
            else:
                st.warning(f"⚠️ **{report['final_verdict_label']}**")

            st.markdown("→ Go to **📊 Result** page for the full report.")

        except Exception as e:
            progress_bar.progress(0)
            status_placeholder.error(f"Analysis failed: {e}")


# ===========================================================================
# Page 3 — Result
# ===========================================================================
elif page == "📊 Result":
    st.title("📊 Analysis Result")

    report = st.session_state.get("last_report")

    if not report:
        st.info("No analysis has been run yet. Go to **🔍 Analyze a PR** and click Analyze.")

        # Show recent analyses from API
        st.markdown("---")
        st.subheader("Recent Analyses")
        analysis_id = st.text_input("Load by Analysis ID (e.g. `run-2026-09-26-01`)")
        if analysis_id.strip() and st.button("Load"):
            try:
                r = requests.get(f"{API_BASE}/api/report/{analysis_id.strip()}", timeout=10)
                r.raise_for_status()
                report = r.json()
                st.session_state["last_report"] = report
            except Exception as e:
                st.error(f"Failed to load report: {e}")

    if report:
        verdict = report.get("final_verdict", "UNKNOWN")

        # Verdict badge
        if verdict == "BLOCK":
            st.error(f"🛑 **{report['final_verdict_label']}**")
        elif verdict == "SAFE":
            st.success(f"✅ **{report['final_verdict_label']}**")
        else:
            st.warning(f"⚠️ **{report['final_verdict_label']}**")

        st.markdown(f"**Analysis ID:** `{report.get('analysis_id', 'N/A')}`")
        st.markdown("---")

        # Rendered summary_markdown
        summary = report.get("summary_markdown", "")
        if summary:
            st.markdown(summary, unsafe_allow_html=False)

        # Expandable per-rule details
        impacted = report.get("impacted_rules", [])
        vr_list  = report.get("validation_results", [])
        tg_list  = report.get("test_gaps", [])

        if impacted:
            st.markdown("---")
            st.subheader("📌 Per-Rule Details")
            vr_map = {v["rule_id"]: v for v in vr_list}
            tg_map = {t["rule_id"]: t for t in tg_list}

            for ir in impacted:
                rule_id = ir["rule_id"]
                vr = vr_map.get(rule_id, {})
                tg = tg_map.get(rule_id, {})

                verdict_label = vr.get("verdict", "Not validated")
                color = {"VIOLATION": "🛑", "OK": "✅", "NEEDS_EVIDENCE": "⚠️"}.get(verdict_label, "⬜")

                with st.expander(f"{color} **{rule_id}** — {verdict_label}", expanded=(verdict_label == "VIOLATION")):
                    st.markdown(f"**Why impacted:** {ir.get('reason', 'N/A')}")
                    chain = ir.get("affected_call_chain", [])
                    if chain:
                        st.markdown(f"**Call chain:** `{'` → `'.join(chain)}`")
                    if vr:
                        st.markdown(f"**Explanation:** {vr.get('explanation', '')}")
                        evidence = vr.get("evidence", [])
                        if evidence:
                            st.markdown("**Evidence:**")
                            for ev in evidence:
                                st.markdown(f"  - {ev}")
                    if tg:
                        if tg.get("has_coverage"):
                            st.info("✅ Existing regression test covers this rule.")
                        else:
                            st.warning("⚠️ No regression test found.")
                            test_code = tg.get("generated_test_code", "")
                            test_path = tg.get("generated_test_path", "")
                            if test_path:
                                st.markdown(f"**Generated test:** `{test_path}`")
                            if test_code:
                                with st.expander("View generated test code"):
                                    st.code(test_code, language="javascript")

        # Raw JSON expander
        with st.expander("🔧 Raw JSON report"):
            st.json(report)

        # Download button
        st.download_button(
            "⬇️ Download Report (JSON)",
            data=json.dumps(report, indent=2),
            file_name=f"{report.get('analysis_id', 'report')}.json",
            mime="application/json",
        )
