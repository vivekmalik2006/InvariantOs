"""
Rule Miner Agent — STUB (Member 1 owns the real implementation).

This stub reads data/rules.json (the hand-written stub) and returns its
contents. The real implementation (Member 1) replaces the body with LLM-
based mining from the demo-repo docs/code/tests.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

from orchestrator.schemas import Rule

logger = logging.getLogger(__name__)

_RULES_JSON = Path(__file__).parent.parent / "data" / "rules.json"


def mine_rules(repo_path: str) -> list[Rule]:
    """
    Mine business rules from the given repository path.

    Args:
        repo_path: Path to the repository to analyze.

    Returns:
        A list of Rule objects.

    NOTE: This is a stub. The real implementation (Member 1) will walk
    repo_path and call the LLM to extract rules from docs, code, and tests.
    """
    logger.info("Rule miner stub: loading rules from %s", _RULES_JSON)
    if not _RULES_JSON.exists():
        logger.warning("rules.json not found at %s; returning empty list.", _RULES_JSON)
        return []
    with open(_RULES_JSON, encoding="utf-8") as f:
        raw = json.load(f)
    rules: list[Rule] = []
    for item in raw:
        try:
            rules.append(Rule(**item))
        except Exception as e:
            logger.warning("Skipping invalid rule entry: %s — %s", item, e)
    logger.info("Rule miner stub: loaded %d rules.", len(rules))
    return rules
