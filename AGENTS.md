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

## Two lanes

nayraa reviews every pull request along two independent axes. They have different
questions, different prompts, different output channels, and — this is the part that is
easy to get wrong — different burdens of proof.

| | Lane 1 — correctness | Lane 2 — shape |
| --- | --- | --- |
| Question | Is this code wrong? | Is this the wrong thing to merge? |
| Would a perfect test suite catch it? | Yes, in principle | No, never |
| Output | inline comments on lines | one pull-request-level comment |
| Burden of proof | on the finding | on the author |
| Default when uncertain | drop it | keep it |
| Who reviews | an external engine | nayraa |
| Second pass | the engine's own | justify |
| Status | delegated | the reason this project exists |

**The lane test.** Would the objection still stand after every bug in the diff was fixed?
If no, it is lane 1. If yes, it is lane 2. A finding that cannot answer this question is
not a finding.

## Why the burden of proof inverts

Lane 1 defaults to dropped. A correctness claim can be settled: either the code path is
reachable and the failure is real, or it is not. We no longer make that judgement
ourselves — the engine does — but we still apply the policy on the way out: two
severities, out-of-scope categories discarded, three findings maximum.

Lane 2 cannot work that way. "This pull request does four unrelated things" has no line
number to point at and no execution to prove. Apply lane 1's posture to it and every
objection dies of uncertainty — the reviewer goes permanently silent and looks healthy
while doing it. That failure mode is worse than noise, because nothing tells you it is
happening.

So lane 2 inverts: the objection stands unless a *concrete necessity* for the shape can be
stated from the provided context. Not a preference, not a plan, not "it was convenient" —
a reason the pull request could not have been split, or could not have used the mechanism
that already exists. The counterweights to that permissiveness are structural, not
tonal: three objection kinds and no others, mandatory path evidence, a hard cap of three,
and a confidence floor.

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

**Noise is the enemy, not missed findings.** A reviewer nobody reads is worth zero. Every
trade here spends recall to buy precision. Zero findings is a valid and common answer in
both lanes.

**Findings never block a merge.** The tool exits 0 no matter what, including when it
crashes. A lane-2 failure must never take lane 1 down with it.

**We do not implement correctness review.** Lane 1 shells out to an existing engine and
maps its output through our noise policy. This is not modesty, it is measurement: our own
finding pass returned 0 candidates in 26 calls on a diff with two real defects, and
Martian's Code Review Bench puts the best tool in the field at 68.6% recall and 56.3%
precision. That is not a gap a one-person project closes by trying harder. Our value is
the policy and lane 2, so spend the effort there. The engine is swappable on purpose —
never couple to one vendor's JSON beyond the mapping in `finder`.

**Capability and permission are separate, and neither alone is enough.** When a pass
produces nothing, ask both what the prompt forbids and what the pass structurally cannot
do. Measured on the same diff: the old prompt single-shot found 0/26; the old prompt with
tools found 0/4; proposal framing without tools ~1/5; proposal framing with tools 6/9.
Neither change worked alone. Never conclude from one sample — three separate readings in
one afternoon were overturned by running the same thing five more times.

**Do not add a knob you cannot measure.** Prompt bullets are not free — every named
pattern is a prior that makes the model hunt for that pattern and find it where it is not.
If you loosen the objection pass and the justify pass in the same change, you have moved
precision in an unknown direction. Say so in the pull request, and change one end at a
time.

**Lane 2 is unmeasured.** It is on by default because it only produces the data that would
let us judge it by running. Until there is an eval set — real pull requests, known planted
defects, hit rate and false-positive rate — no claim about either lane's precision is
anything more than a stance. Building that harness beats adding another prompt bullet to
either lane.

**Say what happened, even when nothing did.** Both lanes report into one sticky comment
that is posted on every run, including empty ones. A reviewer that stays silent is
indistinguishable from one that crashed, and "nothing survived either lane" is a different
claim from "this code is fine". The comment says which.

## Layout

| Module | Job |
| --- | --- |
| `gitdiff` | all git access |
| `finder` | lane 1 — run the external engine, map its JSON through our policy |
| `shape` | deterministic pull-request shape signals, no model |
| `model` | the Gemini client and the fake used in tests |
| `passes` | lane 2's model calls: assess shape, justify |
| `rdjson` | lane 1 output — rdjsonl for reviewdog |
| `comment` | both lanes' summary — markdown for one sticky comment |
| `budget` | every tunable constant |
| `cli` | wiring |

One job per module, tunables in `budget`, no comments or docstrings in the source. Tests
use a fake model client and make no network calls.
