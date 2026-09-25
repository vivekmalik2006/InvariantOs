"""
Diff parsing utilities for InvariantOS.
Extracts changed file paths, changed function/symbol names, and added/removed
lines from a raw unified-diff string.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class DiffHunk:
    file_path: str
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    changed_symbols: list[str] = field(default_factory=list)  # function/class names


@dataclass
class ParsedDiff:
    changed_files: list[str] = field(default_factory=list)
    changed_symbols: list[str] = field(default_factory=list)  # deduped across all hunks
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    hunks: list[DiffHunk] = field(default_factory=list)


# Patterns that identify function/class/method definitions in common languages
_SYMBOL_PATTERNS = [
    re.compile(r"^\+?[-\s]*(?:async\s+)?function\s+(\w+)", re.MULTILINE),       # JS/TS function
    re.compile(r"^\+?[-\s]*(?:async\s+)?def\s+(\w+)", re.MULTILINE),             # Python def
    re.compile(r"^\+?[-\s]*class\s+(\w+)", re.MULTILINE),                         # class (any lang)
    re.compile(r"^\+?[-\s]*(?:public|private|protected|static)?\s+\w+\s+(\w+)\s*\(", re.MULTILINE),  # Java/C# method
    re.compile(r"^\+?[-\s]*const\s+(\w+)\s*=\s*(?:async\s*)?\(", re.MULTILINE), # JS const arrow
    re.compile(r"^\+?[-\s]*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=", re.MULTILINE),  # JS exports
]

_FILE_HEADER = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
_HUNK_HEADER = re.compile(r"^@@ .+ @@\s*(.*)", re.MULTILINE)


def parse_diff(diff: str) -> ParsedDiff:
    """
    Parse a raw unified-diff string and return a structured ParsedDiff.

    The function works by:
    1. Scanning for +++ b/<path> headers to find changed files.
    2. Within each file section, scanning context lines before each hunk for
       the nearest preceding function/class/def declaration (heuristic for
       "what symbol was changed").
    3. Collecting all added (+) and removed (-) lines.

    This is intentionally heuristic — it is used only as a fast first-pass
    signal for the Change Impact Agent.
    """
    result = ParsedDiff()
    all_symbols: set[str] = set()

    # Split into per-file sections by the "diff --git" or "+++ b/" boundary
    file_sections = _split_into_file_sections(diff)

    for file_path, section_text in file_sections:
        hunk = DiffHunk(file_path=file_path)
        result.changed_files.append(file_path)

        lines = section_text.splitlines()
        context_window: list[str] = []  # accumulates context to find nearest symbol

        for line in lines:
            if line.startswith("---") or line.startswith("+++"):
                continue
            if line.startswith("@@"):
                # Extract inline function hint from hunk header: "@@ ... @@ funcName"
                m = _HUNK_HEADER.match(line)
                if m and m.group(1).strip():
                    # Extract only the last word token before '(' to get the actual name
                    # e.g. "async function shipmentJob" → "shipmentJob"
                    raw_hint = m.group(1).strip().split("(")[0].strip()
                    sym = raw_hint.split()[-1] if raw_hint else ""
                    if sym and len(sym) > 1:
                        hunk.changed_symbols.append(sym)
                        all_symbols.add(sym)
                context_window = []
                continue

            if line.startswith("+") and not line.startswith("+++"):
                content = line[1:]
                hunk.added_lines.append(content)
                result.added_lines.append(content)
                context_window.append(content)
            elif line.startswith("-") and not line.startswith("---"):
                content = line[1:]
                hunk.removed_lines.append(content)
                result.removed_lines.append(content)
                context_window.append(content)
            else:
                # Context line — may contain a function/class definition above the hunk
                context_window.append(line.lstrip(" "))

            # Find symbol definitions in accumulated context
            for pattern in _SYMBOL_PATTERNS:
                for m in pattern.finditer("\n".join(context_window[-20:])):
                    sym = m.group(1).strip()
                    if sym and len(sym) > 1:
                        hunk.changed_symbols.append(sym)
                        all_symbols.add(sym)

        # Also scan the whole section text for any symbol mentions
        for pattern in _SYMBOL_PATTERNS:
            for m in pattern.finditer(section_text):
                sym = m.group(1).strip()
                if sym and len(sym) > 1:
                    all_symbols.add(sym)

        result.hunks.append(hunk)

    result.changed_symbols = sorted(all_symbols)
    return result


def _split_into_file_sections(diff: str) -> list[tuple[str, str]]:
    """
    Split a unified diff into (file_path, section_text) pairs.
    Handles both 'diff --git' and bare '+++ b/' headers.
    """
    sections: list[tuple[str, str]] = []

    # Try splitting on 'diff --git a/... b/...' lines first
    git_split = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)
    if len(git_split) > 1:
        for chunk in git_split:
            if not chunk.strip():
                continue
            m = _FILE_HEADER.search(chunk)
            if m:
                sections.append((m.group(1).strip(), chunk))
        return sections

    # Fallback: split on '+++ b/' lines
    parts = re.split(r"(?=^\+\+\+ b/)", diff, flags=re.MULTILINE)
    for part in parts:
        if not part.strip():
            continue
        m = _FILE_HEADER.match(part)
        if m:
            sections.append((m.group(1).strip(), part))
        else:
            # No file header found but there's content — use a placeholder
            sections.append(("unknown", part))

    # If we still found nothing, treat the whole diff as one section
    if not sections:
        sections.append(("unknown", diff))

    return sections


def extract_changed_symbols(diff: str) -> list[str]:
    """Convenience wrapper — returns just the list of changed symbol names."""
    return parse_diff(diff).changed_symbols


def extract_changed_files(diff: str) -> list[str]:
    """Convenience wrapper — returns just the list of changed file paths."""
    return parse_diff(diff).changed_files
