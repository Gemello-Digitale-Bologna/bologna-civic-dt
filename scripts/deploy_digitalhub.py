"""Deploys a site of the urban app on DigitalHub (see docs/deploy-digitalhub.md):

    uv run --no-project --with "digitalhub==0.15.*" --with "digitalhub-runtime-container==0.15.*" \\
        python scripts/deploy_digitalhub.py --project <project> --site piazza_xx_settembre \\
        --image ghcr.io/gemello-digitale-bologna/bologna-civic-dt:<version>

The image's tag must name one build for good — a version (`0.2.0`), a
commit (`sha-ab12cd3`), an experiment (`exp-<anything>`), or a digest: the
platform pulls an image only if its node doesn't have that tag yet, so a
tag that moves (`main`, `latest`) would keep running the old build.
`--pull-always` allows any tag, and has the platform pull it every time.

The function `urban-<site>` gets a new version, with the image; the site's
running runs are stopped first (one process per site's state: never two
writers), then a new run starts, and the script waits until it serves. A
gateway route to the function's stable service (printed at the end)
follows the new run.

With the state in S3 (`--env CIVIC_ENGAGEMENT_STATE=s3://...`), the run's own
S3 credentials, renewed by the app (CIVIC_ENGAGEMENT_S3_CREDENTIALS=digitalhub,
set unless given, or static keys given: `--secret CIVIC_ENGAGEMENT_S3_ACCESS_KEY`).

The SDK's credentials as it reads them: DHCORE_ENDPOINT and
DHCORE_PERSONAL_ACCESS_TOKEN, or a platform workspace's own.
"""

import argparse
import re
import time

import digitalhub as dh

# The platform refuses root: the image's user (see the Dockerfile).
USER = 1000
PORT = 8080
# A run's states while it starts, and once it no longer serves.
STARTING = ("CREATED", "BUILT", "READY", "PENDING")
ENDED = ("ERROR", "STOPPED", "DELETED", "COMPLETED")
# Tags that name one build for good (see the docstring).
FIXED_TAG = re.compile(r"v?\d+\.\d+\.\d+([-+.].*)?|sha-[0-9a-f]{7,40}|exp-.+")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="the platform's project")
    parser.add_argument("--site", required=True, help="the site (CIVIC_ENGAGEMENT_SITE)")
    parser.add_argument("--image", required=True, help="the image, with its tag")
    parser.add_argument("--cpus", default="4", help="CPUs asked for, and given to the app (default 4)")
    parser.add_argument("--memory", default="4Gi", help="memory asked for (default 4Gi)")
    parser.add_argument("--env", action="append", default=[], metavar="NAME=VALUE", help="another variable for the app")
    parser.add_argument("--secret", action="append", default=[], metavar="NAME", help="a project secret for the app")
    parser.add_argument("--timeout", type=int, default=600, help="seconds to wait for the run to serve (default 600)")
    parser.add_argument("--pull-always", action="store_true", help="any tag, pulled every time the run starts")
    args = parser.parse_args()
    if not args.pull_always and not _fixed(args.image):
        raise SystemExit(
            f"{args.image}: a tag that may move (the platform would keep an old build); "
            "use a version, sha-<commit> or exp-<name> tag, or --pull-always"
        )

    project = dh.get_or_create_project(args.project)
    name = f"urban-{args.site.replace('_', '-')}"

    for run in project.list_runs():
        if _function_name(run) == name and run.status.state not in ENDED:
            print(f"Stopping run {run.id} ({run.status.state})", flush=True)
            run.stop()
            _wait(run, lambda state: state in ENDED, args.timeout)

    function = project.new_function(
        name=name,
        kind="container",
        image=args.image,
        image_pull_policy="Always" if args.pull_always else "IfNotPresent",
    )
    envs = {
        "CIVIC_ENGAGEMENT_SITE": args.site,
        "CIVIC_ENGAGEMENT_CPUS": args.cpus,
        **dict(_variable(text) for text in args.env),
    }
    if envs.get("CIVIC_ENGAGEMENT_STATE", "").startswith("s3://") and "CIVIC_ENGAGEMENT_S3_ACCESS_KEY" not in args.secret:
        # The run's credentials last about 5.5 hours: the app renews them.
        envs.setdefault("CIVIC_ENGAGEMENT_S3_CREDENTIALS", "digitalhub")
    run = function.run(
        action="serve",
        service_ports=[{"port": PORT, "target_port": PORT}],
        replicas=1,
        resources={"cpu": args.cpus, "mem": args.memory},
        envs=[{"name": key, "value": value} for key, value in envs.items()],
        secrets=args.secret or None,
        run_as_user=USER,
        run_as_group=USER,
        fs_group=USER,
    )
    print(f"Run {run.id} of {name}, {args.image}", flush=True)
    _wait(run, lambda state: state == "RUNNING" and (run.status.service or {}).get("url"), args.timeout)
    print(f"Serving. A gateway route goes to s-{args.project}-{name}-latest, port {PORT}.")


def _fixed(image: str) -> bool:
    """Whether the image's tag (or digest) names one build for good."""
    if "@sha256:" in image:
        return True
    name, _, tag = image.rpartition(":")
    if not name or "/" in tag:  # no tag (the registry's port isn't one): latest
        return False
    return FIXED_TAG.fullmatch(tag) is not None


def _function_name(run) -> str:
    """The function's name in a run's function key, container://<project>/<name>:<id>."""
    return str(run.spec.function).rsplit("/", 1)[-1].split(":", 1)[0]


def _variable(text: str) -> tuple[str, str]:
    key, sep, value = text.partition("=")
    if not sep or not key:
        raise SystemExit(f"--env {text!r}: NAME=VALUE expected")
    return key, value


def _wait(run, done, timeout: int) -> None:
    start, last = time.monotonic(), None
    while time.monotonic() - start < timeout:
        run.refresh()
        state = run.status.state
        if state != last:
            print(f"  {time.monotonic() - start:4.0f} s  {state}", flush=True)
            last = state
        if done(state):
            return
        if state == "ERROR":
            raise SystemExit(f"Run {run.id} failed: {getattr(run.status, 'message', None)}")
        if state == "PENDING":
            # A container that can't start (an image running as root, one
            # that can't be pulled) leaves the run PENDING: the reason is
            # the pod's.
            waiting = _waiting(run)
            if waiting:
                raise SystemExit(f"Run {run.id} can't start: {waiting}")
        time.sleep(5)
    raise SystemExit(f"Run {run.id} still {run.status.state} after {timeout} s")


def _waiting(run) -> str | None:
    pods = (getattr(run.status, "k8s", None) or {}).get("pods") or []
    for pod in pods:
        for container in (pod.get("status") or {}).get("containerStatuses") or []:
            waiting = (container.get("state") or {}).get("waiting") or {}
            if waiting.get("reason") in ("CreateContainerConfigError", "ErrImagePull", "ImagePullBackOff", "InvalidImageName"):
                return f"{waiting['reason']}: {waiting.get('message', '')}"
    return None


if __name__ == "__main__":
    main()
