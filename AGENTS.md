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
| Second pass | refute | justify |
| Status | in use | new, unmeasured |

**The lane test.** Would the objection still stand after every bug in the diff was fixed?
If no, it is lane 1. If yes, it is lane 2. A finding that cannot answer this question is
not a finding.

## Why the burden of proof inverts

Lane 1 defaults to refuted. A correctness claim can be settled: either the code path is
reachable and the failure is real, or it is not, and the context usually contains enough
to decide. Demanding proof costs recall and buys precision, which is the trade this
project wants.

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
trade here spends recall to buy precision. But never say that to the model: telling a
finder that zero findings is a common answer is how this project spent 26 calls proposing
nothing on a diff with two real defects. Spend recall in the schema and in the second pass,
where it is bounded, not in the instruction that decides whether the first pass looks at
all.

**Findings never block a merge.** The tool exits 0 no matter what, including when it
crashes. A lane-2 failure must never take lane 1 down with it.

**Do not add a knob you cannot measure.** Prompt bullets are not free — every named
pattern is a prior that makes the model hunt for that pattern and find it where it is not.
If you loosen the finder and the refuter in the same change, you have moved precision in
an unknown direction. Say so in the pull request, and prefer changing one end at a time.

**Lane 2 is unmeasured.** It is on by default because it only produces the data that would
let us judge it by running. Until there is an eval set — real pull requests, known planted
defects, hit rate and false-positive rate — no claim about either lane's precision is
anything more than a stance. Building that harness beats adding another prompt bullet to
either lane.

**Capability and permission are separate.** When a pass produces nothing, check both what
the prompt forbids and what the pass is structurally incapable of. A prompt that says zero
findings is valid will produce exactly that. Adding tools to read the codebase alone changes
nothing. Reframing without tools helps only slightly. Only changing both prompt and
capability together moved the outcome.

**Say what happened, even when nothing did.** Both lanes report into one sticky comment
that is posted on every run, including empty ones. A reviewer that stays silent is
indistinguishable from one that crashed, and "nothing survived either lane" is a different
claim from "this code is fine". The comment says which.

## Layout

| Module | Job |
| --- | --- |
| `gitdiff` | all git access |
| `importgraph` | who imports whom |
| `callsites` | symbols, call sites, siblings, signature stripping |
| `bundle` | assemble and trim the context bundle |
| `shape` | deterministic pull-request shape signals, no model |
| `model` | the Gemini client and the fake used in tests |
| `tools` | the three read-only tools the finding pass can call (read_file, search, list_dir) |
| `passes` | the model calls: find, format, refute, assess shape, justify |
| `rdjson` | lane 1 output — rdjsonl for reviewdog |
| `comment` | both lanes' summary — markdown for one sticky comment |
| `budget` | every tunable constant |
| `cli` | wiring |

One job per module, tunables in `budget`, no comments or docstrings in the source. Tests
use a fake model client and make no network calls.
