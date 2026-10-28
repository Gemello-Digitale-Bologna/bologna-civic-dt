# Deploying the urban app on DigitalHub Bologna

**Status: phases 1 (packaging) and 2 (teams) built, not yet deployed** (October 2026).
Tested first on FBK's instance (`most.atlas.fbk.eu`, on FBK's local
network), then on Bologna's.

The urban app — the core with this pack — as containers on the DigitalHub
instance *digitalhub-bologna*, for teams working on a site. What the core
provides (teams, PINs, the state store) is in the core's README, "Teams";
the container's contract and how any pack runs on DigitalHub, the
platform's constraints and how to check an instance, in the core's
`docs/deploy-digitalhub.md`. This page is what's specific to this pack and
this instance.

## Target

- **5 teams of 6 people per site**, 1–2 editors each; fewer if the
  measurements say so (see [Capacity](#capacity)).
- One run per site deployed. Which sites: to be decided (Piazza XX
  Settembre; Piazza Dante, for demos).

## The instance

| | |
|---|---|
| Instance | `digitalhub-bologna`, core **0.15.1** (API level 15) |
| Core (API, identity issuer), KRM | `https://core.bolognadigitaltwin.it`, `https://krm.bolognadigitaltwin.it` |
| S3 | `https://s3.bolognadigitaltwin.it`, bucket `datalake`, path style; prefix for the app: `civic-dt/` |
| Test project | `civic-dt-test` (the production project: to be decided) |
| Runs' credentials | temporary, about 5.5 hours: not for the state (see the core's guide) |

Tested on 24 October 2026 (the procedure is the core's guide's):

| Test | Result |
|---|---|
| Non-root | Root refused; whoami as user 1000 runs |
| GHCR image, 4 CPU / 4 GiB | Pulled; accepted |
| `nproc` | 16 under a 4-CPU quota |
| Volume | Per run: kept across stop/resume, a new run starts empty |
| S3 | Write and read under `datalake/civic-dt-test/` from a run |
| Internet from the cluster | Yes (PyPI) |
| Gateway | **Not yet**: KRM shows no gateways for us (see [Pending](#pending)) |

### FBK's test instance

Before Bologna, the app is tried on FBK's DigitalHub, `most.atlas.fbk.eu`
(reachable from FBK's network only). Tested on 28 October 2026:

| Test | Result |
|---|---|
| Core | **0.15.1**, as Bologna's |
| Non-root | Root refused (its administrators) |
| GHCR image, 4 CPU / 4 GiB | Pulled; `cpu.max` 4 CPUs, memory limit 4.4 GiB |
| `nproc` | 96 under a 4-CPU quota |
| S3 | `https://s3.atlas.fbk.eu`, bucket `most-datalake`, path style: write, read, delete under `civic-dt-test/` from a run |
| Runs' credentials | `AWS_*` with an `AWS_SESSION_TOKEN`, about 5.6 hours |
| A project secret `AWS_ACCESS_KEY_ID` | **Overridden** by the run's own: hence the core's `CIVIC_ENGAGEMENT_S3_*` |
| Internet from the cluster | Yes, through a proxy (`HTTP(S)_PROXY`) |
| Logs | In the console, while the run lasts; `Run.logs()` fails as on Bologna |
| Gateway | Not yet tried |

## Image

The `Dockerfile` at the repository's root, in three stages:

1. **Node**: `npm ci && npm run build` in `frontend/`. The core comes from
   GitHub at the commit pinned in `package.json` (the pre-push hook
   guarantees a pushed commit pins one).
2. **Python**: `uv sync --frozen --no-dev --no-editable`, the core at the
   commit pinned in `pyproject.toml`.
3. **Runtime**: the Python environment, `frontend/dist`, and `data/`
   without the ingestion inputs (`lidar/`, `ortofoto/`: what they give is
   in the committed baselines and terrain grid) and without local
   sessions (`.dockerignore`); `USER 1000:1000`; the core's launcher,
   `python -m civic_engagement.serve bologna_civic_dt.main:app`, on 8080;
   `CIVIC_ENGAGEMENT_FRONTEND` set to the built app,
   `CIVIC_ENGAGEMENT_STATE` to `/tmp/civic-engagement`.

Building it and running it locally: the README's "Container".

GitHub Actions (`.github/workflows/image.yml`) builds it for every tag
`v<version>` and pushes
`ghcr.io/gemello-digitale-bologna/bologna-civic-dt:<version>`, labelled
with the core's commit; by hand, for a branch, as `:<branch>`. Needs the
`Gemello-Digitale-Bologna` organisation to let Actions publish packages,
and the package made public (once, after the first push: the package's
settings on GitHub).

## Runs

One function per site, `urban-<site>` (e.g. `urban-piazza-xx-settembre`),
in the production project, run as in the core's guide with:

| Parameter | Value |
|---|---|
| `image` | `ghcr.io/gemello-digitale-bologna/bologna-civic-dt:<version>` |
| `resources` | `{"cpu": "4", "mem": "4Gi"}` to start; tuned after the measurements |
| `CIVIC_ENGAGEMENT_SITE` | the site |
| `CIVIC_ENGAGEMENT_AUTH` | `pin` (without it, `open`: one shared scene, no login) |
| `CIVIC_ENGAGEMENT_STATE` | `s3://<bucket>/<prefix>/`, e.g. `s3://datalake/civic-dt/` (the keys start with the site's directory, so sites can share it): the state outlives runs and versions (without it, the image's `/tmp`, lost with the run) |
| `CIVIC_ENGAGEMENT_CPUS` | `4` |
| `CIVIC_ENGAGEMENT_TRUSTED_PROXY` | `1` if the gateway sets `X-Forwarded-For`; else unset |
| secrets | `CIVIC_ENGAGEMENT_PIN_SECRET`, `CIVIC_ENGAGEMENT_MANAGER_USER`, `CIVIC_ENGAGEMENT_MANAGER_PASSWORD`; S3's credentials, which must not expire, under the core's names: `CIVIC_ENGAGEMENT_S3_ACCESS_KEY`, `CIVIC_ENGAGEMENT_S3_SECRET_KEY` (the endpoint: the run's `AWS_ENDPOINT_URL`, or `CIVIC_ENGAGEMENT_S3_ENDPOINT`). Not `AWS_*`: the run's own temporary ones (about 5.5 hours) override a secret of that name |
| security | `run_as_user=1000, run_as_group=1000, fs_group=1000` |

The deployment script makes a deployment reproducible from the
repository: a new version of the function with the image, the site's
running runs stopped first (never two writers), a new run, and a wait until
it serves.

```bash
export DHCORE_ENDPOINT=https://core.bolognadigitaltwin.it DHCORE_PERSONAL_ACCESS_TOKEN=<token>
uv run --no-project --with "digitalhub==0.15.*" --with "digitalhub-runtime-container==0.15.*" \
  python scripts/deploy_digitalhub.py --project civic-dt-test --site piazza_xx_settembre \
  --image ghcr.io/gemello-digitale-bologna/bologna-civic-dt:<version>
```

`--env NAME=VALUE` and `--secret NAME` add variables and project secrets;
`--cpus` and `--memory` change the resources. With teams, e.g.:

```bash
  ... --env CIVIC_ENGAGEMENT_AUTH=pin --env CIVIC_ENGAGEMENT_STATE=<the state's place> \
  --secret <the project secret with the PIN secret and the manager's credentials>
```

Then the teams, from a laptop, through the route (or from a platform
workspace, through the service's internal address), with the core's CLI:

```bash
export CIVIC_ENGAGEMENT_ADMIN_URL=https://<the site's hostname> \
  CIVIC_ENGAGEMENT_MANAGER_USER=<user> CIVIC_ENGAGEMENT_MANAGER_PASSWORD=<password>
uv run civic-engagement-admin team create "Tavolo 1"
uv run civic-engagement-admin member add tavolo-1 "Anna" --editor
uv run civic-engagement-admin member add tavolo-1 --viewers
```

**Tags.** The platform pulls an image only if the node doesn't have its tag
yet (`IfNotPresent`): a tag that moves (`main`, `latest`) would keep running
an old build, silently. So the script takes only tags that name one build
for good: a version (`0.2.0`, from a tag `v0.2.0`), a commit (`sha-ab12cd3`,
from the workflow), an experiment (`exp-<name>`, pushed by hand: the
README's "Container"), or a digest. `--pull-always` allows any tag, and has
the platform pull it every time the run starts.

A route per site, to `s-<project>-urban-<site>-latest`, port 8080, on its
own hostname under the instance's services domain (to be confirmed), no
authentication.

## The pack's part

### PINs: a word and three digits

The core's PIN mechanism, with the pack's format (`UrbanPack.pin_format`,
a `WordPin` in `bologna_civic_dt/pins.py`): an Italian word and three
digits, `gabbiano515`. Easier to say, write on a card and remember than
six digits.

- **The words**: `bologna_civic_dt/words_it.txt`, from the Italian word
  list of [BIP-0039](https://github.com/bitcoin/bips/blob/master/bip-0039/italian.txt)
  (2048 words, MIT licence; its origin and licence in the file's header).
  That list is built to be read and typed without mistakes: no accents, 4
  to 9 letters, no two words with the same first four letters. Kept from
  it: 1078 nouns, concrete or neutral; out: verbs, adjectives, participles
  and adverbs, names and countries, and anything unpleasant or that could
  offend (*usuraio*, *otite*, *buffone*). So 1,078,000 PINs, above the
  10⁶ the core requires (`tests/test_pins.py` checks it).
- **Each PIN of a site has its own word** (the format's distinct part): a
  mistyped digit can't land on someone else's PIN; with 30 PINs among 1000
  words, easy.
- **Forgiving input**: case, accents, spaces, hyphens and the order ignored —
  `Gabbiano 515`, `gabbiano-515`, `GABBIANO515` and `515 gabbiano` are the
  same PIN.
- The login screen's hint: `es. gabbiano515`.

### The rest

- **`/api/thermal-field`** reads the session: it takes the team from the
  core's dependency, like the core's routes.
- **The felt-temperature fields**: the thread pool tracing the sun's rays
  (`thermal_field.py`) has as many threads as
  `civic_engagement.config.cpus()` (by default it had the machine's count
  plus 4: 20 threads under a quota of 4). The cache (`felt_field.py`,
  `FIELD_CACHE_SIZE`) holds 60 fields of about 5 MB, for 5 teams;
  `FIELDS_AT_ONCE` (2) is to be measured again on 4 CPUs.
- **The state's storage**: S3 on the platform (the core's `s3` extra,
  boto3, is a dependency); files by default, locally.

## Capacity

Editing costs little. The cost is the felt-temperature fields: computed per
(team's cards, year, date) as viewers move the date, a few hundred MB and
every allowed core each, at most `FIELDS_AT_ONCE` at once. Teams with the
same cards share them.

What decides it is the time of **one field on 4 of the platform's CPUs**,
measured once the image runs there (phase 1):

- around a second: 5 × 6 is fine;
- around ten seconds: date changes queue. Then precompute the fields at
  the reference dates, raise the CPUs, or reduce the teams.

If a field can take longer than the gateway's timeout, the field becomes
asynchronous: a request starts it, the next ones fetch it when ready.

## Pending

Asked to the instance's administrators on 24 October 2026:

| Question | Bears on |
|---|---|
| A gateway route: enabling HTTPRoutes in KRM for us, or creating one; the hostname or domain; a wildcard certificate | Exposure |
| Does the gateway pass on the client's IP (`X-Forwarded-For`)? Its timeout, any limit on response size (we need about 5 MB) | PIN throttling; asynchronous fields |
| ~~The recommended way to keep data for a long-running service~~ S3 (answered October 2026). Still to be had: static credentials limited to our prefix; or else how long a run's `DHCORE_REFRESH_TOKEN` lasts, to refresh the run's own | The state store's credentials |
| Are the runs' volumes deleted with the run? | Cleaning up |
| Which SDK version for core 0.15.1? | The deployment script |

Ours to decide: the sites to deploy, the production project, publishing
images under `Gemello-Digitale-Bologna` on GHCR.

Once a route exists, the gateway tests of the core's guide: the client's
IP, a 5 MB answer, the first wait that fails among 20, 40, 70 and 130 s, a
new run behind the same route.

## Phases

1. **Packaging** (built): the core's phase 1; the Dockerfile, CI, the
   deployment script, the sun-ray pool sized from the quota,
   `CIVIC_ENGAGEMENT_BACKEND` for the dev server's proxy. Still to do: today's
   single session deployed on the platform, reached through the console,
   and the felt-field measurement there.
2. **Teams** (built): the core's phase 2; the word list and `WordPin`;
   `/thermal-field` and the felt-field cache. Tried locally, with the state
   in files, and in an S3 emulator (moto's server).
3. **Production**: the route and the long-lived storage credentials (from
   the administrators); a load test at 5 × 6 from outside; a trial
   workshop.
