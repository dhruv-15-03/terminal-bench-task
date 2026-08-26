# bytecode-verifier — a Terminal-Bench 3 task

One original task for [Terminal-Bench 3](https://github.com/harbor-framework/terminal-bench-3),
laid out so the directory can be dropped into a fork of that repository
unchanged.

The agent is asked to implement the static safety verifier for SBF1, a small
bytecode format for sandboxed plugins. The runtime already exists in the
container; the verifier does not. A module is safe when no execution of it can
read an uninitialised register, touch memory outside the scratch region, divide
by zero, hit the `INT64_MIN / -1` trap, or transfer control outside the
instruction stream.

The constraint that makes it hard is that the verifier must be neither too
strict nor too lax. `/app/spec/SBF.md` pins down the abstract domain, every
transfer function, the branch refinements, the join, the fixpoint schedule and
the error reporting order precisely enough that two correct implementations
agree on every module. Rejecting a module the spec calls safe fails exactly as
hard as accepting one it calls unsafe.

## Layout

```
tasks/bytecode-verifier/
  instruction.md            what the agent is told
  README.md                 reviewer-facing metadata and explanations
  task.toml                 config and metadata
  environment/
    Dockerfile              agent container
    spec/SBF.md             the authoritative specification
    tools/sbfasm.py         assembler and disassembler
    tools/sbfrun.py         concrete interpreter, the runtime being protected
    samples/samples.py      builds the public worked examples at image build
    skeleton/sbfverify.py   stub the agent replaces
  solution/
    solve.sh                oracle entry point
    sbfverify.py            reference verifier
  tests/
    Dockerfile              verifier image
    test.sh                 verifier entry point
    test_verifier.py        grading harness
    corpus.py               hidden corpus, 69 modules
    sbfasm.py               assembler, baked into the verifier image
```

## Running it

Needs [Harbor](https://github.com/laude-institute/harbor) and a running Docker
daemon. The static checks come from the terminal-bench-3 repository, so run
them from a checkout of it with this task copied into `tasks/`.

```bash
for check in checks/check-*.sh; do bash "$check" tasks/bytecode-verifier; done

harbor check tasks/bytecode-verifier -r rubrics/task-implementation.toml

harbor run -p tasks/bytecode-verifier --agent oracle   # expects reward 1.0
harbor run -p tasks/bytecode-verifier --agent nop      # expects reward 0.0
```

## Results

[docs/RESULTS.md](docs/RESULTS.md) has the commands actually run, their output,
and the failure analysis.

| stage | result |
|---|---|
| static checks (22) | pass |
| Docker build, both images | pass |
| oracle validation | reward 1.0 |
| nop validation | reward 0.0 |
| anti-cheat probes | 6/6 score 0 |
| `/run` agent trials | not yet run |
| `/cheat` agent trials | not yet run |
| implementation rubric | not yet run |

Validated against `harbor-framework/terminal-bench-3` at
`c9ffbe1`, with harbor 0.22.0.

The three outstanding rows need a paid model subscription that was not
available while building this. Every command needed to produce them is written
out in [docs/TRIALS.md](docs/TRIALS.md). No trial number anywhere in this
repository is estimated, extrapolated or invented — the rows above say "not yet
run" because they have not been run.

## Grading integrity

The verifier runs in its own container built from `tests/Dockerfile`, started
after the agent's container has been destroyed. The only thing that crosses
over is the single declared artifact, `/app/sbfverify.py`. The tests, the
corpus and the reward file are never present in the agent's container, so they
cannot be edited, and the expected verdicts are never written anywhere the
agent can reach.

Inside the verifier container the candidate is executed once per module as an
unprivileged user, with the module on stdin and no path into `/tests`, and
`/tests` is mode 700 owned by root. `test_corpus_is_not_readable_by_candidate`
asserts that this holds rather than assuming it.

## Licence

MIT, see [LICENSE](LICENSE).
