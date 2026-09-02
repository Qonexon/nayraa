# Working on nayraa

This file is the standing brief for anyone changing this repository, human or agent.
Read it before adding a prompt, a pass, or a finding type.

## What nayraa is for

Writing code stopped being the expensive part. Reading it, owning it, and paying for it
every quarter after it merges did not. Code is a liability that happens to be useful, and
the volume of it a team can now produce in an afternoon has outrun the rate at which that
team can absorb the consequences.

So the job nayraa is built for is not authoring. It is curation: deciding what is allowed
to enter the codebase and stay there.

An AI reviewer that only finds bugs is treating a symptom. A pull request can be entirely
free of defects, pass every test, and still be the wrong thing to merge — because it does
four things at once, or adds a second way to do something the codebase already does, or
introduces an abstraction with one caller that everyone will route around in six months.
Green tests are not evidence of good architecture. They are evidence of the absence of one
particular class of harm.

## One lane

nayraa reviews whether a pull request is the right thing to merge. It does **not** review
whether the code is correct, and adding that back is not a good idea. It was tried: the
correctness pass proposed 0 findings in 26 model calls on a diff containing two real
defects, and the best reviewer on Martian's Code Review Bench manages 68.6% recall at
56.3% precision. Install a commercial reviewer for the lines; several are good at it and
none of them ask the shape question.

**The lane test.** Would the objection still stand after every bug in the diff was fixed?
If no, it is not ours — it belongs to whatever line-level reviewer is installed. An
objection that cannot answer this question is not an objection.

## Why the burden of proof inverts

A correctness claim can be settled: either the code path is reachable and the failure is
real, or it is not. A shape claim cannot. "This pull request does four unrelated things"
has no line number to point at and no execution to prove, so demanding proof kills every
objection by uncertainty — and the reviewer goes permanently silent while looking healthy.
That failure mode is worse than noise, because nothing tells you it is happening.

So the second pass asks for *justification*, not refutation: the objection stands unless a
concrete necessity for the shape can be stated from the diff. Not a preference, not a plan,
not "it was convenient" — a reason the pull request could not have been split, or could
not have used the mechanism that already exists. The counterweights to that permissiveness
are structural, not tonal: three objection kinds and no others, mandatory path evidence, a
hard cap of three, and a confidence floor.

## Rules

**Never argue from size.** A thousand-line mechanical rename is a good pull request. A
forty-line change that introduces a second source of truth is not. Diff size, file count
and commit count are given to the model as *context*, never as evidence, and the prompt
forbids reasoning from them. Size is the symptom people notice; the disease is the number
of distinct concerns and the duplication of mechanism. Encode the disease. A tool that
scores line counts gets gamed into stacked-garbage pull requests within two sprints.

**The schema is the filter.** A reviewer that is not afraid to say no is not produced by
telling a model to be harsh — that yields confident noise, not signal. It is produced by
leaving nowhere to put a hedge: two severities and no `nit`, three objection kinds and no
`other`, a required concrete failure or a required evidence path. When you want the
reviewer to be more decisive, tighten the schema, not the adjectives.

**Noise is the enemy, not missed findings.** A reviewer nobody reads is worth zero. But
never say that to the model: telling a pass that zero findings is a common answer is how
this project spent 26 calls proposing nothing on a diff with two real defects. Spend
recall in the schema and in the second pass, where it is bounded, not in the instruction
that decides whether the first pass looks at all.

**Objections never block a merge.** The tool exits 0 no matter what, including when it
crashes.

**Do not add a knob you cannot measure.** Prompt bullets are not free — every named
pattern is a prior that makes the model hunt for that pattern and find it where it is not.
If you loosen the finder and the refuter in the same change, you have moved precision in
an unknown direction. Say so in the pull request, and prefer changing one end at a time.

**Measure on a fixture pair, not on a hunch.** The lane was validated by running it
against a pull request with three planted shape defects and a clean control: 3/3 runs
objected on the bad one naming the right files, 0/3 on the good one. Three separate
readings earlier that day, each from a single sample, were all overturned by running the
same thing five more times. One sample is not a result. There is no public benchmark for
pull request shape, so fixtures are what we have.

**Say what happened, even when nothing did.** The comment is posted on every run,
including empty ones, and distinguishes three states: objections, no objection, and could
not be run. A reviewer that stays silent is indistinguishable from one that crashed, and
"the lane found nothing" is a different claim from "the lane never ran". This project
shipped that exact bug once — a crashed lane reporting an all-clear.

## Layout

| Module | Job |
| --- | --- |
| `gitdiff` | all git access |
| `shape` | deterministic pull-request shape signals, no model |
| `model` | the Gemini client and the fake used in tests |
| `passes` | the two model calls: object, justify |
| `comment` | markdown for one sticky comment |
| `budget` | every tunable constant |
| `cli` | wiring |

One job per module, tunables in `budget`, no comments or docstrings in the source. Tests
use a fake model client and make no network calls.
