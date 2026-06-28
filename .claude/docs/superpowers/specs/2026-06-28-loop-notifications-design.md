# Loop Notifications — Pluggable `--notify` (macOS default, Pushover opt-in) (Design Spec)

- **Date:** 2026-06-28
- **Status:** Approved design (brainstorming output)
- **Repo:** `claude-skills` (the `personal` plugin)
- **Linear ticket:** none (exploratory personal work)

## Summary

The autonomous loop (`plugins/personal/scripts/loop.py`) currently reports progress only to
stdout (the detached run log). There is no out-of-band signal when a long-running, detached loop
makes progress or finishes — you have to `tail -f` the log.

This change wires up the existing **dead `--notify` flag** into a small **pluggable notifier**.
A notification fires **as each ticket finishes** (with its final disposition) and **once more at
the end of the whole run**. The backend is selectable: bare `--notify` posts a native **macOS**
notification (the default); `--notify pushover` routes to **Pushover** instead. Notifications are
strictly best-effort — a missing backend, missing credentials, or any send error **never affects
the loop**.

## Context

`parse_args` already declares `p.add_argument("--notify", action="store_true")` (loop.py:328), but
`args.notify` is **never read** anywhere — it is a dead placeholder. The original loop design
(`2026-06-24-implementation-loop-design.md`) reserved `--notify` for "the end-of-run Pushover
ping … acceptable to defer to a follow-up." This is that follow-up, generalized to a pluggable
mechanism rather than Pushover-only.

The loop's per-ticket results flow through `main`'s wave loop, where each ticket's `TicketResult`
is appended to `results` and a live `emit(...)` line is printed. Terminal dispositions are
`MERGED`, `READY_FOR_REVIEW`, `NEEDS_HUMAN`, and `FAILED` (the last carries a `failed_step`). The
end-of-run picture is rendered by `format_summary`. Both of these are the natural fire points.

An existing project — `~/projects/sentry-pushover-relay` — already uses the env var names
`PUSHOVER_APP_TOKEN` / `PUSHOVER_USER_KEY` and POSTs to `https://api.pushover.net/1/messages.json`.
This spec reuses those exact names for consistency.

## Key decisions (from brainstorming)

1. **Repurpose `--notify`, don't add a new flag.** The dead `--notify` becomes the notification
   switch. No separate `--pushover` flag.
2. **`--notify` is a pluggable backend selector, not a boolean.** `argparse` with
   `nargs="?", const="macos", default=None`:
   - flag **absent** → `None` → no notifications (unchanged current behavior)
   - `--notify` (bare) → `"macos"`
   - `--notify pushover` → `"pushover"`
3. **macOS native notification is the default backend.** The loop is typically run detached on the
   user's Mac, so a native banner is the lowest-friction default. Pushover is the opt-in remote
   path for when away from the machine.
4. **Extensibility is a first-class goal.** Backends live in a `NOTIFIERS` registry (name →
   callable). Adding a future backend (Slack, email, …) is a single registry entry — no changes to
   the fire sites or dispatch.
5. **Silent failure is guaranteed at the dispatch boundary.** `notify(...)` wraps every backend
   call in `try/except Exception: pass`. A missing backend, an off-macOS host, missing Pushover
   env vars, or a network error all degrade to a no-op. Notifications can never raise into the
   loop.
6. **Flat priority.** Every notification sends at the backend's normal priority. No
   disposition-based urgency mapping (rejected as unnecessary; the status is in the title/body).
7. **No new dependencies.** macOS uses `osascript` (already present on macOS); Pushover uses
   stdlib `urllib`. `loop.py` stays stdlib-only.
8. **Unknown backend name is a soft warning, not a failure.** `--notify slack` (unregistered)
   prints one non-fatal warning line at startup and then no-ops for the run — typos surface
   without breaking anything.

## Behavior

`--notify` (default off). When set to a known backend, the loop sends:

- **Per ticket** — immediately after each ticket's `TicketResult` is produced in the wave loop,
  for **every** disposition (`MERGED`, `READY_FOR_REVIEW`, `NEEDS_HUMAN`, `FAILED`). Title encodes
  ticket id + outcome; body carries the supporting detail (reason / PR URL / cost).
- **End of run** — once after the wave completes (alongside `format_summary`). Title encodes the
  ticket count; body is a per-disposition tally. Sent even when the wave was empty (a "0 ticket(s)"
  ping confirms the run executed).

Notifications fire **only on real runs**. `--dry-run` and `--check` return before the wave
executes and send nothing. `--detach` carries the flag (and its optional value) through to the
detached child unchanged (`_detached_argv` only strips `--detach`).

## Notifier abstraction

All new code lives in `plugins/personal/scripts/loop.py`.

```python
def _applescript_quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

def _macos_notify(title, message, run=subprocess.run):
    # Off-macOS / missing osascript → raises → swallowed by notify().
    script = f"display notification {_applescript_quote(message)} with title {_applescript_quote(title)}"
    run(["osascript", "-e", script], capture_output=True, timeout=10)

def _pushover_notify(title, message, urlopen=urllib.request.urlopen):
    token = os.environ.get("PUSHOVER_APP_TOKEN")
    user = os.environ.get("PUSHOVER_USER_KEY")
    if not token or not user:
        return  # missing creds → silent no-op
    data = urllib.parse.urlencode(
        {"token": token, "user": user, "title": title, "message": message}
    ).encode()
    urlopen(urllib.request.Request("https://api.pushover.net/1/messages.json", data=data), timeout=10)

NOTIFIERS = {"macos": _macos_notify, "pushover": _pushover_notify}

def notify(backend, title, message, notifiers=NOTIFIERS):
    if not backend:
        return
    fn = notifiers.get(backend)
    if fn is None:
        return
    try:
        fn(title, message)
    except Exception:
        pass  # notifications must NEVER affect the loop
```

The `run=` / `urlopen=` injection points keep the backends unit-testable without shelling out or
hitting the network; `notifiers=` keeps `notify` testable with a capture dict.

## Message builders

```python
def _ticket_notification(r):
    status = f"FAILED at {r.failed_step}" if r.failed_step else (r.disposition or r.review_status or "done")
    title = f"Loop: {r.ticket_id} → {status}"
    parts = [p for p in (r.reason, r.pr_url) if p]
    cost = _ticket_cost(r)
    if cost:
        parts.append(f"${cost:.4f}")
    return title, " — ".join(parts) or status

def _summary_notification(results):
    counts = {}
    for r in results:
        key = "FAILED" if r.failed_step else (r.disposition or "?")
        counts[key] = counts.get(key, 0) + 1
    title = f"Loop finished: {len(results)} ticket(s)"
    body = ", ".join(f"{k}: {v}" for k, v in counts.items()) or "no tickets"
    return title, body
```

## Code touch points (all in `plugins/personal/scripts/loop.py`)

1. **Imports:** add `import urllib.request` and `import urllib.parse` (top of file).
2. **`parse_args`:** replace the dead boolean with
   `p.add_argument("--notify", nargs="?", const="macos", default=None, help=...)`. Help text names
   the two backends and the `PUSHOVER_APP_TOKEN`/`PUSHOVER_USER_KEY` requirement, and notes unknown
   backends no-op.
3. **New module-level code:** `_applescript_quote`, `_macos_notify`, `_pushover_notify`,
   `NOTIFIERS`, `notify`, `_ticket_notification`, `_summary_notification` (as above).
4. **`main`:** accept a `notify_fn=notify` parameter (DI, matching the existing
   `runner`/`triage_fn`/`guard_fn` style). After resolving `args.notify`, if it is a non-`None`
   value not in `NOTIFIERS`, `emit`/print one warning line (e.g.
   `notify: unknown backend '<x>' — notifications disabled for this run`) and treat as disabled for
   the rest of the run. In the wave loop, after `results.append(r)`, call
   `notify_fn(backend, *_ticket_notification(r))`. After the loop and `format_summary`, call
   `notify_fn(backend, *_summary_notification(results))`.
5. **`--dry-run` preview:** add a single line reflecting the selected backend when `args.notify` is
   set (e.g. `Notifications: macos (per ticket + end of run)`), so the preview shows intent. No
   notification is actually sent in dry-run.
6. **No change** to `run_ticket_pipeline`, `format_summary`, the triage/guard paths, or any command
   `.md` file.

## Reporting / UX

- **macOS:** a Notification Center banner per ticket (title `Loop: NEU-350 → READY_FOR_REVIEW`,
  body with PR + cost) and one at the end (`Loop finished: 3 ticket(s)` / `MERGED: 2, NEEDS_HUMAN: 1`).
- **Pushover:** the same title/body delivered to the Pushover app via the relay's credentials.
- **Unknown backend:** one stderr/emit warning at startup; loop proceeds with notifications off.

## Testing

`test_loop.py` (unittest). Run from `plugins/personal/scripts/` with `python -m unittest test_loop`.

**New tests:**
- `parse_args`: `--notify` absent → `args.notify is None`; bare `--notify` → `"macos"`;
  `--notify pushover` → `"pushover"`.
- `notify` dispatch: `backend=None` → no call; unknown backend → no call; known backend → backend
  fn invoked once with `(title, message)`; a backend fn that raises → `notify` returns without
  raising and the exception is swallowed.
- `_pushover_notify`: with `PUSHOVER_APP_TOKEN`/`PUSHOVER_USER_KEY` unset (monkeypatched out) →
  injected `urlopen` is **not** called; with both set → `urlopen` called once with a `Request`
  whose URL is the Pushover endpoint and whose body contains the token/user/title/message.
- `_macos_notify`: injected `run` receives an `osascript` argv whose `-e` script contains the
  AppleScript-quoted title and message; `_applescript_quote` escapes embedded `"` and `\`.
- `_ticket_notification`: FAILED (title includes `FAILED at <step>`), NEEDS_HUMAN (reason in body),
  MERGED / READY_FOR_REVIEW (PR URL + `$cost` in body when present).
- `_summary_notification`: counts tally per disposition; empty `results` → `0 ticket(s)` /
  `no tickets`.
- `main` integration (injected `notify_fn` capturing calls, scripted `runner`/`triage`/`guard`):
  - `--notify` set → exactly one ticket-notification per wave ticket **plus** one end-of-run
    notification.
  - no `--notify` → zero notify calls.
  - `--notify` with `--dry-run` → zero notify calls.
  - `--notify bogus` → one warning emitted, zero notify calls.

## Out of scope

- Disposition-based priority/urgency mapping (decided: flat).
- Backends beyond macOS and Pushover (Slack, email, webhook) — the registry makes them trivial to
  add later; none are built now (YAGNI).
- Per-step (mid-pipeline) notifications — only ticket-finish and run-finish fire.
- A `CLAUDE.md` hint to set a default backend per repo — the flag suffices.
- Any change to the review↔address state machine or `mergeit`.

## Open items / deferred

- README: document the repurposed `--notify` flag, its `macos`/`pushover` backends, the
  `PUSHOVER_APP_TOKEN`/`PUSHOVER_USER_KEY` env vars, and the fire points (per ticket + end of run)
  alongside the existing loop flags.
- Whether a future `terminal-notifier` backend (richer macOS notifications, sounds/actions) is
  worth adding — revisit only if the plain `osascript` banner proves insufficient.
