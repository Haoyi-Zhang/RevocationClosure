# Recovery-Stable Revocation Closure

A finite authorization model and durable completion-evidence journal for a fixed
five-gateway audience. The SQL implementation, set/dictionary interpreter and
owned loopback harness exercise authorization, recovery and revocation closure.
The accompanying paper is *Recovery-Stable Revocation Closure for Offline
Capability Delegation* (TDSC).

## Requirements

Python 3.10+ and its standard library, including SQLite. The complete reproduction
uses Linux/POSIX process and resource interfaces, writable local storage and
owned loopback sockets. It needs no external service, dataset download or
credentials. Keep Python assertions enabled; do not use `-O`.
`ENVIRONMENT.md` describes the process model and paper-build dependencies.

## Reproduce

Run from this directory in a POSIX shell. Choose a fresh output outside the
checkout, leaving `results/` unchanged:

```sh
OUT="${TMPDIR:-/tmp}/revocation-run"
python3 -B reproduce.py --out "$OUT" --compare results --max-commands 3
python3 -B reproduce.py --out "$OUT" --compare results --resume --max-commands 3
```

Repeat the resume command until `$OUT/reproduction.json` reports `complete`,
or omit `--max-commands` for one uninterrupted run. A run executes 71 commands
from its retained source snapshot and compares 69 semantic JSON results,
59 structured inputs and the decompressed 10,240-row collector trace. Resume
requires unchanged executable source bytes and membership; use a fresh output
after changing source. Timing and process telemetry are not equality targets.

The 71-command run covers the gateway and collector campaigns, not every later
study. The principal reproduction families are:

| Result family | Entry point | Retained outputs |
| --- | --- | --- |
| Gateway and collector correspondence/recovery | `reproduce.py` | `results/` and `results/reproduction/` |
| Same-information durable reference | `collector_comparison.py` | `results/collector-comparison/` |
| Quota progress, finite states and 750-case SQL comparison | `capacity/run.py` stages `finite`, `directed`, `campaign`, `verify` | `capacity/results/` |
| Admission-to-closure composition | `capacity/integrated_closure.py` | `capacity/results/integrated-closure/` |

The capacity commands and fresh-output requirements are in `capacity/README.md`.
The claim ledger maps the abstract's counts to these separate families. Running
one family does not recertify another family's historical timing or storage data.

## Focused checks

```sh
python3 -B tests/compaction_transactions.py
python3 -B tests/replay_input_contract.py
python3 -B verify_history.py --directory results
python3 -B lookup_batch.py
python3 -B collector_comparison.py --out "${OUT}-collector"
```

The first two commands use disposable local data. History verification reads the
eight retained histories without writing them. The lookup and collector controls
compare the optimized and straightforward implementations under the same
authorization contract. Their optional `--measure` modes require a separate
fresh output; normal correctness checks do not replace retained timings.

The record-budget module has its own confined output layout and commands in
`capacity/README.md`. Its finite, directed, campaign and replay stages distinguish
common admitted workloads from saturated offered pools.
`docs/capacity-progress.md` defines its quotas, progress conditions and row costs.

## Code and evidence

| Location | Role |
|---|---|
| `capability.py` | SQL records, attenuation, ancestry decisions, admission and reclamation |
| `verifier.py` | Separate set/dictionary authorization interpreter |
| `server.py`, `transport.py` | Five sockets and five stores in one owned server process |
| `separate_processes.py` | Five independent owned gateway processes, collector commit-boundary exits and late descendants |
| `collector.py`, `collector_reference.py` | Durable evidence join and same-contract latest-state reference |
| `lookup_batch.py` | Local batched/sequential ancestry comparison |
| `results/` | Retained primary inputs, decisions, traces and measurements |
| `results/reproduction/` | Retained source-closed run, command logs and comparisons |
| `proofs.md`, `collector-proofs.md` | Gateway arguments and journal characterization |
| `claim_evidence_ledger.csv` | Claim-to-proof, implementation and result mapping |
| `source_notes.md`, `external_resources.csv` | Sources, provenance and licenses |

The original five endpoints share one host and one gateway-service process. The model
uses fixed honest membership, authentic immutable records, bounded nonnegative
clocks and non-rollback durable storage. Public fixture keys are model inputs,
not production credentials. Local recovery tests distinguish transaction
rollback, reply loss and database reopen from physical power loss.

A separate recovery study starts five simultaneous gateway processes on one host.
It restarts one gateway without terminating its four peers, then all five gateways;
two collector exits bracket commit. Twenty post-completion checks of descendants
at two depths reject and match the separate interpreter. The same-information
durable reference returns the same completion state. Stateless and volatile
controls retain their distinct failures. Keys and bounded clocks remain fixtures;
independent hosts, authenticated user sessions and power loss are not tested.

```sh
python3 -B tests/test_separate_processes.py
python3 -B separate_processes.py verify --directory results/process-separation
python3 -B separate_processes.py run --out "${OUT}-processes" --compare results/process-separation/summary.json
```

The process study is portable to Windows and POSIX; the original full campaign
still requires POSIX. Retained process IDs and ports identify the captured run,
not equality targets across runs. Stable decisions and scope are compared exactly.

`STATISTICAL-NOTES.md` explains the actual denominators and error bars.
`resource_accounting.md` describes the retained campaign, not an assumed source
count for a future run. Collector and ancestry measurements retain all paired
outcomes, including slower cases; they measure local SQLite work rather than
WAN closure or deployment gains.

The paired collector timing range reported in the paper and claim ledger comes
from `results/collector-comparison/timing-isolated/measurement.json`. The separate
capture at `results/collector-comparison/timing/measurement.json` uses the same
declared case plan but contains its own paired observations. It remains as
additional measurement evidence, not an alternative manuscript source or a
replacement for the cited capture. The two captures are not pooled. Both retain
their own environment, observed timings and slower cases unchanged; neither is
relabeled as a new execution by this documentation update.

## Paper

The complete project also contains `paper/`; from that directory run
`sh build.sh` for the main manuscript and separate supplement. The script uses
the supplied unmodified IEEEtran class/style and an isolated temporary build.
The standalone code repository intentionally contains only this artifact.

The three protocol schematics are drawn directly by
`figures/draw_schematics.py` using ReportLab and the manuscript's URW Times
font from TeX Live. With `kpsewhich` on `PATH`, regenerate them with
`python3 -B figures/draw_schematics.py`. The resulting vector PDFs embed
the font and are included by the manuscript without rasterization.
# Connected quota-to-closure case

The added `capacity/integrated_closure.py` study connects real quota-store
fixture receipts, both completion collectors, admitted late descendants and
actual subprocess recovery. Reproduction, raw inputs and the same-contract
comparison are described in `docs/integrated-closure.md`. It is separate from
the retained 71-command campaign and the 750-case capacity campaign; neither
is relabeled as a rerun. The supplied six-case result is under
`capacity/results/integrated-closure/`.
