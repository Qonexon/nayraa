# nayraa

AI code review for GitHub pull requests. Bring your own Gemini key, post through
[reviewdog](https://github.com/reviewdog/reviewdog), keep the whole thing in one small
Python package.

nayraa exists because most AI reviewers fail in one of two ways: they comment on
everything until people learn to scroll past them, or they are tuned so conservatively
that they never say anything at all. Both are useless, and the second is worse because it
looks healthy.

## Design stance

**Noise is the enemy, not missed findings.** A reviewer nobody reads has a value of zero,
so every design decision here trades recall for precision.

- **Two values of severity — `blocker` and `major`.** There is no `nit`, `suggestion`, or
  `info` level, so the model has nowhere to put one. The schema is the filter.
- **Every finding is adversarially refuted before it is posted.** A second model call is
  asked to *disprove* each candidate and told to default to refuted when uncertain.
- **Three findings per pull request, maximum.**
- **Formatting, naming, import order, unused code and missing tests are out of scope.**
  Your linter and type checker already decide those, and they are always right and always
  free. Turn them on first; nayraa is for what they cannot decide.
- **Findings never block a merge.** The tool exits 0 no matter what — including when it
  crashes. A broken reviewer must not stop your team from shipping.
- **No agent loop.** Context is assembled deterministically by a script, then two model
  calls are made. No tool calling, no multi-turn, no nondeterministic retrieval.

## Quick start

Add a workflow (see [`examples/nayraa.yml`](examples/nayraa.yml)):

```yaml
name: nayraa review
on: pull_request

permissions:
  contents: read
  pull-requests: write

jobs:
  nayraa:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          ref: ${{ github.event.pull_request.head.sha }}
      - uses: Qonexon/nayraa@v0
        with:
          base: ${{ github.event.pull_request.base.sha }}
          head: ${{ github.event.pull_request.head.sha }}
          src-roots: .
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          REVIEWDOG_GITHUB_API_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

`GITHUB_TOKEN` is injected by GitHub automatically, so `GEMINI_API_KEY` is the only secret
you create.

The `fetch-depth: 0` and explicit `ref` matter: nayraa diffs two commits, and the action
does not check out your repository for you.

## How it works

```
git diff ──▶ context bundle ──▶ find candidates ──▶ refute each ──▶ rdjsonl ──▶ reviewdog
                                    (model)          (model)                    (comments)
```

The context bundle is assembled in priority order, and trimmed from the bottom up when it
exceeds the token budget:

| Section | What it is | Why |
| --- | --- | --- |
| `diff` | the unified diff | what changed |
| `changed_files` | full text of every changed file | a diff hunk is not enough context to judge |
| `importer_call_sites` | ±15 lines around each call site in dependent files | did this change break a caller |
| `siblings` | up to 2 files from the same directory | the authoritative statement of local convention |
| `imports` | full text of direct dependencies | is this change correct given what it calls |

Two details that matter more than they look:

**Sibling exemplars carry the convention load.** Showing the model the two files next to
the one being changed is a better statement of house style than any prose description of
it, because code is what the project actually does.

**High fan-out changes degrade honestly.** If a changed file has more than 30 dependents,
nayraa does not try to brute-force the blast radius. It reviews the change on its own
merits and reports one extra finding saying so — `high fan-out change: N dependents,
impact not machine-verified`. Silent truncation would read as "no problems found".

Under the token budget, `imports` degrades to signatures-only (function bodies replaced
with `pass`) before being dropped entirely, and `siblings` outlives it.

## Configuration

### Action inputs

| Input | Required | Default | Notes |
| --- | --- | --- | --- |
| `base` | yes | — | base commit SHA |
| `head` | yes | — | head commit SHA |
| `src-roots` | no | `.` | comma-separated package roots for import resolution |
| `model` | no | — | overrides the built-in default |

### Environment

| Variable | Notes |
| --- | --- |
| `GEMINI_API_KEY` | required |
| `REVIEWDOG_GITHUB_API_TOKEN` | required for posting; use `secrets.GITHUB_TOKEN` |
| `AI_REVIEW_MODEL` | optional model override |

If `src-roots` is wrong, the `imports` and `importer_call_sites` sections come back empty
and reviews get noticeably worse without failing. That is the first thing to check if
findings look shallow.

## CLI

The action is a thin wrapper. nayraa writes
[rdjsonl](https://github.com/reviewdog/reviewdog#reviewdog-diagnostic-format) to stdout and
never talks to the GitHub API itself:

```bash
nayraa --repo-root . --base "$BASE_SHA" --head "$HEAD_SHA" \
  | reviewdog -f=rdjsonl -name=nayraa -reporter=github-pr-review \
      -filter-mode=nofilter -level=warning
```

`-filter-mode=nofilter` is required. The default mode reports only on added lines, which
silently discards findings anchored to context lines.

## Observability

Every run writes counters to stderr:

```
candidates: 5
below_confidence: 1
refuted: 3
reported: 1
```

This is deliberate. A reviewer that reports nothing is indistinguishable from a broken one
unless it tells you *why* it said nothing. `candidates: 0` run after run means the first
pass is too strict; `candidates: 8, refuted: 8` means the second pass is.

## Language support

The import graph, symbol extraction and signature stripping are Python-only, built on the
standard library `ast` module — there is no parser dependency.

Other languages are still reviewed, with the `diff`, `changed_files` and `siblings`
sections. That is a real context, but it loses the dependency layer, which is where the
highest-yield findings tend to live.

| Files | Sections |
| --- | --- |
| `.py` | all five |
| everything else | `diff`, `changed_files`, `siblings` |

## Requirements

- Python 3.11+
- A Gemini API key
- One dependency (`google-genai`); everything else is standard library

## Limitations

- **Fork pull requests do not work.** GitHub withholds secrets and issues a read-only
  token for `pull_request` events from forks, so reviewdog cannot post. Do not reach for
  `pull_request_target` to fix this — it runs untrusted code with your secrets.
- **Project conventions are not wired into the action yet.** The CLI accepts `--rubric`
  pointing at a Markdown file appended to the first-pass prompt, but `action.yml` exposes
  no matching input. Use the CLI directly if you need it.
- **The token budget is 280K, well under Gemini's limit.** That is deliberate — reasoning
  over 800K tokens of code is measurably worse than over 200K — but it means very large
  pull requests get trimmed.
- **This is a young project** (`v0`). The interface may move. Pin the `v0` alias rather
  than assuming stability.

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
pyright
```

Tests use a fake model client throughout and make no network calls.
`scripts/live_api_smoke.py` exercises the real API path and is skipped when
`GEMINI_API_KEY` is unset.
