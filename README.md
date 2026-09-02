# nayraa

Reviews the **shape** of a GitHub pull request: whether it is the right thing to merge,
not whether its lines are correct. Bring your own Gemini key. One sticky comment. Never
blocks a merge.

nayraa does not review code for defects, and deliberately so. Every AI reviewer on the
market does that, several do it well, and this project measured itself doing it badly —
its own correctness pass proposed zero findings in 26 model calls on a diff containing two
real bugs. [Martian's Code Review Bench](https://codereview.withmartian.com/) puts the
best reviewer in the field at 68.6% recall and 56.3% precision, which is not a gap a small
project closes by trying harder. **Install cubic, Greptile, CodeRabbit or Gemini Code
Assist for the lines.** nayraa reviews the other axis, which none of them ask about.

Because a pull request can be free of defects, pass every test, and still be the wrong
thing to merge — it does four unrelated things at once, it adds a second way to do
something the codebase already does, it introduces an abstraction with one caller that
everyone will route around in six months. Writing code is cheap now; owning it is not.

## What it objects to

Exactly three kinds, and nothing else:

| Kind | Meaning |
| --- | --- |
| `mixed_concerns` | two or more unrelated goals that could each have shipped alone |
| `duplicate_mechanism` | a second way to do something the codebase already does |
| `unnecessary_complexity` | an abstraction or flag with one caller and no second one |

Three objections per pull request maximum. Every objection must name the changed paths
that carry it; one that cannot is dropped before it costs a second model call.

**It is forbidden from arguing about size.** A thousand-line mechanical rename is a good
pull request; a forty-line change that adds a second source of truth is not. Diff size,
file count and commit count are given to the model as *context*, never as evidence.
Encoding size as the metric would get gamed into stacked-garbage pull requests within two
sprints, and would cry wolf on every legitimate large refactor.

## How it works

```
git diff ──▶ shape signals ──▶ object ──▶ justify each ──▶ one sticky comment
             (deterministic)   (model)     (model)
```

Shape signals are computed from git with no model involved: files changed, added versus
modified versus deleted, line counts, directories touched, commit subjects, how many
changed files are tests.

**The second pass inverts the usual burden of proof.** A correctness finding has to
survive an attempt to *refute* it. A shape objection has to survive an attempt to
*justify* it — the author's case for why the pull request had to take this shape — and
uncertainty **keeps** the objection rather than dropping it. Demanding proof here would
silence the lane completely, because "this does four things" has no line to prove itself
on. The counterweights are the closed set of kinds, the mandatory path evidence, the
confidence floor and the cap of three.

## Quick start

```yaml
name: nayraa shape review
on: pull_request

permissions:
  contents: read
  pull-requests: write

concurrency:
  group: nayraa-${{ github.event.pull_request.number }}
  cancel-in-progress: true

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
```

`GEMINI_API_KEY` is the only secret you create. `GITHUB_TOKEN` is injected automatically.
The `concurrency` group matters: the comment is updated in place, so two overlapping runs
could otherwise each post their own.

`fetch-depth: 0` and the explicit `ref` matter too — nayraa diffs two commits, and the
action does not check out your repository for you.

### Inputs and environment

| Input | Required | Default | Notes |
| --- | --- | --- | --- |
| `base` | yes | — | base commit SHA |
| `head` | yes | — | head commit SHA |
| `model` | no | — | overrides the built-in default |

| Variable | Notes |
| --- | --- |
| `GEMINI_API_KEY` | required |
| `NAYRAA_MODEL` | optional model override |

## The comment

One sticky comment, updated in place on every push, posted on every run:

- **Objections** — each with the paths that carry it.
- **No objection** — stated explicitly when the lane ran and found nothing.
- **Could not be run** — stated explicitly when the lane failed.

Those last two are different claims and the comment never confuses them. A reviewer that
stays silent is indistinguishable from one that crashed.

## CLI

```bash
nayraa --repo-root . --base "$BASE_SHA" --head "$HEAD_SHA" --out shape.md
```

Writes the comment body to `--out` and nothing to stdout but counters on stderr. Posting
is the caller's job; the action does it with `gh`.

## Observability

```
shape: 12 files
shape_objections: 2
shape_dropped_before_justify: 1
shape_justified: 0
shape_reported: 1
```

`shape_justified` running high means the justify pass is too easy to satisfy;
`shape_objections: 0` run after run means the objection pass is too strict. Those counters
are how this project caught its own correctness lane returning nothing for weeks.

## Status

Verified on a fixture pair: a pull request with three planted shape defects drew objections
in 3 of 3 runs at confidence 0.90–1.00, naming the right files; a clean pull request drew
zero in 3 of 3. It correctly identified mixed concerns and a one-implementation strategy
abstraction, and **missed a duplicated retry helper** — `duplicate_mechanism` needs to see
code outside the diff, and the objection pass currently only sees the diff. That is the
known gap.

Beyond that fixture it is unmeasured. There is no public benchmark for pull request shape:
Code Review Bench scores line-level defect finding, which is the axis nayraa deliberately
does not compete on.

## Requirements

- Python 3.11+
- A Gemini API key
- One dependency (`google-genai`); everything else is standard library

## Limitations

- **Fork pull requests do not work.** GitHub withholds secrets for `pull_request` events
  from forks. Do not reach for `pull_request_target` — it runs untrusted code with your
  secrets.
- **`duplicate_mechanism` under-fires**, per the fixture above.
- **It needs `pull-requests: write` and a pull request event**, and is skipped otherwise.
- **This is a young project** (`v0`). Pin the `v0` alias rather than assuming stability.

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
pyright
```

Tests use a fake model client and make no network calls.
