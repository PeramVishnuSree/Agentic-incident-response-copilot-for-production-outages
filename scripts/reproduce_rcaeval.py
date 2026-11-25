"""Run upstream RCAEval ``main.py`` unmodified and archive auditable outputs.

Each method runs in its own working directory (``main.py`` writes results to
``./output`` and reads data from ``./data``), so methods can run in parallel
without overwriting each other. For every method the script archives the
stdout/stderr, return code, per-case rankings written by ``main.py``, the
RCAEval commit, the interpreter version and the dataset checksum.

Example::

    uv run python scripts/reproduce_rcaeval.py \
        --repo ../external/RCAEval --methods baro,nsigma,e_diagnosis,circa,mmbaro,dummy \
        --rcd-python ../external/RCAEval/env-rcd/bin/python --rcd-methods rcd
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ZENODO_MD5 = {"re2-ob": "b9e23f8842c404b396ffd2becff15de4"}


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    return out.stdout.strip()


def run_method(
    repo: Path, python: str, method: str, dataset: str, out_root: Path, extra: list[str]
) -> dict:
    workdir = repo / "runs" / f"{dataset}-{method}"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    (workdir / "data").symlink_to(repo / "data")
    command = [python, str(repo / "main.py"), "--method", method, "--dataset", dataset, *extra]
    started = datetime.now(UTC)
    proc = subprocess.run(command, cwd=workdir, text=True, capture_output=True, check=False)
    finished = datetime.now(UTC)

    target = out_root / method
    if target.exists():
        shutil.rmtree(target)
    (target / "results").mkdir(parents=True)
    (target / "stdout.txt").write_text(proc.stdout)
    (target / "stderr.txt").write_text(proc.stderr[-20000:])
    for path in sorted((workdir / "output" / "results").glob("*.json")):
        shutil.copy2(path, target / "results" / path.name)
    version = subprocess.run(
        [python, "-c", "import sys; print(sys.version.split()[0])"],
        text=True,
        capture_output=True,
        check=False,
    ).stdout.strip()
    record = {
        "method": method,
        "dataset": dataset,
        "command": " ".join(command[1:]),
        "python": version,
        "returncode": proc.returncode,
        "started_utc": started.isoformat(),
        "seconds": round((finished - started).total_seconds(), 1),
        "n_case_results": len(list((target / "results").glob("*.json"))),
    }
    (target / "run.json").write_text(json.dumps(record, indent=2))
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True, help="RCAEval checkout")
    parser.add_argument("--dataset", default="re2-ob")
    parser.add_argument("--methods", default="baro,nsigma,e_diagnosis,circa,mmbaro,dummy")
    parser.add_argument("--rcd-python", help="Python 3.8 interpreter of the RCD environment")
    parser.add_argument("--rcd-methods", default="")
    parser.add_argument("--python", default=None, help="Interpreter of the default environment")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=Path("eval/artifacts/rcaeval/official_runs"))
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not (repo / "main.py").exists():
        raise SystemExit(f"RCAEval main.py not found under {repo}")
    if _git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("RCAEval checkout has local modifications; refusing to run")
    default_python = args.python or str(repo / "env" / "bin" / "python")
    jobs = [(default_python, m) for m in args.methods.split(",") if m]
    if args.rcd_methods:
        if not args.rcd_python:
            raise SystemExit("--rcd-methods needs --rcd-python")
        rcd_python = str(Path(args.rcd_python).absolute())
        jobs += [(rcd_python, m) for m in args.rcd_methods.split(",") if m]
    jobs = [(str(Path(py).absolute()), m) for py, m in jobs]

    args.output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(run_method, repo, py, m, args.dataset, args.output, ["--report-chance"])
            for py, m in jobs
        ]
        for future in futures:
            future.result()

    runs = [json.loads(p.read_text()) for p in sorted(args.output.glob("*/run.json"))]
    provenance = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "rcaeval_repo": "https://github.com/phamquiluan/RCAEval",
        "rcaeval_commit": _git(repo, "rev-parse", "HEAD"),
        "rcaeval_commit_date": _git(repo, "log", "-1", "--format=%cI"),
        "rcaeval_modified": False,
        "dataset": args.dataset,
        "dataset_zenodo_md5": ZENODO_MD5.get(args.dataset),
        "host_python": sys.version.split()[0],
        "runs": runs,
    }
    (args.output / "provenance.json").write_text(json.dumps(provenance, indent=2))
    print(json.dumps({r["method"]: r["returncode"] for r in runs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
