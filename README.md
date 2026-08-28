# nayraa

AI code review for GitHub pull requests. Bring your own Gemini key, post through
[reviewdog](https://github.com/reviewdog/reviewdog), keep the whole thing in one small
Python package.

nayraa exists because most AI reviewers fail in one of two ways: they comment on
everything until people learn to scroll past them, or they are tuned so conservatively
that they never say anything at all. Both are useless, and the second is worse because it
looks healthy.

They also all review the same thing: lines of code. But a pull request can be free of
defects, pass every test, and still be the wrong thing to merge — because it does four
things at once, or adds a second way to do something the codebase already does. Writing
code is cheap now; owning it is not. So nayraa reviews along two axes, with separate
prompts and separate output:

- **Correctness** — is this code wrong? Inline comments, one per defect.
- **Shape** — is this the wrong thing to merge? One pull-request-level comment.

The test that separates them: would the objection still stand after every bug in the diff
was fixed? See [AGENTS.md](AGENTS.md) for why the two lanes need opposite burdens of proof.

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
  calls are made per lane. No tool calling, no multi-turn, no nondeterministic retrieval.

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

## Pull request shape

Off by default. Set `shape-review: "true"` to enable it.

```
git diff ──▶ shape signals ──▶ find objections ──▶ justify each ──▶ one sticky comment
             (deterministic)      (model)            (model)
```

Shape signals are computed from git without a model: files changed, added versus modified
versus deleted, line counts, directories touched, commit subjects, how many changed files
are tests. They are handed to the model as *context* about what kind of change this is.

The model may then raise at most three objections, of exactly three kinds:

| Kind | Meaning |
| --- | --- |
| `mixed_concerns` | two or more unrelated goals that could each have shipped alone |
| `duplicate_mechanism` | a second way to do something the codebase already does |
| `unnecessary_complexity` | an abstraction or flag with one caller and no second one |

Every objection must name the paths that carry it; one that cannot is dropped before it
costs a second model call.

**The reviewer is forbidden from arguing about size.** A thousand-line mechanical rename
is a good pull request; a forty-line change that adds a second source of truth is not.
Diff size is context, never evidence. Encoding size as the metric would get gamed into
stacked-garbage pull requests within two sprints, and would cry wolf on every legitimate
large refactor.

**The second pass inverts.** Where a correctness finding must survive an attempt to
*refute* it, a shape objection must survive an attempt to *justify* it — and uncertainty
keeps the objection instead of dropping it. Applying the correctness posture here would
silence the lane completely, because "this does four things" has no line to prove. The
counterweights are the closed set of kinds, the mandatory evidence, and the cap of three.

Results are posted as a single sticky comment, updated in place on each push and deleted
outright once the objections are gone. Nothing is ever posted inline, and nothing here
blocks a merge.

## Configuration

### Action inputs

| Input | Required | Default | Notes |
| --- | --- | --- | --- |
| `base` | yes | — | base commit SHA |
| `head` | yes | — | head commit SHA |
| `src-roots` | no | `.` | comma-separated package roots for import resolution |
| `model` | no | — | overrides the built-in default |
| `shape-review` | no | `"false"` | enable the shape lane and its sticky comment |

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

`--shape-out PATH` additionally runs the shape lane and writes the comment body to `PATH`
— markdown when there are objections, an empty file when there are none, and no file at
all if the lane failed. stdout stays pure rdjsonl either way, so the pipe is unaffected.
Posting that file is the caller's job; the action does it with `gh`.

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

With `shape-review` enabled, the shape lane writes its own counters:

```
shape: 12 files
shape_objections: 2
shape_dropped_before_justify: 1
shape_justified: 0
shape_reported: 1
```

`shape_justified` running high means the justify pass is too easy to satisfy;
`shape_objections: 0` run after run means the first shape pass is.

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
- **Shape review is unmeasured.** It is new, it is off by default, and no claim about its
  precision is anything but a stance until there is an eval set. It exists to collect the
  data that would let us judge it. Turn it on expecting to tune it.
- **Shape review needs `pull-requests: write` and a pull request event.** It posts through
  the GitHub API using `github.token`, so it is skipped outside `pull_request` runs and,
  like the inline lane, does not work on fork pull requests.
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
