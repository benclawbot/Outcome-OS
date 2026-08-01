#!/usr/bin/env python3
"""Bootstrap an Outcome OS workspace from a JSON goal profile."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import outcome_os


def load_profile(path: Path) -> dict[str, Any]:
    profile = outcome_os.read_json(path)
    if not isinstance(profile, dict):
        raise ValueError("Goal profile must be a JSON object")
    title = str(profile.get("title", "")).strip()
    objective = str(profile.get("objective", "")).strip()
    criteria = profile.get("criteria")
    if not title or not objective:
        raise ValueError("Goal profile requires non-empty title and objective")
    if not isinstance(criteria, list) or not criteria or not all(isinstance(item, str) and item.strip() for item in criteria):
        raise ValueError("Goal profile requires a non-empty list of criteria strings")
    threshold = float(profile.get("confidence_threshold", 0.85))
    if not 0.5 <= threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0.5 and 1.0")
    max_cycles = int(profile.get("max_cycles", 50))
    if max_cycles < 1:
        raise ValueError("max_cycles must be positive")
    rules = profile.get("operating_rules", [])
    if not isinstance(rules, list) or not all(isinstance(item, str) and item.strip() for item in rules):
        raise ValueError("operating_rules must be a list of non-empty strings")
    return {
        "title": title,
        "objective": objective,
        "criteria": [item.strip() for item in criteria],
        "repository": profile.get("repository"),
        "confidence_threshold": threshold,
        "max_cycles": max_cycles,
        "operating_rules": [item.strip() for item in rules],
    }


def initialize_from_profile(profile_path: Path, destination: Path, force: bool = False) -> outcome_os.Workspace:
    profile_path = profile_path.resolve()
    destination = destination.resolve()
    profile = load_profile(profile_path)
    workspace = outcome_os.Workspace.at(destination)
    if workspace.state_path.exists() and not force:
        raise FileExistsError(f"Workspace already exists at {workspace.data_dir}")
    if force and workspace.data_dir.exists():
        shutil.rmtree(workspace.data_dir)

    objective = profile["objective"]
    rules = profile["operating_rules"]
    if rules:
        objective += "\n\nOperating rules:\n" + "\n".join(f"- {rule}" for rule in rules)
    state = outcome_os.initial_state(
        profile["title"],
        objective,
        profile["criteria"],
        profile["repository"],
        profile["confidence_threshold"],
        profile["max_cycles"],
    )
    state["profile_source"] = str(profile_path)
    state["operating_rules"] = rules
    workspace.save(state)
    workspace.append_event("goal.initialized_from_profile", {
        "profile": str(profile_path),
        "goal": state["goal"],
        "criteria": state["criteria"],
        "operating_rules": rules,
    })
    return workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="outcome-os-init-file", description=__doc__)
    parser.add_argument("profile", help="JSON goal profile")
    parser.add_argument("--path", default=".", help="Workspace destination")
    parser.add_argument("--force", action="store_true", help="Replace an existing Outcome OS workspace")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = initialize_from_profile(Path(args.profile), Path(args.path), args.force)
    except (ValueError, FileExistsError) as exc:
        raise SystemExit(str(exc)) from exc
    print(workspace.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
