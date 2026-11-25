"""Publish the web console as a public Hugging Face Space (Docker, free CPU tier).

    uv run --with huggingface_hub hf auth login          # once, with a "write" token
    uv run --with huggingface_hub python scripts/deploy_hf_space.py [--space user/incident-copilot]

The Space builds deploy/hf-space/Dockerfile, downloads the 30 demo cases from the public
RCAEval dataset, and serves the console in replay mode at https://<user>-<name>.hf.space.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import HfApi

REPO = Path(__file__).resolve().parents[1]
SPACE_FILES = REPO / "deploy" / "hf-space"
IGNORE = [
    ".git/*",
    ".venv/*",
    "**/__pycache__/*",
    ".pytest_cache/*",
    ".ruff_cache/*",
    "datasets",
    "datasets/*",
    "docs/*.docx",
    "experiments/n3/archive_tool_v1/*",
    "README.md",
    "Dockerfile",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--space", help="user/name (default: <your user>/incident-copilot)")
    args = parser.parse_args()
    api = HfApi()
    space = args.space or f"{api.whoami()['name']}/incident-copilot"
    api.create_repo(space, repo_type="space", space_sdk="docker", exist_ok=True)
    api.upload_folder(
        repo_id=space,
        repo_type="space",
        folder_path=REPO,
        ignore_patterns=IGNORE,
        commit_message="Deploy incident copilot console",
    )
    for name in ("Dockerfile", "README.md"):
        api.upload_file(
            repo_id=space,
            repo_type="space",
            path_or_fileobj=SPACE_FILES / name,
            path_in_repo=name,
            commit_message=f"Space {name}",
        )
    owner, name = space.split("/")
    print(f"Space: https://huggingface.co/spaces/{space}")
    print(f"App:   https://{owner.lower()}-{name.lower()}.hf.space  (first build takes ~3-5 min)")


if __name__ == "__main__":
    main()
