# Resource scope and current reproduction

The retained source-closed campaign completed all 70 scientific commands. Each command used one owned local runner and bounded child processes; no GPU, external compute, external model API, private dataset, or production service was used. Individual commands have a 180-second coordinator timeout.

## Measured coordinator record

The authoritative record is `results/reproduction/reproduction.json`.

- Retained executable source files: 23.
- Successful commands: 70.
- Semantic JSON comparisons: 68.
- Exact structured-input comparisons: 59.
- The complete 10,240-row collector trace was compared after gzip decompression.
- Sum of recorded completed-segment wall intervals: 344.690589299 seconds.
- Sum of command-child CPU observations: 446.240841 seconds.
- Sum of recorded coordinator CPU intervals: 0.567358503 seconds.
- Maximum coordinator RSS in the completion report: 141,428 KiB.

These are scoped process observations, not simultaneous whole-environment RSS or an exact cumulative interactive-session total. The first controller invocation was interrupted after two committed command records; a source-verified resume completed the campaign from that durable boundary. No scientific command is marked failed, but the run must not be described as one uninterrupted controller invocation. Time and resources consumed by the interrupted outer controller beyond committed records are not reconstructed as an exact total.

## Primary results and comparisons

The article's lookup figure retains the primary measured per-query data. Reproduction re-executes the grid but checks semantic results and consumed inputs rather than timing equality. The two evidence-journal campaigns retain their own primary timing fields in `collector-audit.json` and `collector-stateful.json`; they are not deployment-latency benchmarks, and database reopen counts are not process-crash counts.

The reproduction guard checks exact executable source bytes and source-set membership. All 23 executable Python files are compared with the snapshot from which the commands run. The standalone repository does not require a toolchain fingerprint or checksum manifest.
