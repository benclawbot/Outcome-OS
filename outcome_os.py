#!/usr/bin/env python3
"""Outcome OS: evidence-backed execution control for AI-assisted project work.

Standard-library only. State is local, auditable, and portable.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "1.0.0"
STATE_DIR = ".outcome-os"
STATE_FILE = "state.json"
LEDGER_FILE = "ledger.jsonl"
DASHBOARD_FILE = "dashboard.html"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "goal"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def data_dir(self) -> Path:
        return self.root / STATE_DIR

    @property
    def state_path(self) -> Path:
        return self.data_dir / STATE_FILE

    @property
    def ledger_path(self) -> Path:
        return self.data_dir / LEDGER_FILE

    @property
    def dashboard_path(self) -> Path:
        return self.data_dir / DASHBOARD_FILE

    @classmethod
    def discover(cls, start: Path | None = None) -> "Workspace":
        current = (start or Path.cwd()).resolve()
        for candidate in (current, *current.parents):
            if (candidate / STATE_DIR / STATE_FILE).exists():
                return cls(candidate)
        raise SystemExit("No Outcome OS workspace found. Run `outcome-os init ...` first.")

    @classmethod
    def at(cls, path: str | Path) -> "Workspace":
        return cls(Path(path).resolve())

    def load(self) -> dict[str, Any]:
        return read_json(self.state_path)

    def save(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        write_json_atomic(self.state_path, state)

    def append_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        previous_hash = "0" * 64
        if self.ledger_path.exists():
            lines = [line for line in self.ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                previous_hash = json.loads(lines[-1])["hash"]
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "type": event_type,
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event["hash"] = sha256_text(canonical_json(event))
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event


def criterion_record(text: str, *, criterion_id: str | None = None, min_evidence: int = 1,
                     required_checks: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "id": criterion_id or f"c-{uuid.uuid4().hex[:8]}",
        "text": text.strip(),
        "min_evidence": max(1, int(min_evidence)),
        "required_checks": sorted(set(required_checks)),
        "evidence": [],
        "status": "pending",
    }


def work_item_record(title: str, *, source: str = "manual", source_id: str | None = None,
                     priority: float = 50.0, acceptance: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "id": f"w-{uuid.uuid4().hex[:8]}",
        "title": title.strip(),
        "status": "pending",
        "priority": float(priority),
        "source": source,
        "source_id": source_id,
        "acceptance": list(acceptance),
        "notes": [],
        "started_at": None,
        "completed_at": None,
    }


def initial_state(title: str, objective: str, criteria: list[str], repo: str | None,
                  threshold: float, max_cycles: int) -> dict[str, Any]:
    now = utc_now()
    records = [criterion_record(text) for text in criteria]
    return {
        "schema_version": 1,
        "system_version": VERSION,
        "goal": {
            "id": f"g-{uuid.uuid4().hex[:10]}",
            "slug": slugify(title),
            "title": title,
            "objective": objective,
            "repository": repo,
            "status": "active",
            "confidence_threshold": threshold,
            "max_cycles": max_cycles,
            "cycle": 0,
            "created_at": now,
        },
        "criteria": records,
        "work_items": [],
        "checks": {},
        "blockers": [],
        "decisions": [],
        "latest_verdict": None,
        "created_at": now,
        "updated_at": now,
    }


def active_blockers(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [b for b in state["blockers"] if b.get("status") == "open"]


def eligible_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [item for item in state["work_items"] if item["status"] in {"pending", "active", "blocked"}],
        key=lambda item: (item["status"] != "active", -float(item.get("priority", 0)), item["title"].lower()),
    )


def criterion_evaluation(criterion: dict[str, Any], checks: dict[str, Any]) -> dict[str, Any]:
    evidence_count = len(criterion.get("evidence", []))
    evidence_ratio = min(1.0, evidence_count / max(1, int(criterion.get("min_evidence", 1))))
    required = criterion.get("required_checks", [])
    passed = sum(1 for name in required if checks.get(name, {}).get("passed") is True)
    check_ratio = 1.0 if not required else passed / len(required)
    complete = evidence_ratio >= 1.0 and check_ratio >= 1.0
    confidence = round((0.65 * evidence_ratio) + (0.35 * check_ratio), 4)
    return {
        "id": criterion["id"],
        "text": criterion["text"],
        "complete": complete,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "minimum_evidence": criterion.get("min_evidence", 1),
        "missing_checks": [name for name in required if checks.get(name, {}).get("passed") is not True],
    }


def verify_state(state: dict[str, Any]) -> dict[str, Any]:
    evaluations = [criterion_evaluation(c, state["checks"]) for c in state["criteria"]]
    criterion_confidence = sum(e["confidence"] for e in evaluations) / max(1, len(evaluations))
    unfinished = [i for i in state["work_items"] if i["status"] not in {"done", "skipped"}]
    blockers = active_blockers(state)
    checks = list(state["checks"].values())
    global_check_ratio = 1.0 if not checks else sum(1 for c in checks if c.get("passed")) / len(checks)
    confidence = round((0.8 * criterion_confidence) + (0.2 * global_check_ratio), 4)
    threshold = float(state["goal"]["confidence_threshold"])
    complete = (
        bool(evaluations)
        and all(e["complete"] for e in evaluations)
        and not unfinished
        and not blockers
        and confidence >= threshold
    )
    remaining = []
    for evaluation in evaluations:
        if not evaluation["complete"]:
            remaining.append(evaluation["text"])
    remaining.extend(f"Work item: {item['title']}" for item in unfinished)
    remaining.extend(f"Blocker: {item['text']}" for item in blockers)
    next_item = eligible_items(state)
    next_action = (
        next_item[0]["title"] if next_item else
        (remaining[0] if remaining else "No action required")
    )
    return {
        "complete": complete,
        "confidence": confidence,
        "threshold": threshold,
        "criteria": evaluations,
        "remaining_criteria": remaining,
        "unfinished_work_items": [item["id"] for item in unfinished],
        "open_blockers": [item["id"] for item in blockers],
        "next_action": next_action,
        "verified_at": utc_now(),
    }


def load_backlog_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, dict):
        for key in ("items", "backlog", "work_items", "recommendations", "tasks"):
            if isinstance(value.get(key), list):
                candidates = value[key]
                break
        else:
            candidates = []
            for nested in value.values():
                if isinstance(nested, dict):
                    try:
                        candidates.extend(load_backlog_items(nested))
                    except (TypeError, ValueError):
                        pass
    else:
        raise ValueError("Backlog must be a JSON object or list")

    normalized: list[dict[str, Any]] = []
    for raw in candidates:
        if isinstance(raw, str):
            normalized.append({"title": raw})
            continue
        if not isinstance(raw, dict):
            continue
        title = raw.get("title") or raw.get("summary") or raw.get("name") or raw.get("action")
        if not title:
            continue
        acceptance = raw.get("acceptance_criteria") or raw.get("acceptance") or []
        if isinstance(acceptance, str):
            acceptance = [acceptance]
        priority = raw.get("priority_score", raw.get("priority", 50))
        if isinstance(priority, str):
            mapping = {"critical": 100, "high": 80, "medium": 50, "low": 20}
            priority = mapping.get(priority.lower(), 50)
        try:
            priority = float(priority)
        except (TypeError, ValueError):
            priority = 50.0
        normalized.append({
            "title": str(title),
            "source_id": raw.get("id") or raw.get("stable_id"),
            "priority": priority,
            "acceptance": acceptance,
        })
    return normalized


def command_init(args: argparse.Namespace) -> int:
    workspace = Workspace.at(args.path)
    if workspace.state_path.exists() and not args.force:
        raise SystemExit(f"Workspace already exists at {workspace.data_dir}. Use --force to replace it.")
    if args.force and workspace.data_dir.exists():
        shutil.rmtree(workspace.data_dir)
    criteria = args.criterion or ["All explicitly requested deliverables exist and are usable",
                                  "All relevant tests and validation checks pass",
                                  "No unresolved blocker remains"]
    state = initial_state(args.title, args.objective, criteria, args.repo, args.threshold, args.max_cycles)
    workspace.save(state)
    workspace.append_event("goal.initialized", {"goal": state["goal"], "criteria": state["criteria"]})
    print(workspace.data_dir)
    return 0


def command_add_item(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    item = work_item_record(args.title, priority=args.priority, acceptance=args.acceptance or [])
    state["work_items"].append(item)
    workspace.save(state)
    workspace.append_event("work_item.added", item)
    print(item["id"])
    return 0


def find_record(records: list[dict[str, Any]], record_id: str, label: str) -> dict[str, Any]:
    for record in records:
        if record["id"] == record_id:
            return record
    raise SystemExit(f"Unknown {label}: {record_id}")


def command_set_item(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    item = find_record(state["work_items"], args.item_id, "work item")
    previous = item["status"]
    item["status"] = args.status
    if args.status == "active" and not item.get("started_at"):
        item["started_at"] = utc_now()
    if args.status in {"done", "skipped"}:
        item["completed_at"] = utc_now()
    if args.note:
        item.setdefault("notes", []).append({"timestamp": utc_now(), "text": args.note})
    workspace.save(state)
    workspace.append_event("work_item.status_changed", {
        "id": item["id"], "from": previous, "to": args.status, "note": args.note
    })
    return 0


def command_evidence(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    criterion = find_record(state["criteria"], args.criterion_id, "criterion")
    evidence = {
        "id": f"e-{uuid.uuid4().hex[:10]}",
        "type": args.type,
        "value": args.value,
        "source": args.source,
        "timestamp": utc_now(),
        "digest": sha256_text(args.value),
    }
    criterion["evidence"].append(evidence)
    workspace.save(state)
    workspace.append_event("criterion.evidence_added", {
        "criterion_id": criterion["id"], "evidence": evidence
    })
    print(evidence["id"])
    return 0


def command_check(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    check = {
        "name": args.name,
        "passed": args.result == "pass",
        "command": args.command,
        "details": args.details,
        "timestamp": utc_now(),
    }
    state["checks"][args.name] = check
    workspace.save(state)
    workspace.append_event("check.recorded", check)
    return 0 if check["passed"] else 1


def command_run_check(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    completed = subprocess.run(args.command, shell=True, text=True, capture_output=True)
    output = (completed.stdout + completed.stderr)[-12000:]
    check = {
        "name": args.name,
        "passed": completed.returncode == 0,
        "command": args.command,
        "details": output,
        "returncode": completed.returncode,
        "timestamp": utc_now(),
    }
    state["checks"][args.name] = check
    workspace.save(state)
    workspace.append_event("check.executed", check)
    print(output, end="" if output.endswith("\n") else "\n")
    return completed.returncode


def command_blocker(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    blocker = {
        "id": f"b-{uuid.uuid4().hex[:8]}",
        "text": args.text,
        "status": "open",
        "owner": args.owner,
        "created_at": utc_now(),
        "resolved_at": None,
    }
    state["blockers"].append(blocker)
    workspace.save(state)
    workspace.append_event("blocker.opened", blocker)
    print(blocker["id"])
    return 0


def command_resolve_blocker(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    blocker = find_record(state["blockers"], args.blocker_id, "blocker")
    blocker["status"] = "resolved"
    blocker["resolved_at"] = utc_now()
    blocker["resolution"] = args.resolution
    workspace.save(state)
    workspace.append_event("blocker.resolved", blocker)
    return 0


def command_import_portfolio(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    source = Path(args.file)
    items = load_backlog_items(read_json(source))
    existing = {(i.get("source"), i.get("source_id"), i["title"]) for i in state["work_items"]}
    added = []
    for raw in items:
        key = ("portfolio-os", raw.get("source_id"), raw["title"])
        if key in existing:
            continue
        item = work_item_record(raw["title"], source="portfolio-os", source_id=raw.get("source_id"),
                                priority=raw.get("priority", 50), acceptance=raw.get("acceptance", []))
        state["work_items"].append(item)
        added.append(item)
    workspace.save(state)
    workspace.append_event("portfolio.imported", {"source": str(source), "added": added})
    print(json.dumps({"added": len(added)}, indent=2))
    return 0


def command_verify(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    verdict = verify_state(state)
    state["latest_verdict"] = verdict
    if verdict["complete"]:
        state["goal"]["status"] = "complete"
    workspace.save(state)
    workspace.append_event("goal.verified", verdict)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0 if verdict["complete"] else 2


def command_status(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    verdict = verify_state(state)
    if args.json:
        print(json.dumps({"state": state, "verdict": verdict}, indent=2, ensure_ascii=False))
        return 0
    goal = state["goal"]
    print(f"{goal['title']} [{goal['status']}]")
    print(f"Confidence: {verdict['confidence']:.0%} / {verdict['threshold']:.0%}")
    print(f"Criteria: {sum(1 for c in verdict['criteria'] if c['complete'])}/{len(verdict['criteria'])}")
    done = sum(1 for item in state["work_items"] if item["status"] in {"done", "skipped"})
    print(f"Work: {done}/{len(state['work_items'])}")
    print(f"Blockers: {len(verdict['open_blockers'])}")
    print(f"Next: {verdict['next_action']}")
    return 0


def prompt_payload(state: dict[str, Any]) -> dict[str, str]:
    verdict = verify_state(state)
    criteria = "\n".join(
        f"- [{criterion['id']}] {criterion['text']} (minimum evidence: {criterion['min_evidence']})"
        for criterion in state["criteria"]
    )
    work = "\n".join(
        f"- [{item['id']}] {item['status']}: {item['title']}"
        for item in sorted(state["work_items"], key=lambda i: -float(i.get("priority", 0)))
    ) or "- No work items have been imported. Derive the smallest concrete next action from the goal."
    work_prompt = textwrap.dedent(f"""
        You are executing a persistent outcome. Continue until the definition of done is demonstrably satisfied.

        GOAL: {state['goal']['title']}
        OBJECTIVE: {state['goal']['objective']}
        REPOSITORY: {state['goal'].get('repository') or 'not specified'}

        DEFINITION OF DONE:
        {criteria}

        CURRENT WORK QUEUE:
        {work}

        CURRENT VERIFIER RESULT:
        - confidence: {verdict['confidence']:.2f}
        - remaining: {json.dumps(verdict['remaining_criteria'], ensure_ascii=False)}
        - next action: {verdict['next_action']}

        Perform the next concrete action now. Do not claim completion without exact evidence. Report changes, tests, blockers, and evidence in a compact structured form.
    """).strip()
    verify_prompt = textwrap.dedent(f"""
        Act as a strict completion verifier. Evaluate the work against the entire original goal, not merely the latest response.

        GOAL: {state['goal']['title']}
        OBJECTIVE: {state['goal']['objective']}
        REQUIRED CONFIDENCE: {state['goal']['confidence_threshold']:.2f}

        CRITERIA:
        {criteria}

        Return only a JSON object with:
        complete, confidence, satisfiedCriteria, remainingCriteria, evidence, blockers, nextAction.
        `complete` may be true only when every criterion has concrete evidence, all relevant checks pass, no work item remains open, and no blocker remains unresolved.
    """).strip()
    return {"work_prompt": work_prompt, "verify_prompt": verify_prompt}


def command_prompt(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    payload = prompt_payload(workspace.load())
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else payload[args.kind])
    return 0


def render_dashboard(state: dict[str, Any], verdict: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value))

    criterion_rows = "".join(
        f"<tr><td>{esc(item['id'])}</td><td>{esc(item['text'])}</td>"
        f"<td>{'✓' if item['complete'] else '—'}</td><td>{item['confidence']:.0%}</td>"
        f"<td>{item['evidence_count']}/{item['minimum_evidence']}</td></tr>"
        for item in verdict["criteria"]
    )
    work_rows = "".join(
        f"<tr><td>{esc(item['id'])}</td><td>{esc(item['title'])}</td><td>{esc(item['status'])}</td>"
        f"<td>{esc(item.get('priority', 0))}</td><td>{esc(item.get('source', 'manual'))}</td></tr>"
        for item in sorted(state["work_items"], key=lambda i: -float(i.get("priority", 0)))
    ) or '<tr><td colspan="5">No work items</td></tr>'
    blockers = "".join(f"<li>{esc(item['text'])}</li>" for item in active_blockers(state)) or "<li>None</li>"
    status_class = "complete" if verdict["complete"] else "active"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(state['goal']['title'])} — Outcome OS</title>
<style>
:root{{--bg:#0b1020;--panel:#141b31;--muted:#9da9c6;--text:#f5f7ff;--line:#27314f;--good:#62d9a3;--warn:#ffcc66}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1100px;margin:auto;padding:32px}}h1{{font-size:38px;margin:0}}h2{{margin-top:0}}.muted{{color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:24px 0}}.card,section{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}}
.value{{font-size:28px;font-weight:750}}.complete{{color:var(--good)}}.active{{color:var(--warn)}}section{{margin:16px 0;overflow:auto}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:10px;text-align:left;border-bottom:1px solid var(--line)}}code{{white-space:pre-wrap}}
</style></head><body><main>
<p class="muted">Outcome OS · evidence-backed execution controller</p><h1>{esc(state['goal']['title'])}</h1>
<p>{esc(state['goal']['objective'])}</p>
<div class="grid"><div class="card"><div class="muted">Status</div><div class="value {status_class}">{esc(state['goal']['status'])}</div></div>
<div class="card"><div class="muted">Confidence</div><div class="value">{verdict['confidence']:.0%}</div></div>
<div class="card"><div class="muted">Threshold</div><div class="value">{verdict['threshold']:.0%}</div></div>
<div class="card"><div class="muted">Next action</div><div>{esc(verdict['next_action'])}</div></div></div>
<section><h2>Completion criteria</h2><table><thead><tr><th>ID</th><th>Criterion</th><th>Done</th><th>Confidence</th><th>Evidence</th></tr></thead><tbody>{criterion_rows}</tbody></table></section>
<section><h2>Work queue</h2><table><thead><tr><th>ID</th><th>Item</th><th>Status</th><th>Priority</th><th>Source</th></tr></thead><tbody>{work_rows}</tbody></table></section>
<section><h2>Open blockers</h2><ul>{blockers}</ul></section>
<section><h2>Audit</h2><p class="muted">Updated {esc(state['updated_at'])}. Run <code>outcome-os doctor</code> to verify the hash chain.</p></section>
</main></body></html>"""


def command_dashboard(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    state = workspace.load()
    verdict = verify_state(state)
    output = Path(args.output).resolve() if args.output else workspace.dashboard_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard(state, verdict), encoding="utf-8")
    workspace.append_event("dashboard.generated", {"path": str(output)})
    print(output)
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    workspace = Workspace.discover()
    errors: list[str] = []
    previous = "0" * 64
    count = 0
    if not workspace.ledger_path.exists():
        errors.append("ledger missing")
    else:
        for number, line in enumerate(workspace.ledger_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            count += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {number}: invalid JSON: {exc}")
                continue
            recorded_hash = event.pop("hash", None)
            if event.get("previous_hash") != previous:
                errors.append(f"line {number}: previous hash mismatch")
            calculated = sha256_text(canonical_json(event))
            if recorded_hash != calculated:
                errors.append(f"line {number}: event hash mismatch")
            previous = recorded_hash or ""
    state = workspace.load()
    if state.get("schema_version") != 1:
        errors.append("unsupported state schema")
    duplicate_ids = []
    all_ids = [state["goal"]["id"]]
    all_ids += [x["id"] for x in state["criteria"]]
    all_ids += [x["id"] for x in state["work_items"]]
    all_ids += [x["id"] for x in state["blockers"]]
    seen = set()
    for value in all_ids:
        if value in seen:
            duplicate_ids.append(value)
        seen.add(value)
    if duplicate_ids:
        errors.append(f"duplicate IDs: {duplicate_ids}")
    result = {"ok": not errors, "events": count, "errors": errors, "workspace": str(workspace.root)}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="outcome-os", description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create an Outcome OS workspace")
    init.add_argument("title")
    init.add_argument("--objective", required=True)
    init.add_argument("--criterion", action="append")
    init.add_argument("--repo")
    init.add_argument("--threshold", type=float, default=0.85)
    init.add_argument("--max-cycles", type=int, default=50)
    init.add_argument("--path", default=".")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    add_item = sub.add_parser("add-item", help="Add a work item")
    add_item.add_argument("title")
    add_item.add_argument("--priority", type=float, default=50)
    add_item.add_argument("--acceptance", action="append")
    add_item.set_defaults(func=command_add_item)

    set_item = sub.add_parser("set-item", help="Change a work item's state")
    set_item.add_argument("item_id")
    set_item.add_argument("status", choices=["pending", "active", "blocked", "done", "skipped"])
    set_item.add_argument("--note")
    set_item.set_defaults(func=command_set_item)

    evidence = sub.add_parser("evidence", help="Attach evidence to a criterion")
    evidence.add_argument("criterion_id")
    evidence.add_argument("value")
    evidence.add_argument("--type", default="artifact")
    evidence.add_argument("--source", default="manual")
    evidence.set_defaults(func=command_evidence)

    check = sub.add_parser("check", help="Record a validation check")
    check.add_argument("name")
    check.add_argument("result", choices=["pass", "fail"])
    check.add_argument("--command")
    check.add_argument("--details", default="")
    check.set_defaults(func=command_check)

    run_check = sub.add_parser("run-check", help="Execute and record a shell validation check")
    run_check.add_argument("name")
    run_check.add_argument("command")
    run_check.set_defaults(func=command_run_check)

    blocker = sub.add_parser("blocker", help="Open a blocker")
    blocker.add_argument("text")
    blocker.add_argument("--owner")
    blocker.set_defaults(func=command_blocker)

    resolve = sub.add_parser("resolve-blocker", help="Resolve a blocker")
    resolve.add_argument("blocker_id")
    resolve.add_argument("--resolution", required=True)
    resolve.set_defaults(func=command_resolve_blocker)

    portfolio = sub.add_parser("import-portfolio", help="Import a Portfolio OS backlog JSON")
    portfolio.add_argument("file")
    portfolio.set_defaults(func=command_import_portfolio)

    verify = sub.add_parser("verify", help="Evaluate all completion gates")
    verify.set_defaults(func=command_verify)

    status = sub.add_parser("status", help="Show current status")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)

    prompt = sub.add_parser("prompt", help="Emit work or verifier prompt")
    prompt.add_argument("kind", choices=["work_prompt", "verify_prompt"])
    prompt.add_argument("--json", action="store_true")
    prompt.set_defaults(func=command_prompt)

    dashboard = sub.add_parser("dashboard", help="Generate a static dashboard")
    dashboard.add_argument("--output")
    dashboard.set_defaults(func=command_dashboard)

    doctor = sub.add_parser("doctor", help="Validate state and audit hash chain")
    doctor.set_defaults(func=command_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "threshold", 0.85) > 1 or getattr(args, "threshold", 0.85) < 0.5:
        parser.error("--threshold must be between 0.5 and 1.0")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
