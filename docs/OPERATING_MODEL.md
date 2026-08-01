# Outcome OS operating model

## The implicit objective

Build a trustworthy personal AI delivery system that can move from intent to verified outcome across a large software portfolio with minimal repeated supervision.

The repeated pattern is not merely “write code.” It is:

- preserve the original goal across long executions;
- select the right next unit of work;
- complete one bounded item at a time;
- inspect failures rather than restarting blindly;
- distinguish implementation from qualification;
- require concrete evidence before declaring completion;
- merge and close the administrative loop.

## Control loop

```text
Observe → Select → Bound → Execute → Validate → Verify → Merge/Close → Learn
              ↑                         |             |
              └──── remaining criteria ┘             └─ evidence ledger
```

### Observe

Portfolio OS, GitHub, CI, and local repository state supply evidence. Outcome OS never treats stale prose as current state.

### Select

Choose one high-value item with no conflicting implementation already active. Stable IDs prevent duplicate execution.

### Bound

Translate the issue into measurable criteria, required evidence, checks, exclusions, and stop conditions.

### Execute

An AI agent or human performs exactly one concrete next action. Work remains visible as `pending`, `active`, `blocked`, `done`, or `skipped`.

### Validate

Run targeted tests first, then the relevant repository-wide qualification. Record exact commands, return codes, and bounded output.

### Verify

The deterministic gate evaluates the complete original goal. Model-generated confidence can supplement evidence but cannot override missing criteria, checks, work, or blockers.

### Merge and close

Merge only after required checks and review gates pass. Close the linked issue only when the merge and issue-specific evidence are present.

### Learn

Keep the ledger. Feed recurring blockers, duplicate work, and qualification boundaries back into Portfolio OS and PM Command Center.

## Roles

| Role | Responsibility |
|---|---|
| Goal owner | Defines objective, exclusions, confidence threshold, and final business outcome |
| Outcome OS | Owns state, ordering, evidence, verification, blockers, and audit integrity |
| Execution agent | Performs the current bounded action and reports exact changes/results |
| External verifier | GitHub, CI, tests, users, or live systems that provide independent evidence |
| Portfolio OS | Discovers, scores, and prioritizes cross-repository opportunities |
| PM Command Center | Produces governance artifacts for risks, decisions, milestones, closure, and benefits |

## Escalation rules

Open a blocker instead of looping when:

- credentials or a required permission are unavailable;
- an external workflow is pending beyond the current execution window;
- the acceptance criterion requires physical, live, or user-provided evidence;
- the requested action conflicts with branch protection or a safety policy;
- a linker/resource boundary prevents authoritative qualification;
- requirements conflict or materially expand beyond the bounded issue.

A blocker is resolved only with a recorded resolution. “Tried again” is not a resolution.

## Weekly portfolio workflow

1. Refresh Portfolio OS and inspect the generated backlog.
2. Import stable backlog items into one or more Outcome OS goals.
3. Keep each active goal bounded to one project outcome.
4. Run work/verify cycles; attach GitHub and CI evidence.
5. Generate the dashboard for active goals.
6. Review blockers and decisions.
7. Close completed goals and feed lessons back into portfolio policy.

## Success metrics

- percentage of goals completed with all evidence gates satisfied;
- median human interventions per completed goal;
- reopened issue rate after AI-assisted closure;
- CI retry rate without code change;
- time from issue selection to verified merge;
- percentage of blockers explicitly recorded before stopping;
- duplicate work avoided through stable IDs and portfolio import.
