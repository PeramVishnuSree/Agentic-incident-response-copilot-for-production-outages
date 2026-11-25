"""Download the 90 RE2-OB cases (public RCAEval benchmark) and build the RE2-OB/ view.

    uv run --with huggingface_hub python scripts/fetch_re2ob.py [--dest ../datasets/RCAEval]

Cases land as <dest>/re2ob_<service>_<fault>_<n>/ (metrics, logs, traces, inject_time);
<dest>/RE2-OB/ holds one symlink per case, which is what the console and agent read.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def build_view(dest: Path) -> int:
    view = dest / "RE2-OB"
    view.mkdir(exist_ok=True)
    count = 0
    for case in sorted(dest.glob("re2ob_*")):
        if not (case / "inject_time.txt").exists():
            continue
        link = view / case.name
        if not link.exists():
            link.symlink_to(Path("..") / case.name)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", type=Path, default=REPO_ROOT.parent / "datasets" / "RCAEval")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument(
        "--demo-only", action="store_true", help="only repetition 1 (the 30 console cases)"
    )
    args = parser.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    if not args.skip_download:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id="phamquiluan/RCAEval",
            repo_type="dataset",
            allow_patterns=["re2ob_*_1/*"] if args.demo_only else ["re2ob_*"],
            local_dir=args.dest,
        )
    print(f"{build_view(args.dest)} RE2-OB cases ready under {args.dest / 'RE2-OB'}")


if __name__ == "__main__":
    main()
