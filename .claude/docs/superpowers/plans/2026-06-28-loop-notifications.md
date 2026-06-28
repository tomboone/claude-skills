# Loop Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the loop's dead `--notify` flag into a pluggable notifier that fires as each ticket finishes and once at the end of the run, defaulting to a native macOS banner with `--notify pushover` as an opt-in backend.

**Architecture:** All changes are in `plugins/personal/scripts/loop.py` (plus its `test_loop.py`). A `NOTIFIERS` registry maps a backend name to a `(title, message)` callable; a single `notify()` dispatcher looks up the backend and swallows every exception so notifications can never affect the loop. `main()` resolves the backend from `--notify`, fires a per-ticket notification after each `TicketResult`, and a summary notification after the wave.

**Tech Stack:** Python 3 standard library only (`subprocess` + `osascript` for macOS, `urllib` for Pushover). Tests use `unittest`.

## Global Constraints

- **Stdlib only** — no new dependencies. macOS uses `osascript`; Pushover uses `urllib`.
- **Silent failure is mandatory** — a missing backend, missing creds, off-macOS host, or any send error degrades to a no-op. Notifications must NEVER raise into the loop.
- **Pushover env var names (verbatim):** `PUSHOVER_APP_TOKEN`, `PUSHOVER_USER_KEY` (matches the existing `sentry-pushover-relay`).
- **Pushover endpoint (verbatim):** `https://api.pushover.net/1/messages.json`.
- **Backend names:** `macos` (default for bare `--notify`), `pushover`.
- **Flat priority** — no disposition-based urgency.
- **Run tests** from `plugins/personal/scripts/` with `python3 -m unittest test_loop`.
- **Commits:** Conventional Commits, imperative subject ≤72 chars. No `Co-Authored-By` trailer. No footer in commit messages.
- All new module-level functions must be defined **before** `main()` (so `main`'s `notify_fn=notify` default resolves).

---

### Task 1: `--notify` becomes a backend selector

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (`parse_args`, line ~328)
- Test: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `parse_args(argv).notify` → `None` (absent), `"macos"` (bare `--notify`), or the given value (e.g. `"pushover"`).

- [ ] **Step 1: Write the failing test**

Add to `test_loop.py`:

```python
class TestNotifyArg(unittest.TestCase):
    def test_absent_is_none(self):
        self.assertIsNone(loop.parse_args([]).notify)

    def test_bare_flag_defaults_macos(self):
        self.assertEqual(loop.parse_args(["--notify"]).notify, "macos")

    def test_explicit_backend(self):
        self.assertEqual(loop.parse_args(["--notify", "pushover"]).notify, "pushover")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_loop.TestNotifyArg -v`
Expected: FAIL — bare `--notify` yields `True` (current `store_true`), not `"macos"`.

- [ ] **Step 3: Replace the dead flag in `parse_args`**

In `loop.py`, replace the line:

```python
    p.add_argument("--notify", action="store_true")
```

with:

```python
    p.add_argument(
        "--notify", nargs="?", const="macos", default=None,
        help="Notify as each ticket finishes and at end of run. Bare --notify uses a "
             "macOS banner; '--notify pushover' uses Pushover (needs PUSHOVER_APP_TOKEN "
             "and PUSHOVER_USER_KEY). Unknown backends are ignored.",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest test_loop.TestNotifyArg -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(loop): make --notify a backend selector (macos default)"
```

---

### Task 2: AppleScript quoting + macOS notifier

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (new module-level functions, placed after `format_summary` / before `TRIAGE_PROMPT`)
- Test: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: `subprocess` (already imported).
- Produces:
  - `_applescript_quote(s) -> str` — returns `s` wrapped in double quotes with `\` and `"` escaped.
  - `_macos_notify(title, message, run=subprocess.run) -> None` — shells `osascript -e '<script>'`.

- [ ] **Step 1: Write the failing test**

Add to `test_loop.py`:

```python
class TestApplescriptQuote(unittest.TestCase):
    def test_wraps_in_quotes(self):
        self.assertEqual(loop._applescript_quote("hi"), '"hi"')

    def test_escapes_double_quote_and_backslash(self):
        # input chars: a " b \ c  ->  "a\"b\\c"
        self.assertEqual(loop._applescript_quote('a"b\\c'), '"a\\"b\\\\c"')


class TestMacosNotify(unittest.TestCase):
    def test_builds_osascript_command(self):
        seen = {}
        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return None
        loop._macos_notify("My Title", "My Body", run=fake_run)
        cmd = seen["cmd"]
        self.assertEqual(cmd[0], "osascript")
        self.assertEqual(cmd[1], "-e")
        self.assertIn("display notification", cmd[2])
        self.assertIn('"My Body"', cmd[2])
        self.assertIn('"My Title"', cmd[2])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_loop.TestApplescriptQuote test_loop.TestMacosNotify -v`
Expected: FAIL with `AttributeError: module 'loop' has no attribute '_applescript_quote'`.

- [ ] **Step 3: Write the implementation**

In `loop.py`, after `format_summary` (ends ~line 281) and before `TRIAGE_PROMPT`, add:

```python
def _applescript_quote(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _macos_notify(title, message, run=subprocess.run):
    # Off-macOS or missing osascript → raises → swallowed by notify().
    script = f"display notification {_applescript_quote(message)} with title {_applescript_quote(title)}"
    run(["osascript", "-e", script], capture_output=True, timeout=10)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest test_loop.TestApplescriptQuote test_loop.TestMacosNotify -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(loop): add macOS osascript notifier backend"
```

---

### Task 3: Pushover notifier

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (add `urllib` imports near the top; add `_pushover_notify` after `_macos_notify`)
- Test: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: `os` (imported), `urllib.request`, `urllib.parse`.
- Produces: `_pushover_notify(title, message, urlopen=urllib.request.urlopen) -> None` — POSTs to the Pushover endpoint when both env vars are set; no-ops (no POST) when either is missing.

- [ ] **Step 1: Write the failing test**

Add to `test_loop.py`:

```python
class TestPushoverNotify(unittest.TestCase):
    def test_no_post_when_env_missing(self):
        import unittest.mock
        called = []
        def fake_urlopen(req, **kw):
            called.append(req)
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            loop._pushover_notify("t", "m", urlopen=fake_urlopen)
        self.assertEqual(called, [])

    def test_posts_when_env_present(self):
        import unittest.mock
        captured = {}
        def fake_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["data"] = req.data
        env = {"PUSHOVER_APP_TOKEN": "tok", "PUSHOVER_USER_KEY": "usr"}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            loop._pushover_notify("Title", "Body", urlopen=fake_urlopen)
        self.assertEqual(captured["url"], "https://api.pushover.net/1/messages.json")
        body = captured["data"].decode()
        self.assertIn("token=tok", body)
        self.assertIn("user=usr", body)
        self.assertIn("Title", body)
        self.assertIn("Body", body)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_loop.TestPushoverNotify -v`
Expected: FAIL with `AttributeError: module 'loop' has no attribute '_pushover_notify'`.

- [ ] **Step 3: Write the implementation**

In `loop.py`, add the imports near the existing top-of-file imports (after `import subprocess`):

```python
import urllib.parse
import urllib.request
```

Then add after `_macos_notify`:

```python
def _pushover_notify(title, message, urlopen=urllib.request.urlopen):
    token = os.environ.get("PUSHOVER_APP_TOKEN")
    user = os.environ.get("PUSHOVER_USER_KEY")
    if not token or not user:
        return  # missing creds → silent no-op
    data = urllib.parse.urlencode(
        {"token": token, "user": user, "title": title, "message": message}
    ).encode()
    req = urllib.request.Request("https://api.pushover.net/1/messages.json", data=data)
    urlopen(req, timeout=10)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest test_loop.TestPushoverNotify -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(loop): add Pushover notifier backend"
```

---

### Task 4: `NOTIFIERS` registry + `notify` dispatch

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (add after `_pushover_notify`)
- Test: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: `_macos_notify`, `_pushover_notify`.
- Produces:
  - `NOTIFIERS` — dict `{"macos": _macos_notify, "pushover": _pushover_notify}`.
  - `notify(backend, title, message, notifiers=NOTIFIERS) -> None` — no-op for falsy/unknown backend; otherwise calls the backend, swallowing all exceptions.

- [ ] **Step 1: Write the failing test**

Add to `test_loop.py`:

```python
class TestNotifyDispatch(unittest.TestCase):
    def test_none_backend_no_call(self):
        calls = []
        loop.notify(None, "t", "m", notifiers={"macos": lambda *a: calls.append(a)})
        self.assertEqual(calls, [])

    def test_unknown_backend_no_call(self):
        calls = []
        loop.notify("nope", "t", "m", notifiers={"macos": lambda *a: calls.append(a)})
        self.assertEqual(calls, [])

    def test_known_backend_called(self):
        calls = []
        loop.notify("macos", "t", "m", notifiers={"macos": lambda *a: calls.append(a)})
        self.assertEqual(calls, [("t", "m")])

    def test_swallows_backend_exception(self):
        def boom(*a):
            raise RuntimeError("x")
        loop.notify("macos", "t", "m", notifiers={"macos": boom})  # must not raise

    def test_registry_has_builtin_backends(self):
        self.assertIn("macos", loop.NOTIFIERS)
        self.assertIn("pushover", loop.NOTIFIERS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_loop.TestNotifyDispatch -v`
Expected: FAIL with `AttributeError: module 'loop' has no attribute 'notify'`.

- [ ] **Step 3: Write the implementation**

In `loop.py`, after `_pushover_notify`, add:

```python
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

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest test_loop.TestNotifyDispatch -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(loop): add notifier registry and silent dispatch"
```

---

### Task 5: Notification message builders

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (add after `notify`; uses existing `_ticket_cost`)
- Test: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: `TicketResult`, `_ticket_cost` (existing, line ~222).
- Produces:
  - `_ticket_notification(r) -> (title, message)` — title `Loop: <id> → <status>` where status is `FAILED at <step>` for failures else the disposition; message joins reason / PR URL / `$cost`.
  - `_summary_notification(results) -> (title, message)` — title `Loop finished: <N> ticket(s)`; message is a per-disposition tally (`no tickets` when empty).

- [ ] **Step 1: Write the failing test**

Add to `test_loop.py`:

```python
class TestNotificationMessages(unittest.TestCase):
    def test_failed_ticket_title_and_step(self):
        r = loop.TicketResult("A-1", True, None, None, "shipit",
                              "shipit produced no PR URL", None, "FAILED", 0)
        title, body = loop._ticket_notification(r)
        self.assertIn("A-1", title)
        self.assertIn("FAILED at shipit", title)
        self.assertIn("shipit produced no PR URL", body)

    def test_needs_human_reason_in_body(self):
        r = loop.TicketResult("A-2", True, "https://github.com/o/r/pull/2",
                              "CHANGES_REQUESTED", None, "impasse: ...", None, "NEEDS_HUMAN", 3)
        title, body = loop._ticket_notification(r)
        self.assertIn("NEEDS_HUMAN", title)
        self.assertIn("impasse", body)

    def test_ready_for_review_includes_pr_and_cost(self):
        usage = [{"step": "implementit", "cost_usd": 1.5}]
        r = loop.TicketResult("A-3", True, "https://github.com/o/r/pull/3",
                              "APPROVED", None, None, usage, "READY_FOR_REVIEW", 1)
        title, body = loop._ticket_notification(r)
        self.assertIn("READY_FOR_REVIEW", title)
        self.assertIn("pull/3", body)
        self.assertIn("$1.5000", body)

    def test_summary_counts_by_disposition(self):
        results = [
            loop.TicketResult("A-1", True, "u", "APPROVED", None, None, None, "MERGED", 1),
            loop.TicketResult("A-2", True, "u", "APPROVED", None, None, None, "MERGED", 1),
            loop.TicketResult("A-3", True, None, None, "shipit", "x", None, "FAILED", 0),
        ]
        title, body = loop._summary_notification(results)
        self.assertIn("3 ticket(s)", title)
        self.assertIn("MERGED: 2", body)
        self.assertIn("FAILED: 1", body)

    def test_summary_empty(self):
        title, body = loop._summary_notification([])
        self.assertIn("0 ticket(s)", title)
        self.assertIn("no tickets", body)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_loop.TestNotificationMessages -v`
Expected: FAIL with `AttributeError: module 'loop' has no attribute '_ticket_notification'`.

- [ ] **Step 3: Write the implementation**

In `loop.py`, after `notify`, add:

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

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest test_loop.TestNotificationMessages -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(loop): add ticket + summary notification message builders"
```

---

### Task 6: Wire notifications into `main`

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (`main` signature + body; `--dry-run` preview)
- Test: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: `notify`, `_ticket_notification`, `_summary_notification`, `NOTIFIERS`.
- Produces: `main(argv, runner=..., triage_fn=..., guard_fn=..., notify_fn=notify)` — fires `notify_fn(backend, *_ticket_notification(r))` after each ticket and `notify_fn(backend, *_summary_notification(results))` after the wave, **only** when `backend` is a known notifier; warns once and disables on an unknown backend; never fires in `--dry-run`/`--check`.

- [ ] **Step 1: Write the failing test**

Add to `test_loop.py`:

```python
class TestMainNotify(unittest.TestCase):
    def _driving_runner(self):
        def runner(cmd, timeout):
            p = cmd[2]
            if "/personal:implementit" in p:
                return loop.InvocationResult(0, "STATUS: IMPLEMENTED", False)
            if "/personal:shipit" in p:
                return loop.InvocationResult(0, "PR https://github.com/o/r/pull/1", False)
            if "/personal:reviewit" in p:
                return loop.InvocationResult(0, "STATUS: APPROVED", False)
            return loop.InvocationResult(0, "", False)
        return runner

    def _wave(self, *ids):
        return {"project": "p", "wave": [{"id": i, "title": ""} for i in ids], "held": []}

    def test_fires_per_ticket_and_summary(self):
        calls = []
        with contextlib.redirect_stdout(io.StringIO()):
            rc = loop.main(
                ["--project", "p", "--repo", "r", "--notify"],
                runner=self._driving_runner(),
                triage_fn=lambda *a, **k: self._wave("A-1", "A-2"),
                guard_fn=lambda runner: (True, "ok"),
                notify_fn=lambda *a: calls.append(a),
            )
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 3)               # 2 per-ticket + 1 summary
        self.assertEqual(calls[-1][0], "macos")
        self.assertIn("Loop finished", calls[-1][1])

    def test_no_notify_means_no_calls(self):
        calls = []
        with contextlib.redirect_stdout(io.StringIO()):
            loop.main(
                ["--project", "p", "--repo", "r"],
                runner=self._driving_runner(),
                triage_fn=lambda *a, **k: self._wave("A-1"),
                guard_fn=lambda runner: (True, "ok"),
                notify_fn=lambda *a: calls.append(a),
            )
        self.assertEqual(calls, [])

    def test_dry_run_no_notify_calls(self):
        calls = []
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            loop.main(
                ["--project", "p", "--repo", "r", "--notify", "--dry-run"],
                runner=self._driving_runner(),
                triage_fn=lambda *a, **k: self._wave("A-1"),
                guard_fn=lambda runner: (True, "ok"),
                notify_fn=lambda *a: calls.append(a),
            )
        self.assertEqual(calls, [])
        self.assertIn("Notifications: macos", buf.getvalue())

    def test_unknown_backend_warns_and_disables(self):
        calls = []
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            loop.main(
                ["--project", "p", "--repo", "r", "--notify", "bogus"],
                runner=self._driving_runner(),
                triage_fn=lambda *a, **k: self._wave("A-1"),
                guard_fn=lambda runner: (True, "ok"),
                notify_fn=lambda *a: calls.append(a),
            )
        self.assertEqual(calls, [])
        self.assertIn("unknown backend", err.getvalue())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_loop.TestMainNotify -v`
Expected: FAIL — `main()` has no `notify_fn` parameter (`TypeError: main() got an unexpected keyword argument 'notify_fn'`).

- [ ] **Step 3: Update `main`**

In `loop.py`, change the signature:

```python
def main(argv, runner=subprocess_runner, triage_fn=run_triage, guard_fn=feasibility_guard, notify_fn=notify):
```

After `efforts = default_efforts()`, add backend resolution:

```python
    backend = args.notify
    if backend is not None and backend not in NOTIFIERS:
        print(f"notify: unknown backend {backend!r} — notifications disabled for this run", file=sys.stderr)
        backend = None
```

In the `if args.dry_run:` block, after `print(f"Base branch: {base}")`, add:

```python
        if backend:
            print(f"Notifications: {backend} (per ticket + end of run)")
```

In the wave loop, immediately after `results.append(r)`, add:

```python
        if backend:
            notify_fn(backend, *_ticket_notification(r))
```

After `print(format_summary(results, triage["held"]))`, add:

```python
    if backend:
        notify_fn(backend, *_summary_notification(results))
```

- [ ] **Step 4: Run the focused test, then the whole suite**

Run: `python3 -m unittest test_loop.TestMainNotify -v`
Expected: PASS (4 tests).

Run: `python3 -m unittest test_loop -v`
Expected: PASS (entire suite green — no regressions).

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(loop): fire notifications per ticket and at end of run"
```

---

### Task 7: Document `--notify` in the README

**Files:**
- Modify: `README.md` (usage synopsis line ~119; flag table row ~130)

**Interfaces:**
- Consumes: nothing. Documentation only.
- Produces: nothing.

- [ ] **Step 1: Update the usage synopsis**

In `README.md`, replace `[--notify]` in the synopsis (line ~119) with `[--notify [backend]]`:

```
                                 [--limit N] [--notify [backend]] [--max-rounds N] [--detach] [--merge]
```

- [ ] **Step 2: Update the flag table row**

Replace the existing `--notify` row:

```
| `--notify` | Send a single end-of-run notification. |
```

with:

```
| `--notify [backend]` | Send a notification as each ticket finishes (with its final disposition) and once at the end of the run. Bare `--notify` posts a native **macOS** banner; `--notify pushover` sends via **Pushover** (requires `PUSHOVER_APP_TOKEN` and `PUSHOVER_USER_KEY` env vars). Off by default. Missing credentials or an unknown backend fail silently — the loop is never affected. |
```

- [ ] **Step 3: Verify no stale "single end-of-run" wording remains**

Run: `grep -n "single end-of-run" README.md`
Expected: no output (the only occurrence was the row just replaced).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(loop): document pluggable --notify backends"
```

---

## Self-Review

**Spec coverage:**
- Repurpose dead `--notify` as backend selector → Task 1. ✓
- `nargs="?"`, `const="macos"`, `default=None` → Task 1. ✓
- macOS default backend (`osascript`) → Task 2. ✓
- Pushover backend, env names, endpoint, missing-creds no-op → Task 3. ✓
- `NOTIFIERS` registry + `notify` silent dispatch → Task 4. ✓
- Per-ticket + summary message builders (all dispositions, empty case) → Task 5. ✓
- `main` wiring: `notify_fn` DI, per-ticket fire, end-of-run fire, unknown-backend warning, dry-run preview line, no fire on dry-run/check → Task 6. ✓
- No new deps / stdlib only → Global Constraints + Tasks 2–3. ✓
- README documentation (deferred item in spec) → Task 7. ✓
- Detach propagation: no code change needed (`_detached_argv` only strips `--detach`); covered by existing behavior, noted in spec. ✓ (No task required — `--notify`/value pass through unchanged.)

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every test step shows the assertions.

**Type consistency:** `notify(backend, title, message, notifiers=NOTIFIERS)` is called as `notify_fn(backend, *_ticket_notification(r))` / `notify_fn(backend, *_summary_notification(results))` — both builders return a `(title, message)` tuple, matching the `(backend, title, message)` call shape. `NOTIFIERS` keys (`macos`, `pushover`) match the backend names produced by `parse_args` and checked in `main`. `_ticket_cost` is the existing helper (no redefinition). `_macos_notify(run=…)` / `_pushover_notify(urlopen=…)` injection points match their tests.
