# GitHub CLI convention

**Every GitHub operation these commands perform goes through the `gh` CLI.** Not a GitHub MCP
server, not the REST API via `curl`, not the web UI.

This is a hard rule, not a preference, and it is written down because nothing in the command bodies
enforced it before: they *name* `gh` commands, but an agent running in a workspace that happens to
have a GitHub MCP configured could reach for `mcp__github__*` tools instead and still look like it
was doing the right thing.

## Why

- **`gh` is the only path present everywhere these commands run** — every dev machine and the Coder
  workspace, installed and authenticated. A GitHub MCP is configured per-project and is absent from
  most of them. A command that reaches for one works in the repo where it happens to be configured
  and stalls in every other.
- **The failure is worst where it is least visible.** Under `plugins/personal/scripts/loop.py` the
  steps run headlessly with `--permission-mode bypassPermissions`. A missing MCP tool there does not
  prompt; it produces a step that never emits its `STATUS:` sentinel, which the loop records as
  `FAILED` with no useful diagnostic.
- **`gh --json`/`--jq` output is deterministic and greppable.** The commands parse it directly
  (`gh pr view PR_NUMBER --json baseRefOid --jq '.baseRefOid'`). MCP tool output shapes are not
  guaranteed stable across server versions.

## Rules

1. Use `gh` for every read and write against GitHub — PR listing, creation, diffs, comments, checks,
   merges, and branch cleanup.
2. **Never** substitute a GitHub MCP tool, even when one is available in the session and looks more
   convenient. Availability is not a reason to use it.
3. If `gh` is missing or unauthenticated, **stop and say so**. Do not fall back to an MCP server, and
   do not fall back to raw API calls. The user fixes the tooling; the command does not route around it.
4. **Keep `gh` invocations unpiped** where a `settings.json` `allow` rule is meant to match them —
   those rules are prefix matches, so `gh pr merge 12 --squash` matches and
   `gh pr merge 12 --squash | tail -5` may not. Capture output and process it in a separate step
   instead.

## The `gh` surface these commands use

| Command | Uses |
|---|---|
| `/personal:shipit` | `gh pr create` |
| `/personal:mergeit` | `gh pr view --comments`, `gh pr checks`, `gh pr checks --watch`, `gh pr merge` |
| `/personal:reviewit` | `gh pr view`, `gh pr diff`, `gh pr view --json baseRefOid/headRefOid`, `gh pr comment` |
| `/personal:addressit` | `gh pr view`, `gh pr diff`, `gh pr checkout`, `gh pr comment` |
| `pr-resolution-convention.md` | `gh pr list --state open --json number,headRefName,title` |

Anything added later belongs in this table.

Note that **CI detection is deliberately not a `gh` call** — `/personal:mergeit` reads
`.github/workflows/` from disk with `grep -r`, because `gh pr checks` cannot distinguish "this repo
has no CI" from "the check has not registered yet". That is a correctness decision, not an exception
to this convention.
