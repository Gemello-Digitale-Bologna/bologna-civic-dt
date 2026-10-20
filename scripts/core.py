"""Which core (civic-engagement) this pack is built on, for both its backend
(pyproject.toml) and its app (frontend/package.json): a commit of the core's
repository, or a local checkout while developing both.

    python3 scripts/core.py <commit>              # the core at that commit, from GitHub
    python3 scripts/core.py <commit> --repo <url> # ... from another repository (e.g. file:///...)
    python3 scripts/core.py local [../civic-engagement]

then updates the locks and installs (uv sync, npm install); if either
fails, everything goes back to the previous core. A local core is for
development only: commit the pack pinned to a commit of the core. The
backend uses it as it is (editable), and so does the app's dev server and
build (see frontend/vite.config.ts); npm installs a copy of it (see
frontend/.npmrc), which the app's typecheck reads: run this again when the
core's interface changes.

Run it with python3, not `uv run`: uv syncs the project before running
anything, which a broken pin stops. The script needs only Python's standard
library.
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
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
# What the script changes: put back if an install fails.
FILES = ["pyproject.toml", "uv.lock", "frontend/package.json", "frontend/package-lock.json"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("commit", help='a commit of the core, or "local"')
    parser.add_argument("path", nargs="?", default="../civic-engagement", help="the local core, from the pack's root (with local)")
    parser.add_argument("--repo", default=GITHUB, help="the core's repository (with a commit)")
    args = parser.parse_args()

    if args.commit == "local":
        core = (ROOT / args.path).resolve()
        if not (core / "civic_engagement").is_dir() or not (core / "package.json").is_file():
            raise SystemExit(f"{core}: not a checkout of the core (civic-engagement)")
        python = f'civic-engagement = {{ path = "{os.path.relpath(core, ROOT)}", editable = true }}'
        npm = f"file:{os.path.relpath(core, ROOT / 'frontend')}"
    elif COMMIT.match(args.commit):
        repo = args.repo.removesuffix(".git")
        python = f'civic-engagement = {{ git = "{repo}", rev = "{args.commit}" }}'
        # GitHub's npm URLs end in .git; a local repository's path doesn't.
        npm = f"git+{repo}{'.git' if repo.startswith('http') else ''}#{args.commit}"
    else:
        raise SystemExit(f'{args.commit!r}: neither "local" nor a commit (7 to 40 hexadecimal digits)')

    saved = {name: (ROOT / name).read_bytes() for name in FILES if (ROOT / name).exists()}
    try:
        set_core(python, npm)
    except (subprocess.CalledProcessError, SystemExit, KeyboardInterrupt) as error:
        for name, content in saved.items():
            (ROOT / name).write_bytes(content)
        # The backend's packages back to the previous core (npm leaves its
        # own as they were when it fails).
        subprocess.run(["uv", "sync", "--quiet"], cwd=ROOT)
        raise SystemExit(f"{error or 'Interrupted'}\nNothing changed: the core is the previous one.")
    print(f"civic-engagement: {python.split('= ', 1)[1]} / {npm}")


def set_core(python: str, npm: str) -> None:
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


if __name__ == "__main__":
    main()
