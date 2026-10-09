"""Inject / clean up a registered fault scenario.

Usage:
    uv run python -m scenarios.runner.run <scenario-id> [--cleanup]

S1 scope: apply/delete the Chaos Mesh manifest for the scenario and print the
ground truth so a run can be recorded by hand. S2 wires this into the
evaluation harness so each run is captured automatically (E11, E12).
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "scenarios" / "registry.yaml"


def _load_registry() -> dict:
    with REGISTRY.open() as fh:
        return yaml.safe_load(fh)


def _kubectl(action: str, manifest: pathlib.Path) -> None:
    subprocess.run(["kubectl", action, "-f", str(manifest)], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a fault scenario.")
    parser.add_argument("scenario", help="Scenario id from scenarios/registry.yaml")
    parser.add_argument(
        "--cleanup", action="store_true", help="Delete the fault instead of applying it"
    )
    args = parser.parse_args(argv)

    registry = _load_registry()
    scenarios = registry.get("scenarios", {})
    if args.scenario not in scenarios:
        print(f"unknown scenario '{args.scenario}'. known: {', '.join(scenarios)}", file=sys.stderr)
        return 2

    spec = scenarios[args.scenario]
    manifest = REPO_ROOT / spec["inject"]
    ground_truth = REPO_ROOT / spec["ground_truth"]

    action = "delete" if args.cleanup else "apply"
    print(f"{action} scenario '{args.scenario}' -> {manifest}")
    _kubectl(action, manifest)

    if not args.cleanup:
        print("\n--- ground truth ---")
        print(ground_truth.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
