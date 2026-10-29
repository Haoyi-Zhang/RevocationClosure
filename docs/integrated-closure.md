# Quota-conditioned closure consumer

This local test connects `capacity/capacity_store.py` receipts to the actual
`collector.ClosureJournal` and the same-information `DurableReference`. Receipt
bytes are not reconstructed or replaced by a hand-set mask. The root capability
module authenticates each receipt produced by the quota store. Their fixture
domains are compatible; they remain public experiment keys, not credentials.

Run from `capacity/`:

```sh
python -B integrated_closure.py --out results/fresh-integrated
python -B integrated_closure.py --out results/integrated-closure --verify --table ../../paper/integrated-closure.tex
```

The six cases cross a common five-grant cohort and a saturated twelve-grant
offered pool with append, separate-row reservation and target-row replacement.
R=12, U=2 and epsilon=2. Reservation and replacement have ordinary logical
grant limits 5 and 10. The grant prefix includes an unrevoked control, a valid
root/target and expiring unrelated pressure grants. The target deadlines are
(1000,1000,1000,40,40). Nodes 0-2 receive the revoke at modeled time 20; the
other two receive no revoke. One gateway process exits after its revoke commit
but before reply, then retries and supplies a real receipt. A collector process
exits after its time-42 commit but before reply. Both stores reopen in actual
subprocesses, not a simulated Boolean reset. Expired pressure rows are compacted
at time 42; two previously withheld descendant grants are actually admitted,
not left missing. A fresh worker checks both descendant depths and the unrelated
control at all five coordinates, using clock 43, and compares all 15 decisions
to the separate set/dictionary specification. The collector accepts clock 41 at
modeled time 43 (within error 2), retaining K=40 and matching the durable reference.

Five cases close at modeled time 42 and reject all 50 subsequent descendant
checks. Saturated append returns no receipts and stays open; its six live-audience
descendant checks allow, while four short-audience checks expire. This is the
expected absence of a completion guarantee, not post-completion resurrection.
All 30 unrelated-control checks allow. Eleven actual child exits return 70;
six recovery workers return 0 and check 42 database integrity results.

Offline verification recomputes the descendant/control totals from the individual
decisions, checks the distinct fifteen-coordinate product and the per-gateway
expected outcomes, and compares them with saved counters before table export.
It rejects a changed decision even when the same mutation is copied into both
summary and case records; mutation regressions exercise this boundary and the CLI.

Logical rows, allocated SQLite pages and DB/WAL/SHM extents have separate raw
fields. Five stores are summed only within a case. Common append/reservation use
28 rows after the revoke schedule, replacement 25; all allocate 25 database pages.
Those rows do not imply proportional byte savings. Recorded local revoke-call
elapsed intervals include selected subprocess startup/crash/retry, and are not a
SQL microbenchmark or a policy latency comparison. Closure 42 is a logical
observation time, not a measured network completion latency.

## Relation to a real systems concern

Chubby's upstream paper describes invalidation/lease coordination, recovery
waiting and client resource-growth review (Sections 2.7, 4.4, 4.5):
https://research.google/pubs/the-chubby-lock-service-for-loosely-coupled-distributed-systems/
https://storage.googleapis.com/gweb-research2023-media/pubtools/4444.pdf
These primary-source passages were checked on 2026-10-24. They ground the
design question of preserving a completion contract under resource bounds.
This harness is not a Chubby implementation, production maintenance history,
or an independently collected workload. The additional result is the explicit
link from quota admission to available receipt evidence and then quantified
hidden-descendant rejection. Reservation/replacement themselves are established
storage choices. In a nonnegative clock API, deadlines <=epsilon cannot support
use at all; d>2*epsilon is required for a guaranteed positive initial time-wise
window at t=0. Relative lifetimes must first be mapped into the same retained
epoch; this study does not justify resetting deadline epochs after reboot.
