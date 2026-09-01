# nayraa

Reviews the **shape** of a GitHub pull request, and runs an existing reviewer for the
lines. Bring your own Gemini key, post through
[reviewdog](https://github.com/reviewdog/reviewdog), keep the whole thing in one small
Python package.

Every AI reviewer on the market reviews the same thing: lines of code. But a pull request
can be free of defects, pass every test, and still be the wrong thing to merge — because
it does four things at once, or adds a second way to do something the codebase already
does. Writing code is cheap now; owning it is not. So nayraa reviews along two axes:

- **Correctness** — is this code wrong? Delegated to
  [open-code-review](https://github.com/alibaba/open-code-review), filtered through
  nayraa's noise policy, posted as inline comments.
- **Shape** — is this the wrong thing to merge? nayraa's own, and the reason it exists.
  One pull-request-level comment.

The test that separates them: would the objection still stand after every bug in the diff
was fixed? See [AGENTS.md](AGENTS.md) for why the two lanes need opposite burdens of proof.

## Design stance

**Noise is the enemy, not missed findings.** A reviewer nobody reads has a value of zero,
so every design decision here trades recall for precision.

- **Two values of severity — `blocker` and `major`.** There is no `nit`, `suggestion`, or
  `info` level, so the model has nowhere to put one. The schema is the filter.
- **Three findings per pull request, maximum.**
- **Formatting, naming, import order, unused code and missing tests are out of scope.**
  Your linter and type checker already decide those, and they are always right and always
  free. Turn them on first; nayraa is for what they cannot decide.
- **Findings never block a merge.** The tool exits 0 no matter what — including when it
  crashes. A broken reviewer must not stop your team from shipping.
- **Correctness review is somebody else's job.** nayraa used to implement its own, and
  it was measured proposing 0 findings in 26 model calls on a diff containing two real
  defects. [Martian's Code Review Bench](https://codereview.withmartian.com/) puts the
  best tool in the field at 68.6% recall and 56.3% precision — not a gap a small project
  closes by trying harder. So the lane is delegated and the policy is kept.

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
git diff ──▶ ocr ──────────▶ JSON ──▶ nayraa policy ──▶ rdjsonl ──▶ reviewdog
             (agent loop)                                           (comments)
```

The correctness lane runs `ocr review --from <base> --to <head> --format json` and parses
what comes back. `ocr` is [open-code-review](https://github.com/alibaba/open-code-review)
(Apache-2.0): a single Go binary with no server and no database, driving a real agent loop
with its own read-only tools over your checkout. The action installs it for you and it
uses the same `GEMINI_API_KEY`.

nayraa's contribution is the filter on the way out:

| Engine value | Becomes |
| --- | --- |
| severity `critical`, `high` | `blocker` |
| severity `medium` | `major` |
| severity `low` | dropped |
| category `bug`, `security`, `performance`, `data`, `api`, `concurrency`, `other` | kept |
| category `style`, `documentation`, `test`, `maintainability` | dropped |

Then excluded paths are dropped and the result is capped at three findings, blockers
first. That is the whole lane: a subprocess and a policy.

**The engine is swappable on purpose.** Set `engine` to any shell command containing
`{base}` and `{head}` that writes findings JSON to stdout, and nayraa will run that
instead. Never couple to one vendor beyond the mapping above.

## Pull request shape

On by default. Set `summary-comment: "false"` to turn the lane and its comment off.

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

**The burden of proof is inverted.** A correctness finding has to survive an attempt to
*refute* it. A shape objection has to survive an attempt to *justify* it — and uncertainty
keeps the objection instead of dropping it. Demanding proof here would silence the lane
completely, because "this does four things" has no line to prove itself on. The
counterweights are the closed set of kinds, the mandatory evidence, and the cap of three.

## The summary comment

Both lanes report into one sticky comment, updated in place on every push. It is posted on
every run, including runs that found nothing:

- **Code defects** — a table of what the correctness lane reported, with severity and
  location. Every row is also posted inline on the line it concerns; the table exists so
  the state of a review is legible without hunting through the Files tab.
- **Shape** — the objections, with the paths that carry each one.
- **No issues found** — stated explicitly when both lanes came back empty.

That last case is the point of always posting. A reviewer that stays silent is
indistinguishable from one that crashed, and "nothing survived either lane" is a different
claim from "this code is fine" — the comment says which one it is. A lane that failed says
so too, rather than reporting its silence as an all-clear. Shape objections never appear
inline, and nothing here blocks a merge.

Because the comment is updated in place, give the workflow a `concurrency` group keyed on
the pull request (as the example does). Without one, two overlapping runs can each find no
existing comment and post their own, and the slower run wins.

## Configuration

### Action inputs

| Input | Required | Default | Notes |
| --- | --- | --- | --- |
| `base` | yes | — | base commit SHA |
| `head` | yes | — | head commit SHA |
| `engine` | no | `ocr` | correctness engine, or a command template with `{base}` and `{head}` |
| `model` | no | — | overrides the built-in default |
| `summary-comment` | no | `"true"` | shape lane plus the sticky summary comment |

### Environment

| Variable | Notes |
| --- | --- |
| `GEMINI_API_KEY` | required; used by both the engine and the shape lane |
| `REVIEWDOG_GITHUB_API_TOKEN` | required for posting; use `secrets.GITHUB_TOKEN` |
| `AI_REVIEW_MODEL` | optional model override for the shape lane |

It remains the only secret you create.

## CLI

The action is a thin wrapper. It needs `ocr` on `PATH`
(`npm install -g @alibaba-group/open-code-review`) unless you pass your own `--engine`.
nayraa writes
[rdjsonl](https://github.com/reviewdog/reviewdog#reviewdog-diagnostic-format) to stdout and
never talks to the GitHub API itself:

```bash
nayraa --repo-root . --base "$BASE_SHA" --head "$HEAD_SHA" \
  | reviewdog -f=rdjsonl -name=nayraa -reporter=github-pr-review \
      -filter-mode=nofilter -level=warning
```

`-filter-mode=nofilter` is required. The default mode reports only on added lines, which
silently discards findings anchored to context lines.

`--engine` takes `ocr` (the default) or a command template. `--summary-out PATH` runs the
shape lane and writes the summary comment body to `PATH`. The file is always written,
including when nothing was found; if either lane fails, the summary is still written and
says which one could not be reviewed. stdout stays pure rdjsonl either way, so the pipe is
unaffected. Posting that file is the caller's job; the action does it with `gh`.

## Observability

Every run writes counters to stderr:

```
defects: 1
shape: 12 files
shape_objections: 2
shape_dropped_before_justify: 1
shape_justified: 0
shape_reported: 1
```

This is deliberate. A reviewer that reports nothing is indistinguishable from a broken one
unless it tells you *why* it said nothing. `shape_justified` running high means the justify
pass is too easy to satisfy; `shape_objections: 0` run after run means the objection pass
is too strict. That second counter is how the old correctness lane was caught returning
nothing for weeks.

## Language support

Whatever the engine supports. nayraa's own half — the shape lane and the policy filter —
is language-agnostic: it reads git metadata and the engine's JSON, never source syntax.
The Python-only import graph that used to constrain this is gone.

## Limitations

- **Fork pull requests do not work.** GitHub withholds secrets and issues a read-only
  token for `pull_request` events from forks, so reviewdog cannot post. Do not reach for
  `pull_request_target` to fix this — it runs untrusted code with your secrets.
- **The correctness lane is only as good as the engine.** nayraa contributes the policy,
  not the finding. If `ocr` misses a defect, so does nayraa. Neither lane has been run
  against [Code Review Bench](https://codereview.withmartian.com/), so no precision or
  recall number is claimed here.
- **Shape review is unmeasured.** It is new, it is on by default so that it produces the
  data that would let us judge it, and until there is an eval set no claim about its
  precision is anything but a stance. Expect to tune it; `summary-comment: "false"` turns
  it off.
- **The summary comment needs `pull-requests: write` and a pull request event.** It posts
  through the GitHub API using `github.token`, so it is skipped outside `pull_request`
  runs and, like the inline lane, does not work on fork pull requests.
- **This is a young project** (`v0`). The interface may move. Pin the `v0` alias rather
  than assuming stability.

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
pyright
```

Tests use a fake model client throughout, never invoke the engine, and make no network
calls. `scripts/live_api_smoke.py` exercises the real API path and is skipped when
`GEMINI_API_KEY` is unset.
