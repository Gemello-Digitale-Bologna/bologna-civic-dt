"""Which core (civic-engagement) this pack is built on, for both its backend
(pyproject.toml) and its app (frontend/package.json): a commit of the core's
repository, or a local checkout while developing both.

    python3 scripts/core.py <commit>              # the core at that commit, from GitHub
    python3 scripts/core.py <commit> --repo <url> # ... from another repository (e.g. file:///...)
    python3 scripts/core.py local [../civic-engagement]

then updates the locks and installs (uv sync, npm install). A local core is
for development only: commit the pack pinned to a commit of the core. The
backend uses it as it is (editable); the app gets a copy of its frontend
(see frontend/.npmrc): run this again after changing it.
"""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITHUB = "https://github.com/fbk-most/civic-engagement"
SOURCE = re.compile(r"^civic-engagement = \{.*\}$", re.MULTILINE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("commit", help='a commit of the core, or "local"')
    parser.add_argument("path", nargs="?", default="../civic-engagement", help="the local core, from the pack's root (with local)")
    parser.add_argument("--repo", default=GITHUB, help="the core's repository (with a commit)")
    args = parser.parse_args()

    if args.commit == "local":
        core = (ROOT / args.path).resolve()
        python = f'civic-engagement = {{ path = "{os.path.relpath(core, ROOT)}", editable = true }}'
        npm = f"file:{os.path.relpath(core, ROOT / 'frontend')}"
    else:
        repo = args.repo.removesuffix(".git")
        python = f'civic-engagement = {{ git = "{repo}", rev = "{args.commit}" }}'
        # GitHub's npm URLs end in .git; a local repository's path doesn't.
        npm = f"git+{repo}{'.git' if repo.startswith('http') else ''}#{args.commit}"

    pyproject = ROOT / "pyproject.toml"
    text, count = SOURCE.subn(python, pyproject.read_text())
    if count != 1:
        raise SystemExit("pyproject.toml: no civic-engagement line under [tool.uv.sources]")
    pyproject.write_text(text)

    package = ROOT / "frontend" / "package.json"
    manifest = json.loads(package.read_text())
    manifest["dependencies"]["civic-engagement"] = npm
    package.write_text(json.dumps(manifest, indent=2) + "\n")

    subprocess.run(["uv", "sync"], cwd=ROOT, check=True)
    subprocess.run(["npm", "install"], cwd=ROOT / "frontend", check=True)
    print(f"civic-engagement: {python.split('= ', 1)[1]} / {npm}")


if __name__ == "__main__":
    main()
