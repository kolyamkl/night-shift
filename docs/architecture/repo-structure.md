# Repository structure

How the MuGuard repository is laid out, why, and what moved on 25 October 2026.
The layout follows what comparable open-source Python and TypeScript projects do,
within one constraint: a parallel rewrite of `backend/` was in progress, so nothing
the backend reads by path moved in this change. Those moves are listed under
[follow-ups](#follow-ups).

## What comparable projects do

| Project | Code | Data, training and evaluation | Docs, scripts, config |
| --- | --- | --- | --- |
| [Presidio](https://github.com/data-privacy-stack/presidio) (formerly microsoft/presidio) | One folder per package (`presidio-analyzer/`, `presidio-anonymizer/`, ...), each with its own `pyproject.toml`, `Dockerfile` and `tests/` | Evaluation and the synthetic data generator live in a separate repo, [presidio-research](https://github.com/data-privacy-stack/presidio-research), with `presidio_evaluator/`, `notebooks/`, `data/` and `tests/`. Its [`.gitignore`](https://github.com/data-privacy-stack/presidio-research/blob/main/.gitignore) ignores `/data`, `datasets/` and `model-outputs/` except one 1 MB synthetic file, `synth_dataset_v2.json` | `docs/` (mkdocs), `e2e-tests/`, `scripts/`; `AGENTS.md` and `CLAUDE.md` committed as shared agent instructions; `.env`, `.vscode` and `.idea` ignored |
| [Protect AI LLM Guard](https://github.com/protectai/llm-guard) (archived) | Library `llm_guard/` and the deployable `llm_guard_api/` side by side | [`benchmarks/`](https://github.com/protectai/llm-guard/tree/main/benchmarks) holds a `run.py` and two small example files; `examples/` holds integration scripts | `docs/`, `tests/`, a [`Makefile`](https://github.com/protectai/llm-guard/blob/main/Makefile) with `install-dev`, `lint`, `test`, `docs-serve` |
| [scrubadub](https://github.com/LeapBeyond/scrubadub) | Package `scrubadub/` | Accuracy benchmarks sit in `tests/` with one tiny example document; [`bin/download_data.sh`](https://github.com/LeapBeyond/scrubadub/blob/master/bin/download_data.sh) downloads the Enron and SMS corpora into `data/raw` rather than committing them | `docs/`, `design/` (usage sketches), `requirements/` split by purpose |
| [Netflix Dispatch](https://github.com/Netflix/dispatch) (archived) | Python package and the Vue frontend both under `src/dispatch/` | [`data/`](https://github.com/Netflix/dispatch/tree/main/data) holds a sample database dump for local development and the script that refreshes it | `docs/`, `docker/`, `scripts/`, `bin/`; `.vscode/` and `.devcontainer/` committed |
| [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template) | `backend/` and `frontend/` side by side, each with its own `Dockerfile`, tests and config | None | `scripts/` for repo-wide shell scripts, one [workflow per concern](https://github.com/fastapi/full-stack-fastapi-template/tree/master/.github/workflows) (`test-backend.yml`, `playwright.yml`, ...); `.claude/skills/` and `.agents/skills/` committed; `.vscode/*` ignored except `extensions.json` |
| [Cookiecutter Data Science](https://cookiecutter-data-science.drivendata.org/) (the common ML layout) | Package named after the project | `data/{raw,external,interim,processed}`, `models/`, `notebooks/`, `reports/`. [`/data/` is git-ignored by default](https://github.com/drivendataorg/cookiecutter-data-science/blob/master/docs/docs/opinions.md) | `docs/`, `references/`, a `Makefile` |

What this means for each kind of content:

- **Datasets** sit in a top-level `data/` (Dispatch, Cookiecutter, presidio-research).
  Small synthetic or sample sets are committed; raw downloads and bulk outputs are not.
- **Training and evaluation tooling** is kept apart from the runtime code: a separate
  repo (Presidio), a `benchmarks/` folder (LLM Guard) or benchmark scripts beside the
  tests (scrubadub). The running app never imports it.
- **Experiments** go in `notebooks/` or `benchmarks/`; their results in `reports/` or
  a results folder, not mixed with source code.
- **Docs** are always a top-level `docs/`. **Scripts** that act on the whole repo are a
  top-level `scripts/` or `bin/`.
- **Editor and agent config** is committed only when it is shared on purpose (Presidio's
  `AGENTS.md`, the template's `.claude/skills/`, Dispatch's `.devcontainer/`). Personal
  settings, IDE folders and tool state are ignored.
- **Kept out of git** everywhere: `.env` files, caches (`__pycache__`, `.pytest_cache`,
  `.mypy_cache`), build output (`dist/`, `node_modules/`), coverage, IDE folders, raw
  or large data and model outputs.

### Should a project commit the data it trained on?

Commit the data when it is small, safe to share and needed to reproduce a reported
number; otherwise commit the code and the pinned source that rebuild it.

- Cookiecutter Data Science ignores `data/` by default, but says a small amount of data
  that rarely changes may be committed. GitHub [warns at 50 MB and rejects files over
  100 MB](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github);
  larger data belongs in object storage, Git LFS or a tool such as [DVC](https://dvc.org/doc/use-cases/versioning-data-and-models).
- presidio-research commits exactly one synthetic dataset and ignores the rest; scrubadub
  downloads third-party corpora with a script instead of committing them.
- [Datasheets for Datasets](https://arxiv.org/abs/1803.09010) (Gebru et al.) asks every
  dataset to state its source, composition, collection process and allowed uses.

For MuGuard this means: keep the committed datasets. They hold about 27 MB, every
person in them is invented, the templates are public with their licences recorded in
`data/sources/*/manifest.json`, and the 91.7% adapter was trained on calls built
from `data/docs`. Keep out of git, as the repo already did: `data/raw/` (may hold real
people), `data/external/` (third-party licences, rebuilt by `training/dataconv` from
pinned revisions), the bulk of `data/synthetic/` (the local `data/` folder is about
1.5 GB), `data/rounds/` and `training/evalkit/runs/`.

## Audit of the top level

Origin is `git log --format='%an' -- <path>`, by number of commits. "Claude" means
commits written by AI agents in teammates' sessions.

| Entry | What it is | Origin | App needs it at runtime | Decision |
| --- | --- | --- | --- | --- |
| `.claude/` | `launch.json`: dev-server definitions for the Claude Code preview tool | Dmytro 2, Glib 1 | No | Removed from git, ignored, local copy kept. Its server commands are now `make dev` and `make demo-servers` |
| `.impeccable/` | Design-tool sidecar: `design.json`, 9 HTML mock variants, question logs, surface briefs | Glib 1, Dmytro 1 | No | Removed from git, ignored, local copy kept |
| `.superpowers/` | Brainstorm mockups | never tracked | No | Stays ignored |
| `backend/` | FastAPI API | Mykola 10, Glib 9, Claude 6, Dmytro 2 | Yes | Untouched (rewritten in a parallel PR) |
| `frontend/` | React + Vite app, landing page, unit and Playwright tests | Dmytro 8, Claude 7, Glib 5, Mykola 3 | Yes | Untouched |
| `data/` | Datasets, answer keys, Mubit results, sample PDFs | Mykola 6, Claude 4, Glib 2, Dmytro 2 | Only `data/synthetic/pdfs/` | Stays; its README now lists every subfolder |
| `datagen/` | Synthetic UK document generator (uv project) | Glib 1, Dmytro 1 | No | Moved to `training/datagen/` |
| `dataconv/` | Converters for open PII datasets (uv project) | Glib 1, Dmytro 1 | No | Moved to `training/dataconv/` |
| `evalkit/` | Redaction helpers, regex baseline, prompt, scorer, Mubit sender | Glib 1, Dmytro 1 | Yes: imported by `backend/app`, copied by `backend/Dockerfile` | Stays this PR; see follow-ups |
| `demo/` | Records, voices and edits the submission video (Remotion, Playwright) | Dmytro 2 | No | Stays: a self-contained deliverable with its own `package.json`, as `examples/` or `benchmarks/` are elsewhere |
| `docs/` | Architecture, Mubit, security, deployment, research | Claude 10, Mykola 9, Dmytro 9, Glib 8 | No | Stays; this page added |
| `scripts/` | Mixed: T1 dataset pipeline, review dataset tool, source builders, OCR evaluation, sample builder, local database, README numbers | Mykola 10, Claude 4, Glib 3 | No, but `backend/tests/test_llm.py` loads `scripts/dataset/send_batch.py` | Training tools moved to `training/`; repo-wide helpers and the pinned `dataset/` stay |
| `tests/` | Dataset pipeline, ingestion and review dataset tests | Mykola 5, Claude 2, Glib 1 | No | Review tests moved next to their tool; the rest stays (follow-ups) |
| `requirements.txt` | Python deps for the root scripts and tests | Mykola 1, Claude 1 | No (the backend has its own `pyproject.toml`) | Stays; header names who uses it |
| `DESIGN.md`, `PRODUCT.md` | Design system and product context | Dmytro 4, Glib 2; Glib 2, Dmytro 1 | No | Stay at the root: the Impeccable design tool reads both there, and the README links the design system |
| `README.md` | Project overview, run and verify steps | Glib 9, Mykola 5, Dmytro 1 | No | Edited: layout tree, `make` commands, links |
| `LICENSE` | PolyForm Noncommercial 1.0.0 | Mykola 1, Glib 1 | No | Stays |
| `.gitignore` | Ignore rules | Dmytro 5, Glib 4, Mykola 1, Claude 1 | No | Grouped by purpose; adds `.claude/`, `.impeccable/`, editor and cache folders; every earlier rule kept |
| `.env.example` | Template for `.env` | Glib 3, Mykola 2, Claude 1 | No (template only) | Stays |
| `.dockerignore`, `.railwayignore` | What Docker builds and `railway up` upload | Glib 1 each | Yes, for deploys from the repo root | Unchanged |

## Before and after

Before:

```text
.claude/                launch.json
.impeccable/            design.json, mocks/, questions/, surfaces/
backend/
data/
datagen/
dataconv/
demo/
docs/
evalkit/
frontend/
scripts/
├── dataset/  ocr/  review_dataset/  samples/  sources/
└── local_db.py  readme_numbers.py
tests/
└── dataset/  ingest/  review_dataset/
.dockerignore  .env.example  .gitignore  .railwayignore
DESIGN.md  LICENSE  PRODUCT.md  README.md  requirements.txt
```

After:

```text
.github/workflows/      frontend.yml: type-check and unit tests
backend/                the API (unchanged)
frontend/               the web app (unchanged)
evalkit/                stays until the backend PR lands
training/               everything that builds, sends and scores T1 data
├── README.md           the three approaches, owners and results
├── datagen/            synthetic documents (was datagen/)
├── dataconv/           open-dataset converters (was dataconv/)
├── review_redaction/   review-redaction task (was scripts/review_dataset/)
│   └── tests/          (was tests/review_dataset/)
└── sources/            template fetchers and builders (was scripts/sources/)
data/                   datasets (unchanged paths)
demo/                   submission video
docs/                   + architecture/repo-structure.md
scripts/
├── dataset/  ocr/  samples/
└── local_db.py  readme_numbers.py
tests/
└── dataset/  ingest/
.dockerignore  .env.example  .gitignore  .railwayignore
DESIGN.md  LICENSE  Makefile  PRODUCT.md  README.md  requirements.txt
```

## Moves and why

| Old path | New path | Why |
| --- | --- | --- |
| `datagen/` | `training/datagen/` | Training data tool, not part of the app. Default output paths now `../../data/...`; the research copy path no longer hard-codes one laptop |
| `dataconv/` | `training/dataconv/` | Same. Its `/Users/dima/...` path constants now resolve from the repository root, so it runs in any checkout |
| `scripts/review_dataset/` | `training/review_redaction/` | Glib's approach gets its own folder, named after its datasets `data/review_redaction_v2*` |
| `tests/review_dataset/` | `training/review_redaction/tests/` | Tests sit next to the tool, as in `datagen/` and `dataconv/`; three repo-root paths adjusted |
| `scripts/sources/` | `training/sources/` | Builders of `data/docs` for the rewrite approach; same folder depth, so their code needed no path change |

Removed from git, kept on disk and now ignored: `.claude/launch.json` and the 20 files
of `.impeccable/`. They are personal tool state, not project config. Git history keeps
every version. Nothing was deleted from disk.

**After pulling this change**, git removes these files from other checkouts. To get
them back as ignored local files:

```sh
git restore --source=decae56 -- .impeccable .claude/launch.json
```

Old checkouts also keep ignored leftovers in the old folders (`datagen/.venv`,
`dataconv/.venv`); delete those folders and run `uv sync` inside `training/datagen`
and `training/dataconv`.

Paths inside dated research notes (`docs/research/`), `docs/APP-SPEC.md` and recorded
run files (`data/results/**/run.json`) keep the layout of their day; the table above
maps them.

## Follow-ups

The first four follow-ups were done on 25 October, after the backend PR landed:

| Old path | New path | Notes |
| --- | --- | --- |
| `evalkit/` | `training/evalkit/` | The backend PR copied the runtime helpers into `backend/app/redaction/` and `backend/app/llm/`, so the backend imports nothing from it and the package moved whole. `send_batch --design rewrite` reads `backend/app/llm/prompts.py` |
| `data/synthetic/pdfs/` | `backend/samples/` | The app ships these files. `VEIL_SAMPLES_DIR` defaults there, the Dockerfile copies it, and Docker builds now leave out `data/` and `training/` whole |
| `scripts/dataset/`, `tests/dataset/` | `training/rewrite/`, `training/rewrite/tests/` | `backend/tests/llm/test_t1.py` loads `training/rewrite/send_batch.py` by path |
| `tests/ingest/` | `backend/tests/ingest/` | Runs with the backend tests; `reportlab` joined the backend's dev dependencies. The root `tests/` folder is gone |

The deprecated import adapters in `backend/app` (`prompts.py`, `extract.py`, `addresses.py`,
`pipeline.py` and the `rewrite_values` re-export) were removed once their callers moved.
The Docker build context stays the repository root, because Railway builds both services
from it with `RAILWAY_DOCKERFILE_PATH`.

Still open:

1. **Python lint.** `make lint` checks only syntax errors and undefined names. A shared
   ruff rule set needs agreement first: ruff's defaults report about 240 style findings
   outside `backend/`.
2. **CI for Python.** Add backend tests with a PostgreSQL service and the training suites
   (`make test-training`) next to the frontend workflow.
3. **Optional.** `frontend/docs/` holds 2.7 MB of PR screenshots that could live under
   `docs/`; the four `data/review_redaction_v2*` folders could become one
   `data/review_redaction/` with a subfolder per version.
