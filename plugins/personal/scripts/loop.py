#!/usr/bin/env python3
"""Headless orchestrator: runs /implementit -> /shipit -> /reviewit per loop-ready ticket."""
import argparse
import json
import re
import subprocess
import sys
from collections import namedtuple

InvocationResult = namedtuple("InvocationResult", ["returncode", "result_text", "timed_out", "usage"], defaults=[None])
TicketResult = namedtuple("TicketResult", ["ticket_id", "implemented", "pr_url", "review_status", "failed_step", "reason", "usage"], defaults=[None])


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


def implementit_complete(result_text):
    """True when /implementit signalled it actually executed the plan to completion."""
    return "STATUS: IMPLEMENTED" in (result_text or "")


def classify_outcome(returncode, result_text, timed_out, step):
    if timed_out:
        return (False, f"{step} timed out")
    if returncode != 0:
        return (False, f"{step} exited {returncode}")
    if step == "implementit" and not implementit_complete(result_text):
        # A zero exit is not enough: /implementit exits 0 even when it bails early
        # (e.g. no plan found). Require the explicit completion sentinel so a no-op
        # implement step doesn't march on to /shipit and report a false success.
        if "STATUS: NO_PLAN" in (result_text or ""):
            return (False, "implementit found no plan/spec (run planit first)")
        return (False, "implementit did not complete (no STATUS: IMPLEMENTED)")
    if step == "shipit" and shipit_pr_url(result_text) is None:
        return (False, "shipit produced no PR URL")
    return (True, "")


def _usage_record(step, model, usage):
    rec = {"step": step, "model": model}
    if usage:
        rec.update(usage)
    return rec


def run_ticket_pipeline(ticket, runner, models, timeouts):
    tid = ticket["id"]
    usages = []

    res = runner(build_claude_cmd(f"/personal:implementit {tid}", models["implementit"]), timeouts["implementit"])
    usages.append(_usage_record("implementit", models["implementit"], res.usage))
    ok, reason = classify_outcome(res.returncode, res.result_text, res.timed_out, "implementit")
    if not ok:
        return TicketResult(tid, False, None, None, "implementit", reason, usages)

    res = runner(build_claude_cmd(f"/personal:shipit {tid}", models["shipit"]), timeouts["shipit"])
    usages.append(_usage_record("shipit", models["shipit"], res.usage))
    ok, reason = classify_outcome(res.returncode, res.result_text, res.timed_out, "shipit")
    if not ok:
        return TicketResult(tid, True, None, None, "shipit", reason, usages)
    pr_url = shipit_pr_url(res.result_text)

    res = runner(build_claude_cmd(f"/personal:reviewit {tid}", models["reviewit"]), timeouts["reviewit"])
    usages.append(_usage_record("reviewit", models["reviewit"], res.usage))
    ok, reason = classify_outcome(res.returncode, res.result_text, res.timed_out, "reviewit")
    if not ok:
        return TicketResult(tid, True, pr_url, None, "reviewit", reason, usages)

    return TicketResult(tid, True, pr_url, parse_review_status(res.result_text), None, None, usages)


_USAGE_FIELDS = ("cost_usd", "input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
_STEP_ORDER = ("implementit", "shipit", "reviewit", "addressit", "mergeit")


def _ticket_cost(r):
    return sum(
        rec["cost_usd"] for rec in (r.usage or [])
        if isinstance(rec.get("cost_usd"), (int, float))
    )


def _sum_usage(results):
    """Aggregate cost/tokens per step and overall across ticket results."""
    by_step = {}
    total = {f: 0 for f in _USAGE_FIELDS}
    for r in results:
        for rec in (r.usage or []):
            agg = by_step.setdefault(rec.get("step", "?"), {f: 0 for f in _USAGE_FIELDS})
            for f in _USAGE_FIELDS:
                v = rec.get(f)
                if isinstance(v, (int, float)):
                    agg[f] += v
                    total[f] += v
    return by_step, total


def _format_usage_lines(results):
    by_step, total = _sum_usage(results)
    if not by_step:
        return []
    def row(label, a):
        return (f"  {label}: ${a['cost_usd']:.4f}  {a['input_tokens']} in / {a['output_tokens']} out"
                f"  (cache read {a['cache_read_input_tokens']})")
    lines = ["Usage by step:"]
    ordered = [s for s in _STEP_ORDER if s in by_step] + [s for s in by_step if s not in _STEP_ORDER]
    for step in ordered:
        lines.append(row(step, by_step[step]))
    lines.append(row("TOTAL", total))
    return lines


def format_summary(results, held):
    lines = ["", "=== Loop run summary ==="]
    if not results:
        lines.append("No tickets processed.")
    for r in results:
        if r.failed_step:
            line = f"  {r.ticket_id}: FAILED at {r.failed_step} — {r.reason}"
        else:
            pr = r.pr_url or "(no PR)"
            review = r.review_status or "(no review)"
            line = f"  {r.ticket_id}: PR {pr} — review {review}"
        if r.usage:
            line += f" — ${_ticket_cost(r):.4f}"
        lines.append(line)
    lines.extend(_format_usage_lines(results))
    if held:
        lines.append("Held for a future run (blockers not yet merged):")
        for h in held:
            waiting = ", ".join(h.get("waiting_on", [])) or "?"
            lines.append(f"  {h.get('id')}: waiting on {waiting}")
    return "\n".join(lines)


TRIAGE_PROMPT = (
    "Using the Linear MCP, find work tickets in project {project!r} that are ready for the "
    "implementation loop: they carry the {label!r} label, every one of their blockedBy blockers "
    "has status Done, and the ticket itself is still un-started (status Todo or Backlog, not "
    "In Progress/In Review/Done). Return ONLY a JSON object as your final message, no prose:\n"
    '{{"project": "{project}", "wave": [{{"id": "...", "title": "..."}}], '
    '"held": [{{"id": "...", "title": "...", "waiting_on": ["..."]}}]}}'
)


def parse_args(argv):
    p = argparse.ArgumentParser(description="Run one wave of loop-ready tickets through implement/ship/review.")
    p.add_argument("--project")
    p.add_argument("--label", default="loop-ready")
    p.add_argument("--tickets", nargs="*")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--notify", action="store_true")
    return p.parse_args(argv)


def _parse_claude_json(stdout):
    """Parse a `claude -p --output-format json` payload; return the dict or None."""
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _result_from_stdout(stdout):
    payload = _parse_claude_json(stdout)
    return (payload.get("result") or "") if payload else ""


def _usage_from_stdout(stdout):
    """Pull cost + token counts from a claude -p payload into a flat dict (None if unparseable)."""
    payload = _parse_claude_json(stdout)
    if not payload:
        return None
    usage = payload.get("usage") or {}
    return {
        "cost_usd": payload.get("total_cost_usd"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
    }


def subprocess_runner(cmd, timeout):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return InvocationResult(proc.returncode, _result_from_stdout(proc.stdout), False, _usage_from_stdout(proc.stdout))
    except subprocess.TimeoutExpired:
        return InvocationResult(-1, "", True, None)


def _read_repo_claude_md():
    for name in ("CLAUDE.md", ".claude/CLAUDE.md"):
        try:
            with open(name, "r") as f:
                return f.read()
        except OSError:
            continue
    return ""


def resolve_project(args, read_claude_md=_read_repo_claude_md):
    if args.project:
        return args.project
    for line in read_claude_md().splitlines():
        if line.strip().lower().startswith("linear_initiative:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("Cannot resolve project: pass --project or set 'linear_initiative:' in the repo CLAUDE.md.")


def feasibility_guard(runner):
    res = runner(build_claude_cmd("Reply with exactly: LOOP_OK", "haiku"), 120)
    if res.timed_out or res.returncode != 0:
        return (False, "claude -p did not run (check CLI/auth/MCP availability)")
    if "LOOP_OK" not in (res.result_text or ""):
        return (False, f"unexpected guard output: {res.result_text!r}")
    return (True, "ok")


def run_triage(project, label, runner):
    res = runner(build_claude_cmd(TRIAGE_PROMPT.format(project=project, label=label), "sonnet"), 300)
    if res.timed_out or res.returncode != 0:
        raise SystemExit("Triage call failed.")
    return parse_triage_result(res.result_text)


def main(argv, runner=subprocess_runner, triage_fn=run_triage, guard_fn=feasibility_guard):
    args = parse_args(argv)
    models = {"implementit": "sonnet", "shipit": "sonnet", "reviewit": "opus"}
    timeouts = {"implementit": 1800, "shipit": 600, "reviewit": 900}

    ok, msg = guard_fn(runner)
    if not ok:
        print(f"Feasibility check failed: {msg}", file=sys.stderr)
        return 2
    if args.check:
        print("Feasibility check passed.")
        return 0

    project = resolve_project(args)
    if args.tickets:
        triage = {"project": project, "wave": [{"id": t, "title": ""} for t in args.tickets], "held": []}
    else:
        triage = triage_fn(project, args.label, runner)

    wave = triage["wave"][: args.limit] if args.limit else triage["wave"]

    if args.dry_run:
        print(f"Project: {project}. Wave ({len(wave)}): {[t['id'] for t in wave]}")
        for t in wave:
            for step, model in (("implementit", models["implementit"]), ("shipit", models["shipit"]), ("reviewit", models["reviewit"])):
                print("  would run:", " ".join(build_claude_cmd(f"/personal:{step} {t['id']}", model)))
        print(format_summary([], triage["held"]))
        return 0

    results = [run_ticket_pipeline(t, runner, models, timeouts) for t in wave]
    print(format_summary(results, triage["held"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
