"""Publish the replay-mode website as a free static Hugging Face Space.

    HF_TOKEN=<write token> uv run --with huggingface_hub python scripts/deploy_hf_space.py

Builds dist/site with scripts/build_static_site.py (needs the RE2-OB demo cases from
scripts/fetch_re2ob.py) and uploads it. No server runs: the browser replays the
recorded Qwen3-4B investigations, so the site stays up when this machine is off.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from huggingface_hub import HfApi

REPO = Path(__file__).resolve().parents[1]
SITE = REPO / "dist" / "site"
SPACE_README = REPO / "deploy" / "hf-space" / "README.md"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--space", help="user/name (default: <your user>/incident-copilot)")
    parser.add_argument("--skip-build", action="store_true", help="upload the existing dist/site")
    args = parser.parse_args()
    if not args.skip_build:
        env = {**os.environ, "PYTHONPATH": str(REPO)}
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "build_static_site.py")], check=True, env=env
        )
    shutil.copy(SPACE_README, SITE / "README.md")
    api = HfApi()
    space = args.space or f"{api.whoami()['name']}/incident-copilot"
    api.create_repo(space, repo_type="space", space_sdk="static", exist_ok=True)
    api.upload_folder(
        repo_id=space,
        repo_type="space",
        folder_path=SITE,
        delete_patterns=["*"],
        commit_message="Deploy incident copilot website",
    )
    owner, name = space.split("/")
    print(f"Space: https://huggingface.co/spaces/{space}")
    print(f"App:   https://{owner.lower()}-{name.lower()}.static.hf.space")


if __name__ == "__main__":
    main()
