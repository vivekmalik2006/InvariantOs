"""
Test Gap Agent — Member 3 (Real Implementation).

For each impacted rule:
  1. Coverage check: scan test files for references to the rule's call chain
     AND assertions about the violating condition (e.g. CANCELLED status).
  2. If no coverage found, call the LLM to generate a real Jest regression test.
  3. Write the generated test to demo-repo/tests/generated/rule_XXX_regression.test.js.

Fallback: if the LLM call fails, write a deterministic stub test that still
correctly tests the CANCELLED-order scenario for RULE-001.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from orchestrator.schemas import ImpactedRule, TestGap

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze(diff: str, impacted_rules: list[ImpactedRule], repo_path: str) -> list[TestGap]:
    """
    Check test coverage for each impacted rule and generate a regression test
    if coverage is missing.

    Args:
        diff:            Raw unified-diff string of the PR.
        impacted_rules:  Output of the Change Impact Agent.
        repo_path:       Path to the repository under analysis.

    Returns:
        A list of TestGap — one per impacted rule.
    """
    gaps: list[TestGap] = []

    for impacted in impacted_rules:
        has_coverage, matched_file = _check_coverage(impacted, repo_path)

        if has_coverage:
            logger.info("Coverage confirmed for %s in %s", impacted.rule_id, matched_file)
            gaps.append(TestGap(
                rule_id=impacted.rule_id,
                has_coverage=True,
                generated_test_path=None,
                generated_test_code=None,
            ))
        else:
            logger.info("No coverage found for %s — generating regression test.", impacted.rule_id)
            test_code = _generate_test(impacted, diff, repo_path)
            test_path = _test_output_path(impacted, repo_path)

            _write_test_file(test_path, test_code)

            gaps.append(TestGap(
                rule_id=impacted.rule_id,
                has_coverage=False,
                generated_test_path=test_path,
                generated_test_code=test_code,
            ))

    return gaps


# ---------------------------------------------------------------------------
# Coverage detection
# ---------------------------------------------------------------------------

def _check_coverage(impacted: ImpactedRule, repo_path: str) -> tuple[bool, str]:
    """
    Return (has_coverage, matched_file_path).

    Coverage is confirmed only if we find a test that:
      1. References at least one function from the affected call chain.
      2. AND contains an assertion about the violation condition (e.g. 'CANCELLED').

    Generated tests are excluded from coverage — they count as "no coverage" so
    the agent always has an opportunity to refresh the generated test.
    """
    tests_dir = os.path.join(repo_path, "tests")
    if not os.path.isdir(tests_dir):
        return False, ""

    chain_lower = [fn.lower() for fn in (impacted.affected_call_chain or [])]
    # Keyword hint from the rule ID — RULE-001 looks for CANCELLED condition
    violation_hints = _get_violation_hints(impacted)

    for dirpath, dirnames, filenames in os.walk(tests_dir):
        # Skip the generated/ subdirectory — generated tests don't count as real coverage
        dirnames[:] = [d for d in dirnames if d != "generated"]
        for fname in filenames:
            if not (fname.endswith(".test.js") or fname.endswith(".spec.js")
                    or fname.endswith(".test.ts")):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read().lower()
                chain_hit = any(fn in content for fn in chain_lower)
                violation_hit = any(hint in content for hint in violation_hints)
                if chain_hit and violation_hit:
                    return True, fpath
            except OSError:
                continue

    return False, ""


def _get_violation_hints(impacted: ImpactedRule) -> list[str]:
    """
    Return lowercase strings that indicate a test is asserting the violation condition.
    Derived from the rule's call chain and common patterns.
    """
    hints = ["cancelled", "violation", "must not", "should not", "not.tohavebeencalled",
             "not tohavebeencalled", "toberejected", "tothrow", "rejects"]
    # Add any identifiers from the rule_id pattern
    rule_lower = impacted.rule_id.lower().replace("-", "_")
    hints.append(rule_lower)
    return hints


# ---------------------------------------------------------------------------
# Test generation
# ---------------------------------------------------------------------------

_TEST_GEN_SYSTEM_PROMPT = """\
You are a senior JavaScript/Jest test engineer. You will be given:
1. A business rule that a code change might violate.
2. The call chain affected by the change.
3. The PR diff showing the change.

Write a Jest test file that:
- Uses jest.mock() for all external dependencies.
- Has a primary test named to clearly describe the violation scenario.
- Contains an assertion that FAILS on the buggy code and PASSES on the fixed code.
- Uses async/await where appropriate.
- Is self-contained and can be run with `npx jest` from the repo root.
- Imports from relative paths like `../../src/...`.

Return ONLY the test file contents — no markdown fences, no explanation."""


def _generate_test(impacted: ImpactedRule, diff: str, repo_path: str) -> str:
    """Generate a Jest regression test via LLM, with a safe fallback."""
    try:
        from orchestrator.llm_client import complete, LLMClientError  # type: ignore

        call_chain = " → ".join(impacted.affected_call_chain) if impacted.affected_call_chain else "unknown"
        entry_fn = impacted.affected_call_chain[0] if impacted.affected_call_chain else "unknownFunction"
        final_fn = impacted.affected_call_chain[-1] if impacted.affected_call_chain else "unknownFunction"
        source_module = _infer_source_module(entry_fn)

        user_prompt = (
            f"Rule: {impacted.rule_id}\n"
            f"Statement: {impacted.reason}\n"
            f"Call chain: {call_chain}\n"
            f"Entry function: {entry_fn} (from {source_module})\n"
            f"Terminal function: {final_fn}\n\n"
            f"PR diff:\n```\n{diff[:2000]}\n```\n\n"
            "Write a Jest test file for this regression. "
            "The primary test must assert that a CANCELLED order does NOT trigger "
            f"{final_fn}. Include a second test confirming a PAID order DOES trigger it."
        )

        test_code = complete(_TEST_GEN_SYSTEM_PROMPT, user_prompt)
        # Strip any accidental markdown fences
        test_code = re.sub(r"^```(?:javascript|js)?\s*", "", test_code, flags=re.MULTILINE)
        test_code = re.sub(r"\s*```\s*$", "", test_code, flags=re.MULTILINE)
        test_code = test_code.strip()

        if len(test_code) < 100:
            raise ValueError("LLM returned implausibly short test code.")

        logger.info("LLM generated test for %s (%d chars)", impacted.rule_id, len(test_code))
        return test_code

    except Exception as exc:
        logger.warning(
            "LLM test generation failed for %s (%s); using deterministic fallback.",
            impacted.rule_id, exc,
        )
        return _fallback_test(impacted)


def _infer_source_module(fn_name: str) -> str:
    """Map a function name to its most likely source module path."""
    fn_lower = fn_name.lower()
    if any(k in fn_lower for k in ["order", "cancel", "status"]):
        return "../../src/orders"
    if any(k in fn_lower for k in ["shipment", "ship", "warehouse"]):
        return "../../src/shipments"
    if any(k in fn_lower for k in ["payment", "refund", "pay"]):
        return "../../src/payments"
    if any(k in fn_lower for k in ["discount", "coupon"]):
        return "../../src/discounts"
    return "../../src/orders"


def _fallback_test(impacted: ImpactedRule) -> str:
    """
    Deterministic fallback test for the demo scenario.
    For RULE-001 this test WILL fail on the buggy branch and pass on main.
    For other rules, generates a skeleton test with TODO markers.
    """
    rule_id = impacted.rule_id
    call_chain = impacted.affected_call_chain or []
    entry_fn = call_chain[0] if call_chain else "unknownFunction"
    source_module = _infer_source_module(entry_fn)

    # Specialised, verified test for RULE-001 (the demo scenario)
    if rule_id == "RULE-001" or "shipmentJob" in call_chain or "createShipment" in call_chain or "cancelOrder" in call_chain:
        return f"""\
/**
 * Regression test for {rule_id}
 * Auto-generated by InvariantOS Test Gap Agent.
 *
 * Rule: {impacted.reason}
 * Call chain: {" → ".join(call_chain) if call_chain else "unknown"}
 *
 * This test MUST FAIL on the buggy branch and PASS on the fixed branch.
 */

'use strict';

const {{ cancelOrder }} = require('../../src/orders');
const {{ shipmentJob }} = require('../../src/shipments');
const warehouseApi = require('../../src/warehouseApi');

jest.mock('../../src/warehouseApi');
jest.mock('../../src/inventory', () => ({{
  decrementInventory: jest.fn().mockResolvedValue(undefined),
}}));

describe('{rule_id} regression', () => {{
  beforeEach(() => {{
    jest.clearAllMocks();
    warehouseApi.createShipment.mockResolvedValue({{ shipmentId: 'SHIP-GEN', status: 'CREATED' }});
  }});

  test('A CANCELLED order must NOT trigger createShipment (RULE-001)', async () => {{
    const originalOrder = {{ id: 'ORD-REG-001', status: 'PAID', items: [] }};
    const cancelledOrder = cancelOrder(originalOrder);

    const result = await shipmentJob(cancelledOrder);

    expect(warehouseApi.createShipment).not.toHaveBeenCalled();
    expect(result).toBeNull();
  }});

  test('A PAID order SHOULD trigger createShipment', async () => {{
    const order = {{ id: 'ORD-REG-002', status: 'PAID', items: [] }};
    await shipmentJob(order);
    expect(warehouseApi.createShipment).toHaveBeenCalledTimes(1);
  }});
}});
"""

    # Generic skeleton for other rules — requires LLM for a real test body
    chain_str = " → ".join(call_chain) if call_chain else "unknown"
    return f"""\
/**
 * Regression test skeleton for {rule_id}
 * Auto-generated by InvariantOS Test Gap Agent (LLM unavailable — skeleton only).
 *
 * Rule: {impacted.reason}
 * Call chain: {chain_str}
 *
 * TODO: Fill in the test body to assert the violation scenario.
 * Run with: npx jest tests/generated/{rule_id.lower().replace("-", "_")}_regression.test.js
 */

'use strict';

// TODO: import the relevant module
// const {{ {entry_fn} }} = require('{source_module}');

describe('{rule_id} regression — {impacted.reason[:60]}', () => {{
  test.todo('Add regression test — requires LLM to generate (set WATSONX_API_KEY or OPENAI_API_KEY)');
}});
"""


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _test_output_path(impacted: ImpactedRule, repo_path: str) -> str:
    """Compute the output path for the generated test file."""
    rule_slug = impacted.rule_id.lower().replace("-", "_")
    return os.path.join(repo_path, "tests", "generated", f"{rule_slug}_regression.test.js")


def _write_test_file(path: str, code: str) -> None:
    """Write generated test to disk."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        logger.info("Generated test written to %s", path)
    except OSError as exc:
        logger.warning("Could not write generated test to %s: %s", path, exc)
