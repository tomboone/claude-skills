#!/usr/bin/env python3
"""Headless orchestrator: runs /implementit -> /shipit -> /reviewit per loop-ready ticket."""
import json
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
