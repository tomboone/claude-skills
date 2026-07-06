# Migrate the personal plugin off Superpowers to Matt Pocock's skill suite

The `personal` plugin's ticket pipeline (`projectit` → `planit` → `implementit` → `shipit` → `reviewit` ↔ `addressit` → `mergeit`) was built entirely on `superpowers:*` skills (`brainstorming`, `writing-plans`, `subagent-driven-development`, `requesting-code-review`, `receiving-code-review`). That stack proved too slow for how this pipeline is actually used — e.g. implementation via `subagent-driven-development`'s fresh-subagent-per-task plus two-stage-per-task review routinely took close to an hour even when the plan already spelled out the code to write.

We're replacing each Superpowers dependency with the equivalent Matt Pocock skill, trading per-step isolation/review depth for speed, on the view that this pipeline's real safety net is the post-ship review gate (`reviewit` ↔ `addressit`, unchanged) rather than in-flight choreography:

- `projectit` Phase 1 and `planit` Step 4: `superpowers:brainstorming` (+ `writing-plans` for `planit`) → `/grilling` + `/domain-modeling`, producing a spec and `CONTEXT.md`/ADR updates instead of a step-by-step plan with pre-written code.
- `implementit`: `superpowers:subagent-driven-development` → `/implement`, a single direct pass instead of fresh-subagent-per-task with two-stage review.
- `reviewit`: `superpowers:requesting-code-review` → `/review`.
- `addressit`: `superpowers:receiving-code-review` → inlined instructions directly in `addressit.md` (no Matt Pocock equivalent exists for "verify each finding, fix the valid ones, push back with reasoning on the rest").
- `shipit` and `mergeit` are unaffected — neither ever depended on Superpowers.

See [[0002-two-pass-code-review-is-intentional]] and [[0003-planit-keeps-its-per-ticket-gate]] for two non-obvious consequences of this migration.
