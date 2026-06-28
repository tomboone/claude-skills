#!/usr/bin/env python3
"""Headless orchestrator: drives /implementit -> /shipit -> (/reviewit <-> /addressit)* -> /mergeit per loop-ready ticket."""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import namedtuple
from datetime import datetime, timezone

InvocationResult = namedtuple("InvocationResult", ["returncode", "result_text", "timed_out", "usage"], defaults=[None])
TicketResult = namedtuple(
    "TicketResult",
    ["ticket_id", "implemented", "pr_url", "review_status", "failed_step", "reason", "usage", "disposition", "rounds"],
    defaults=[None, None, 0],
)


def default_models():
    return {"implementit": "sonnet", "shipit": "sonnet", "reviewit": "opus",
            "reviewit_rereview": "sonnet", "addressit": "sonnet", "mergeit": "haiku",
            "triage": "sonnet", "guard": "haiku"}


def default_timeouts():
    return {"implementit": 1800, "shipit": 600, "reviewit": 900,
            "addressit": 1800, "mergeit": 1200}


def default_efforts():
    return {"implementit": "high", "shipit": "low", "reviewit": "high",
            "reviewit_rereview": "medium", "addressit": "medium", "mergeit": "low",
            "triage": "medium", "guard": "low"}


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


def parse_address_status(result_text):
    text = result_text or ""
    if "STATUS: BLOCKED" in text:
        return "BLOCKED"
    if "STATUS: PUSHED_BACK" in text:
        return "PUSHED_BACK"
    if "STATUS: ADDRESSED" in text:
        return "ADDRESSED"
    return None


def parse_merge_status(result_text):
    text = result_text or ""
    if "STATUS: MERGE_BLOCKED" in text:
        return "MERGE_BLOCKED"
    if "STATUS: MERGED" in text:
        return "MERGED"
    return None


MAX_ROUNDS = 3

_PR_RE = re.compile(r"https://github\.com/[^\s)]+/pull/\d+")


def build_claude_cmd(prompt, model, effort=None):
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--permission-mode", "bypassPermissions",
    ]
    if effort is not None:
        cmd += ["--effort", effort]
    return cmd


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


def run_ticket_pipeline(ticket, runner, models, timeouts, max_rounds=MAX_ROUNDS, efforts=None, emit=None, merge=False, base=None):
    tid = ticket["id"]
    usages = []

    def step(name, model, timeout, label=None, effort_key=None):
        if emit:
            emit(label or name)
        effort = (efforts or {}).get(effort_key or name)
        suffix = f" --base {base}" if (base and name in ("implementit", "shipit")) else ""
        res = runner(build_claude_cmd(f"/personal:{name} {tid}{suffix}", model, effort=effort), timeout)
        usages.append(_usage_record(name, model, res.usage))
        return res

    def fail(at, reason):
        return TicketResult(tid, True, pr_url, last_review, at, reason, usages, "FAILED", rounds)

    def stall(reason):
        return TicketResult(tid, True, pr_url, last_review, None, reason, usages, "NEEDS_HUMAN", rounds)

    pr_url = None
    last_review = None
    rounds = 0

    res = step("implementit", models["implementit"], timeouts["implementit"])
    ok, reason = classify_outcome(res.returncode, res.result_text, res.timed_out, "implementit")
    if not ok:
        return TicketResult(tid, False, None, None, "implementit", reason, usages, "FAILED", 0)

    res = step("shipit", models["shipit"], timeouts["shipit"])
    ok, reason = classify_outcome(res.returncode, res.result_text, res.timed_out, "shipit")
    if not ok:
        return TicketResult(tid, True, None, None, "shipit", reason, usages, "FAILED", 0)
    pr_url = shipit_pr_url(res.result_text)

    while True:
        rounds += 1
        review_key = "reviewit" if rounds == 1 else "reviewit_rereview"
        model = models[review_key]
        res = step("reviewit", model, timeouts["reviewit"], label=f"reviewit (round {rounds})", effort_key=review_key)
        if res.timed_out or res.returncode != 0:
            return fail("reviewit", f"reviewit {'timed out' if res.timed_out else f'exited {res.returncode}'}")
        last_review = parse_review_status(res.result_text)
        if last_review == "APPROVED":
            break
        if last_review != "CHANGES_REQUESTED":
            return fail("reviewit", "reviewit emitted no verdict")

        res = step("addressit", models["addressit"], timeouts["addressit"], label=f"addressit (round {rounds})")
        if res.timed_out or res.returncode != 0:
            return fail("addressit", f"addressit {'timed out' if res.timed_out else f'exited {res.returncode}'}")
        addressed = parse_address_status(res.result_text)
        if addressed == "PUSHED_BACK":
            return stall("impasse: reviewer requested changes, addressit pushed back")
        if addressed == "BLOCKED" or addressed is None:
            return stall("addressit blocked / emitted no status")
        if rounds >= max_rounds:
            return stall(f"max rounds ({max_rounds}) reached without approval")
        # else ADDRESSED → loop for re-review

    if not merge:
        return TicketResult(tid, True, pr_url, last_review, None, None, usages, "READY_FOR_REVIEW", rounds)

    res = step("mergeit", models["mergeit"], timeouts["mergeit"])
    if res.timed_out or res.returncode != 0:
        return fail("mergeit", f"mergeit {'timed out' if res.timed_out else f'exited {res.returncode}'}")
    if parse_merge_status(res.result_text) == "MERGED":
        return TicketResult(tid, True, pr_url, last_review, None, None, usages, "MERGED", rounds)
    return stall("merge blocked (CI failed / verdict not ready)")


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
            disp = r.disposition or (r.review_status or "(no review)")
            line = f"  {r.ticket_id}: {disp} — PR {pr} — {r.rounds} round(s)"
            if r.disposition == "NEEDS_HUMAN" and r.reason:
                line += f" — {r.reason}"
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
    "implementation loop. A ticket qualifies only if ALL hold: it carries BOTH the {label!r} "
    "label AND the {repo_label!r} label; every one of its blockedBy blockers has status Done; "
    "and the ticket itself is still un-started (status Todo or Backlog, not In Progress/In "
    "Review/Done). EXCLUDE any issue that has sub-issues (children) or carries the 'user-story' "
    "label — those are containers, not implementable work. Return ONLY a JSON object as your "
    "final message, no prose:\n"
    '{{"project": "{project}", "wave": [{{"id": "...", "title": "..."}}], '
    '"held": [{{"id": "...", "title": "...", "waiting_on": ["..."]}}]}}'
)


def _loop_log_path(now):
    # CWD-relative, like _read_repo_claude_md/resolve_project: the loop is invoked
    # from the repo root, so this resolves to <repo>/.claude/loop/run-*.log.
    return os.path.join(".claude", "loop", f"run-{now.strftime('%Y%m%dT%H%M%SZ')}.log")


def _detached_argv(argv):
    return [sys.executable, os.path.abspath(__file__)] + [a for a in argv if a != "--detach"]


def _spawn_detached(argv):
    log_path = _loop_log_path(datetime.now(timezone.utc))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    gi = os.path.join(os.path.dirname(log_path), ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w") as f:
            f.write("*\n")
    logf = open(log_path, "w")
    proc = subprocess.Popen(_detached_argv(argv), stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    return proc.pid, log_path


def parse_args(argv):
    p = argparse.ArgumentParser(description="Run one wave of loop-ready tickets through implement/ship/review<->address/merge.")
    p.add_argument("--project")
    p.add_argument("--repo")
    p.add_argument("--label", default="loop-ready")
    p.add_argument("--tickets", nargs="*")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--notify", action="store_true")
    p.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    p.add_argument("--detach", action="store_true")
    p.add_argument("--merge", action="store_true")
    p.add_argument("--base")
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


def _repo_name_from_url(url):
    """Canonical repo name (basename, no .git) from an origin remote URL; None if unparseable."""
    s = (url or "").strip().rstrip("/")
    if not s:
        return None
    if s.endswith(".git"):
        s = s[:-4]
    # scp-style uses ':' before the path; normalize it to '/' then take the last segment
    last = s.replace(":", "/").rstrip("/").split("/")[-1]
    return last or None


def _git_remote_url():
    """origin remote URL via git, or None if unavailable (no repo / no remote / git missing)."""
    try:
        proc = subprocess.run(["git", "remote", "get-url", "origin"],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def resolve_repo_label(args, read_claude_md=_read_repo_claude_md, remote_url_fn=_git_remote_url):
    """Resolve this repo's loop label as 'repo:<name>'. --repo > linear_repo: hint > git remote."""
    name = args.repo
    if name is None:
        for line in read_claude_md().splitlines():
            if line.strip().lower().startswith("linear_repo:"):
                name = line.split(":", 1)[1].strip()
                break
    if name is None:
        name = _repo_name_from_url(remote_url_fn())
    if not name:
        raise SystemExit(
            "Cannot resolve repo: pass --repo, set 'linear_repo:' in the repo CLAUDE.md, "
            "or run from a repo with an 'origin' git remote."
        )
    return f"repo:{name}"


WORK_BRANCH_PREFIXES = ("feat/", "fix/")


def _current_branch():
    """Current branch name, or None / 'HEAD' if detached/unavailable."""
    try:
        proc = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _default_branch():
    """Repo default branch (origin/HEAD target), or None."""
    try:
        proc = subprocess.run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip().split("/", 1)[-1]  # strip 'origin/'
    return None


def _unmerged_release_branches(default_branch):
    """origin release/* branches not merged into the default branch (basenames), name-sorted."""
    try:
        proc = subprocess.run(
            ["git", "branch", "-r", "--no-merged", f"origin/{default_branch}",
             "--list", "origin/release/*"],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    names = []
    for line in proc.stdout.splitlines():
        ref = line.strip()
        if ref.startswith("origin/"):
            names.append(ref[len("origin/"):])
    return sorted(names)


def resolve_base(args, read_claude_md=_read_repo_claude_md,
                 current_branch_fn=_current_branch,
                 default_branch_fn=_default_branch,
                 unmerged_releases_fn=_unmerged_release_branches,
                 emit=None):
    """Resolve the loop's base branch (work-branch base + PR base). See design spec §3.1."""
    # 1. explicit flag
    if args.base:
        return args.base
    # 2. loop_base: hint in CLAUDE.md
    for line in read_claude_md().splitlines():
        if line.strip().lower().startswith("loop_base:"):
            val = line.split(":", 1)[1].strip()
            if val:
                return val
    # 3. current checked-out branch, if it's a usable integration branch
    cur = current_branch_fn()
    if cur and cur != "HEAD" and not cur.startswith(WORK_BRANCH_PREFIXES):
        return cur
    # 4. fallback: default branch, rescued by a lone unmerged release/* (logged)
    default = default_branch_fn() or "main"
    releases = unmerged_releases_fn(default)
    if len(releases) == 1:
        if emit:
            emit(f"base: auto-selected {releases[0]} (only unmerged release/* branch)")
        return releases[0]
    return default


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


def run_triage(project, label, repo_label, runner):
    res = runner(build_claude_cmd(
        TRIAGE_PROMPT.format(project=project, label=label, repo_label=repo_label), "sonnet"), 300)
    if res.timed_out or res.returncode != 0:
        raise SystemExit("Triage call failed.")
    return parse_triage_result(res.result_text)


def main(argv, runner=subprocess_runner, triage_fn=run_triage, guard_fn=feasibility_guard):
    args = parse_args(argv)

    if args.detach:
        pid, log_path = _spawn_detached(argv)
        print(f"Loop started (pid {pid}).")
        print(f"Watch: tail -f {log_path}")
        return 0

    models = default_models()
    timeouts = default_timeouts()
    efforts = default_efforts()

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
        repo_label = None
    else:
        repo_label = resolve_repo_label(args)
        triage = triage_fn(project, args.label, repo_label, runner)

    wave = triage["wave"][: args.limit] if args.limit else triage["wave"]

    base = resolve_base(args, emit=lambda m: print(m, flush=True))

    if args.dry_run:
        filt = repo_label if repo_label else "(none — explicit tickets)"
        print(f"Project: {project}. Repo filter: {filt}. Wave ({len(wave)}): {[t['id'] for t in wave]}")
        print(f"Base branch: {base}")
        for t in wave:
            for step_name in ("implementit", "shipit", "reviewit"):
                suffix = f" --base {base}" if (base and step_name in ("implementit", "shipit")) else ""
                cmd = build_claude_cmd(f"/personal:{step_name} {t['id']}{suffix}", models[step_name], effort=efforts.get(step_name))
                print("  would run:", " ".join(cmd))
            print(f"  then loop: reviewit ↔ addressit up to {args.max_rounds} round(s) "
                  f"(re-review model {models['reviewit_rereview']}, effort {efforts.get('reviewit_rereview')})")
            if args.merge:
                cmd = build_claude_cmd(f"/personal:mergeit {t['id']}", models["mergeit"], effort=efforts.get("mergeit"))
                print("  would run:", " ".join(cmd))
            else:
                print("  then stop on approval → READY_FOR_REVIEW (merge disabled; pass --merge to auto-merge)")
        print(format_summary([], triage["held"]))
        return 0

    def emit(msg):
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

    emit(f"wave: {len(wave)} ticket(s)")
    results = []
    for i, t in enumerate(wave, 1):
        emit(f"[{i}/{len(wave)}] {t['id']}")
        r = run_ticket_pipeline(t, runner, models, timeouts, max_rounds=args.max_rounds, efforts=efforts, emit=emit, merge=args.merge, base=base)
        if r.disposition == "NEEDS_HUMAN":
            emit(f"{r.ticket_id} → NEEDS_HUMAN: {r.reason}")
        elif r.failed_step:
            emit(f"{r.ticket_id} → FAILED at {r.failed_step}")
        else:
            emit(f"{r.ticket_id} → {r.disposition}")
        results.append(r)
    print(format_summary(results, triage["held"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
