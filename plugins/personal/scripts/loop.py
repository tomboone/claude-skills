#!/usr/bin/env python3
"""Headless orchestrator: runs /implementit -> /shipit -> /reviewit per loop-ready ticket."""
import json
import re
from collections import namedtuple

InvocationResult = namedtuple("InvocationResult", ["returncode", "result_text", "timed_out"])
TicketResult = namedtuple("TicketResult", ["ticket_id", "implemented", "pr_url", "review_status", "failed_step", "reason"])


def parse_triage_result(result_text):
    """Extract the last JSON object from triage output; normalize keys."""
    text = (result_text or "").strip()
    decoder = json.JSONDecoder()
    last = None
    i = 0
    while i < len(text):
        if text[i] == "{":
            try:
                obj, idx = decoder.raw_decode(text[i:])
            except json.JSONDecodeError:
                i += 1
                continue
            if isinstance(obj, dict):
                last = obj
            i += idx
        else:
            i += 1
    if last is None:
        raise ValueError("no JSON object found in triage result")
    return {
        "project": last.get("project"),
        "wave": last.get("wave", []),
        "held": last.get("held", []),
    }


def parse_review_status(result_text):
    """Return APPROVED / CHANGES_REQUESTED / None from a /reviewit result."""
    if "STATUS: CHANGES_REQUESTED" in (result_text or ""):
        return "CHANGES_REQUESTED"
    if "STATUS: APPROVED" in (result_text or ""):
        return "APPROVED"
    return None


_PR_RE = re.compile(r"https://github\.com/[^\s)]+/pull/\d+")


def build_claude_cmd(prompt, model):
    return [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--permission-mode", "bypassPermissions",
    ]


def shipit_pr_url(result_text):
    m = _PR_RE.search(result_text or "")
    return m.group(0) if m else None


def classify_outcome(returncode, result_text, timed_out, step):
    if timed_out:
        return (False, f"{step} timed out")
    if returncode != 0:
        return (False, f"{step} exited {returncode}")
    if step == "shipit" and shipit_pr_url(result_text) is None:
        return (False, "shipit produced no PR URL")
    return (True, "")


def format_summary(results, held):
    lines = ["", "=== Loop run summary ==="]
    if not results:
        lines.append("No tickets processed.")
    for r in results:
        if r.failed_step:
            lines.append(f"  {r.ticket_id}: FAILED at {r.failed_step} — {r.reason}")
        else:
            pr = r.pr_url or "(no PR)"
            review = r.review_status or "(no review)"
            lines.append(f"  {r.ticket_id}: PR {pr} — review {review}")
    if held:
        lines.append("Held for a future run (blockers not yet merged):")
        for h in held:
            waiting = ", ".join(h.get("waiting_on", [])) or "?"
            lines.append(f"  {h.get('id')}: waiting on {waiting}")
    return "\n".join(lines)
