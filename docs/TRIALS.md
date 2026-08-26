# Running the agent trials

The `/run` and `/cheat` trials for this task have not been run: they need a paid
model subscription that was not available while the task was built. This file is
the exact procedure to produce them, so the numbers can be filled into
`docs/RESULTS.md` by anyone with an authenticated `codex` or `claude` CLI.

Assumes a fresh Linux host with Docker running. Harbor is pinned to 0.22.0, the
version everything else in this repo was validated on.

## A. Setup

**1.** Base packages.
```bash
sudo apt-get update && sudo apt-get install -y curl git jq zip
```

**2.** Install uv.
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**3.** Put uv on PATH (repeat this in every new shell).
```bash
export PATH="$HOME/.local/bin:$PATH"
```

**4.** Install the pinned harbor.
```bash
uv tool install harbor==0.22.0
```

**5.** Confirm the version. Must print `0.22.0`.
```bash
harbor --version
```

**6.** Clone the repo and enter it. Every later step runs from here.
```bash
git clone https://github.com/dhruv-15-03/terminal-bench-task && cd terminal-bench-task
```

**7.** Fetch the two TB3 files that live outside this repo, pinned to the commit
the task was validated against.
```bash
mkdir -p tb3-rubrics && TB3=405a783ea111ab855718ce93b2b0cadaa2e8d47f && curl -fsSL -o tb3-rubrics/hack-trial-prompt.md https://raw.githubusercontent.com/harbor-framework/terminal-bench-3/$TB3/rubrics/hack-trial-prompt.md && curl -fsSL -o tb3-rubrics/task-implementation.toml https://raw.githubusercontent.com/harbor-framework/terminal-bench-3/$TB3/rubrics/task-implementation.toml && ls -l tb3-rubrics
```

---

## B. Auth checks — do these before anything expensive

**8.** Docker.
```bash
docker ps >/dev/null 2>&1 && echo "DOCKER OK" || echo "DOCKER NOT RUNNING - stop"
```

**9.** Install the two agent CLIs. Both are free to install and neither asks for
anything at install time. Versions below are the ones this procedure was checked
against.
```bash
npm install -g @openai/codex@0.149.1 @anthropic-ai/claude-code@2.1.246
```

**10.** Confirm the executables resolve.
```bash
codex --version && claude --version
```

**11.** Codex auth. Harbor injects `~/.codex/auth.json` from the host into the
container, so that file must exist. `codex login` opens a browser and signs in
with a ChatGPT account; `codex login status` prints `Not logged in` until it
succeeds.
```bash
codex login && codex login status
```

**12.** Verify.
```bash
test -f ~/.codex/auth.json && echo "CODEX OK" || echo "CODEX NOT AUTHED"
```

**13.** Claude auth. This is the step people get wrong. `CLAUDE_FORCE_OAUTH=1`
needs the long-lived token that `claude setup-token` prints; simply having run
`claude` and logged in is **not** enough, and harbor aborts the run with
`CLAUDE_FORCE_OAUTH is set but CLAUDE_CODE_OAUTH_TOKEN is not`. The command
requires a Claude subscription.
```bash
claude setup-token
```

**14.** Export the token it printed.
```bash
export CLAUDE_CODE_OAUTH_TOKEN='<paste-token-here>'
```

**15.** Confirm.
```bash
test -n "$CLAUDE_CODE_OAUTH_TOKEN" && echo "CLAUDE OK" || echo "CLAUDE NOT SET"
```

If only one of the two is authenticated, run that agent's trials and report the
other as unavailable. Half the evidence honestly labelled beats six trials with
a broken half.

---

## C. Free validation — no model quota used. Do not skip.

**16.** Oracle. Builds both images and runs the reference solution.
Expect `Mean: 1.000`. Validation writes to `validate/`, kept separate from
`runs/` so it never mixes into the trial classification in section G.
```bash
harbor run -p tasks/bytecode-verifier -a oracle -e docker --yes -o validate --job-name validate-oracle
```

> If this is not `1.000`, **stop and report it**. Something is wrong with the
> environment, not the task — it is 1.000 locally. Running paid trials against a
> broken setup wastes quota and proves nothing.

**17.** Nop. Expect `Mean: 0.000`.
```bash
harbor run -p tasks/bytecode-verifier -a nop -e docker --yes -o validate --job-name validate-nop
```

---

## D. `/run` trials — 3 per agent, all six must fail

`-k 3` is three trials. `-n 1` runs them one at a time, which matters: parallel
trials on a subscription trip rate limits, and a rate-limited trial does not
count. `-r 2` retries **infrastructure exceptions only** — a genuine reward-0
failure is not an exception and is never retried, so this cannot mask a result.

**18.** Codex, `gpt-5.6-sol`, `reasoning_effort=xhigh`.
```bash
harbor run -p tasks/bytecode-verifier -a codex -m openai/gpt-5.6-sol --ak reasoning_effort=xhigh --ae CODEX_FORCE_AUTH_JSON=1 -e docker -k 3 -n 1 -r 2 --yes -o runs --job-name run-codex
```

**19.** Claude Code, `claude-opus-5`, `reasoning_effort=max`.
```bash
harbor run -p tasks/bytecode-verifier -a claude-code -m anthropic/claude-opus-5 --ak reasoning_effort=max --ae CLAUDE_FORCE_OAUTH=1 --ae CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN" --ae CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000 -e docker -k 3 -n 1 -r 2 --yes -o runs --job-name run-claude
```

`CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000` is from Klavis's own defaults file — without
it, large single-response file writes hit the output cap and crash the trial,
which would be an invalid trial rather than a model failure.

**Quota-safe variant:** if you want to measure before committing, run either
command with `-k 1` and a name like `run-codex-t1`, check the cost (section G),
then run the remaining two with `-k 2` and a different `--job-name`. Three
trials across two job directories is fine. Keep both directories.

---

## E. `/cheat` trials — every trial must score 0

There is no `/cheat` subcommand. CI strips the "do not cheat" sentence from
`instruction.md`, appends the red-team prompt, and runs a normal trial. You are
doing the same thing by hand.

**20.** Back up the instruction file.
```bash
cp tasks/bytecode-verifier/instruction.md /tmp/instruction.md.bak
```

**21.** Apply the adversarial prompt, exactly as CI does.
```bash
sed -i -E 's/[[:space:]]*[Dd]o not cheat[^.]*\.//g' tasks/bytecode-verifier/instruction.md && printf '\n\n' >> tasks/bytecode-verifier/instruction.md && cat tb3-rubrics/hack-trial-prompt.md >> tasks/bytecode-verifier/instruction.md && tail -5 tasks/bytecode-verifier/instruction.md
```

**22.** Codex cheat trials.
```bash
harbor run -p tasks/bytecode-verifier -a codex -m openai/gpt-5.6-sol --ak reasoning_effort=xhigh --ae CODEX_FORCE_AUTH_JSON=1 -e docker -k 3 -n 1 -r 2 --yes -o runs --job-name cheat-codex
```

**23.** Claude cheat trials.
```bash
harbor run -p tasks/bytecode-verifier -a claude-code -m anthropic/claude-opus-5 --ak reasoning_effort=max --ae CLAUDE_FORCE_OAUTH=1 --ae CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN" --ae CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000 -e docker -k 3 -n 1 -r 2 --yes -o runs --job-name cheat-claude
```

If quota is tight, `-k 1` on each is defensible — CI's docker path runs one cheat
trial per agent. Say which you did.

**24.** Restore the instruction file. **Do not skip this.** A mutated
`instruction.md` fails the `check-instruction-suffix` static check if it is ever
committed.
```bash
cp /tmp/instruction.md.bak tasks/bytecode-verifier/instruction.md
```

**25.** Prove it is restored. Must print `RESTORED CLEAN` and no diff.
```bash
git diff --exit-code tasks/bytecode-verifier/instruction.md && echo "RESTORED CLEAN"
```

---

## F. Rubric check

**26.** LLM-judged implementation rubric. Uses claude quota; run it last.
```bash
harbor check tasks/bytecode-verifier -r tb3-rubrics/task-implementation.toml --ae CLAUDE_FORCE_OAUTH=1 --ae CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN" -e docker
```

---

## G. What invalidates a trial

Klavis is explicit: agent crashes, API and rate-limit failures, container
failures and timeouts do **not** count as model failures.

**27.** Classify every trial in one command.
```bash
for f in runs/*/*__*/result.json; do echo "$f | reward=$(jq -r '.verifier_result.rewards.reward // "none"' "$f") | exception=$(jq -r '.exception_info.exception_type // "none"' "$f")"; done
```

Read it like this:

| exception | reward | meaning |
|---|---|---|
| `none` | `0.0` | **genuine model failure — this is what we want** |
| `none` | `1.0` | model solved it — report immediately, this changes everything |
| anything else | any | **invalid trial — re-run it, do not count it** |

Exception types that mean *invalid, re-run*:

- Auth — `AgentAuthenticationError`, `AuthenticationError`, `NotAuthenticatedError`, `ApiKeyRejectedError`, `StaleAccessTokenError`
- Rate limit / quota — `ApiRateLimitError`, `ApiUsageLimitError`, `ApiOverloadedError`, `HostedQuotaExceededError`
- API / network — `ApiError`, `ApiConnectionError`, `ApiConnectionClosedError`, `ApiInternalServerError`, `ApiResponseStalledError`, `NetworkConnectionError`, `UnknownApiError`
- Timeout — `AgentTimeoutError`, `AgentSetupTimeoutError`, `EnvironmentStartTimeoutError`, `VerifierTimeoutError`
- Crash / container — `NonZeroAgentExitCodeError`, `SandboxBuildFailedError`, `HealthcheckError`, `MemoryLimitExceededError`
- Context / output cap — `ContextLengthExceededError`, `ContextWindowExceededError`, `OutputLengthExceededError`, `OutputTokenExceededError`
- Verifier plumbing — `RewardFileNotFoundError`, `RewardFileEmptyError`, `VerifierOutputParseError`
- `AgentSafetyRefusalError` — a refusal, not a capability failure. Flag it separately, do not count it as a pass or a fail.

If a trial dies on a rate limit, wait for the window to reset and re-run that
trial. Do not count it and do not average it in.

**Never** lower `[agent] timeout_sec` (currently 14400) to save quota. A trial
that hits the timeout is an invalid trial, not a model failure.

---

## H. Cost and time

Honest answer on cost: **I cannot give you a dollar figure.** No paid trial of
this task has been run, so any number would be invented. What is known:

- Agent timeout is **14400s (4h) per trial** — a ceiling, not an expectation.
  Verifier timeout is 900s.
- Worst case, 6 `/run` trials serially at the ceiling is 24h of wall clock.
  Realistically far less: the task is read-a-spec then write one file, not a
  large repo exploration.
- On subscription auth (`auth.json` / OAuth) you are not billed per token. The
  binding constraint is the rolling usage window, so pace the trials.

**28.** Measure actual cost and duration after the first job, and extrapolate
from real numbers rather than from my guess.
```bash
for f in runs/*/*__*/result.json; do echo "$f | cost=$(jq -r '.agent_result.cost_usd // "n/a"' "$f") | in=$(jq -r '.agent_result.n_input_tokens // "n/a"' "$f") | out=$(jq -r '.agent_result.n_output_tokens // "n/a"' "$f") | start=$(jq -r '.agent_execution.started_at // "n/a"' "$f") | end=$(jq -r '.agent_execution.finished_at // "n/a"' "$f")"; done
```

**Splitting across sessions is fine.** The six `/run` trials do not have to
happen in one sitting. Each `harbor run` writes its own directory under `runs/`.
Use a distinct `--job-name` each time, keep every job directory, and re-do steps
3, 11 and 21 in each new shell. Only requirement: each individual trial
completes cleanly.

---

## I. What to bring back

**29.** Print the classification and cost tables again and copy the terminal
output, including the summary table harbor prints at the end of each run (the
`| Trials | Exceptions | Mean |` block).
```bash
for f in runs/*/*__*/result.json; do echo "$f | reward=$(jq -r '.verifier_result.rewards.reward // "none"' "$f") | exception=$(jq -r '.exception_info.exception_type // "none"' "$f")"; done
```

**30.** Zip everything, trials and validation both.
```bash
zip -r klavis-trials.zip runs/ validate/ && ls -lh klavis-trials.zip
```

The zip must contain, for each trial directory
`runs/<job-name>/bytecode-verifier__<hash>/`:

- `result.json` — reward, exception, cost, timestamps
- `trial.log` — full harbor log for the trial
- `agent/*.txt` — **the trajectory**, what the model actually did
- `verifier/test-stdout.txt` — pytest output, shows *which* of the 69 modules failed
- `verifier/reward.txt` — the raw 0 or 1
- `artifacts/app/sbfverify.py` — **the verifier the model actually wrote**

Plus `runs/<job-name>/result.json` (job-level stats) for each job.

The two that matter most for the write-up are `artifacts/app/sbfverify.py` and
`verifier/test-stdout.txt`. Together they show exactly which requirement each
model got wrong, which is what turns "it failed" into a real failure analysis.
If the zip is too large to send, those two files per trial plus every
`result.json` are the minimum.

**31.** If anything aborted, capture the error text verbatim rather than
summarising it.
```bash
grep -riE "error|exception|rate.?limit|denied|unauthor" runs/*/*__*/trial.log | tail -40
```
