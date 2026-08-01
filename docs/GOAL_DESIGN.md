# Designing verifiable goals

A useful goal is an executable contract, not an aspiration.

## Required fields

### Objective

Describe the real-world outcome in one sentence. Use a verb and an observable result.

Weak: “Improve Medusa.”

Strong: “Take one open Medusa issue without an implementation PR through bounded implementation, passing qualification, merge to main, and evidence-backed closure.”

### Completion criteria

Each criterion must be independently falsifiable. Prefer artifact, state, test, or external observation criteria.

Good criteria:

- PR exists and links the issue;
- exact targeted and workspace validation commands pass;
- all required checks are green;
- no review thread remains actionable;
- PR is merged into main;
- issue is closed with evidence.

Bad criteria:

- code looks good;
- probably finished;
- most tests pass;
- should work.

### Evidence

Name what proves the criterion: commit SHA, PR number, workflow run, test output, screenshot, artifact digest, live transcript/audio result, or user acceptance.

### Exclusions

State what the goal must not expand into. This prevents an agent from turning a bounded issue into a repository rewrite.

### Confidence threshold

Use 0.85 for ordinary implementation goals and 0.90–0.95 for security, release, or live-integration work. The threshold is an additional gate, never a substitute for missing evidence.

## One-item execution rule

Only one work item should be `active`. A verifier selects the next action from remaining criteria and priority. This reduces state drift and makes failure attribution precise.

## Failure handling

Record the first complete failure set before editing. Group failures by root cause. Do not rerun an unchanged command merely to seek a different result unless the failure is explicitly classified as flaky or resource-dependent.

## Closure rule

Implementation complete, PR merged, and issue closed are three separate states. A goal that requires all three remains incomplete until all three have evidence.
