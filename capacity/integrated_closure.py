"""Owned quota-store -> authentic fixture receipt -> collector/recovery chain."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from collector import ClosureJournal
from collector_reference import DurableReference
from capability import receipt_authenticated
from capacity_store import CapacityStore, CapacityError
from fixtures import grant, revoke, owned
import reference

BUDGET, UNSEEN, EPSILON = 12, 2, 2


def open_store(folder, policy, node):
    return CapacityStore(folder/f"gateway-{node}.sqlite", policy, BUDGET, UNSEEN, node, EPSILON)


def invoke(folder, action, policy, expected=0):
    run = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()),
                          "--worker", action, "--out", str(folder), "--policy", policy],
                         capture_output=True, text=True, timeout=20)
    if run.returncode != expected:
        raise ValueError((action, run.returncode, run.stderr))
    return {"action": action, "exit_code": run.returncode,
            "result": json.loads(run.stdout) if run.stdout.strip() else None}


def worker(folder, action, policy):
    plan = json.loads((folder/"inputs.json").read_text(encoding="utf-8"))
    if action == "gateway-commit":
        s = open_store(folder, policy, 1)
        s.set_clock(20)
        s.ingest([plan["revoke"]], failpoint="after_commit_before_reply")
    elif action == "collector-commit":
        with ClosureJournal(folder/"collector.sqlite", plan["revoke"], EPSILON) as c:
            c.observe(42, plan["receipts"], failpoint="after_commit_before_reply")
    elif action == "recover":
        decisions = []
        for node in range(5):
            s = open_store(folder, policy, node)
            s.set_clock(43)
            snapshot = s.snapshot()
            state = reference.State(floor=snapshot["floor"])
            for row in snapshot["records"]:
                event = row["event"]
                g = event if event["kind"] == "grant" else event["target"]
                (state.grants if event["kind"] == "grant" else state.revokes)[g["id"]] = event
            for g in plan["children"]+[plan["control"]]:
                actual = s.authorize(g["id"], g["subject"], 1, g["service"])
                oracle = reference.state_allow(state, policy, g, node, 43, EPSILON)
                if actual["allow"] != oracle:
                    raise ValueError("recovered SQL/spec mismatch")
                decisions.append({"gateway": node, "target": g["id"], **actual})
            if s.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("gateway integrity")
            s.close()
        with ClosureJournal(folder/"collector.sqlite", plan["revoke"], EPSILON) as c, \
             DurableReference(folder/"reference.sqlite", plan["revoke"], EPSILON) as r:
            actual, baseline = c.observe(41, []), r.observe(41, [])
            if actual != baseline:
                raise ValueError("same-information collector mismatch")
            print(json.dumps({"status": actual, "decisions": decisions,
                              "integrity_checks": 7 if all(x.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok" for x in (c,r)) else 0}))


def case(root, cohort, policy):
    folder = root/f"{cohort}-{policy}"
    folder.mkdir()
    root_grant = grant(0, 1, None, 3, [1000]*5, "integrated-root")
    target = grant(1, 2, root_grant, 1, [1000,1000,1000,40,40], "integrated-target")
    control = grant(0, 4, None, 1, [1000]*5, "integrated-control")
    children = [grant(2, 3, target, 1, target["deadlines"], "withheld-child")]
    children.append(grant(3, 4, children[0], 1, target["deadlines"], "withheld-grandchild"))
    offered = [root_grant, target, control]+[grant(0, 1, None, 1, [38]*5, f"pressure-{i}") for i in range(9)]
    event = revoke(target)
    stores = [open_store(folder, policy, i) for i in range(5)]
    admitted, refusals = [], []
    for node, s in enumerate(stores):
        s.set_clock(10)
        n = 0
        for g in offered[:5] if cohort == "common" else offered:
            try:
                s.ingest([g]); n += 1
            except CapacityError as exc:
                refusals.append({"node": node, "target": g["id"], "reason": str(exc)})
        admitted.append(n)
    plan = {"cohort": cohort, "policy": policy, "budget": BUDGET, "unseen": UNSEEN,
            "epsilon": EPSILON, "offered": offered[:5] if cohort == "common" else offered,
            "target": target, "revoke": event, "children": children, "control": control, "receipts": []}
    (folder/"inputs.json").write_text(json.dumps(plan, indent=2)+"\n", encoding="utf-8")
    physical = {"after_grants": [s.physical() for s in stores]}
    process = []
    receipts = []
    revoke_refusals = []
    started = time.perf_counter()
    for node in range(3):
        s = stores[node]
        s.set_clock(20)
        # A capacity refusal has no postcommit point and must not produce a receipt.
        if node == 1 and not (cohort == "saturated" and policy == "append"):
            s.close()
            process.append(invoke(folder, "gateway-commit", policy, 70))
            s = stores[node] = open_store(folder, policy, node)
            s.set_clock(20)
        try:
            receipts.extend(s.ingest([event])["receipts"])
        except CapacityError as exc:
            revoke_refusals.append({"gateway": node, "reason": str(exc)})
    local_revoke_seconds = time.perf_counter()-started
    if any(not receipt_authenticated(r) for r in receipts):
        raise ValueError("capacity receipts incompatible with collector authentication")
    plan["receipts"] = receipts
    (folder/"inputs.json").write_text(json.dumps(plan, indent=2)+"\n", encoding="utf-8")
    physical["after_revokes"] = [s.physical() for s in stores]
    logical = [s._counts()["records"] for s in stores]
    with ClosureJournal(folder/"collector.sqlite", event, EPSILON) as c, \
         DurableReference(folder/"reference.sqlite", event, EPSILON) as r:
        observations = [{"actual_time":20, "clock":20, "journal":c.observe(20, receipts),
                         "reference":r.observe(20, receipts)}]
        if observations[0]["journal"] != observations[0]["reference"]:
            raise ValueError("initial collector mismatch")
    process.append(invoke(folder, "collector-commit", policy, 70))
    with ClosureJournal(folder/"collector.sqlite", event, EPSILON) as c, \
         DurableReference(folder/"reference.sqlite", event, EPSILON) as r:
        status, baseline = c.status(), r.observe(42, receipts)
        if status != baseline:
            raise ValueError("lost-reply evidence differs")
        observations.append({"actual_time":42, "clock":42, "journal":status, "reference":baseline})
    for s in stores:
        s.set_clock(42)
        s.compact()  # only expired pressure roots leave; target horizon is 1000
        s.ingest(children)  # must succeed, so a missing/capacity-rejected child cannot mask the test
    physical["after_late_children"] = [s.physical() for s in stores]
    for s in stores:
        s.close()
    recovered = invoke(folder, "recover", policy)
    process.append(recovered)
    report = recovered["result"]
    if report["integrity_checks"] != 7:
        raise ValueError("integrity")
    denied = [d for d in report["decisions"] if d["target"] in {g["id"] for g in children}]
    controls = [d for d in report["decisions"] if d["target"] == control["id"]]
    expected_closed = not (cohort == "saturated" and policy == "append")
    if report["status"]["closed"] != expected_closed or any(not d["allow"] for d in controls):
        raise ValueError("completion or unrelated authority")
    if expected_closed and any(d["allow"] for d in denied):
        raise ValueError("postcompletion descendant allowed")
    if not expected_closed and sum(d["allow"] for d in denied) != 6:
        raise ValueError("open control must retain live descendants at three gateways")
    result = {"cohort":cohort, "policy":policy, "admitted_grants_per_gateway":admitted,
              "grant_refusals":len(refusals), "receipts":len(receipts), "revoke_refusals":len(revoke_refusals),
              "logical_records_after_revokes":logical, "closed_at_logical_time":42 if expected_closed else None,
              "closed_after_recovery":report["status"]["closed"], "late_descendant_checks":len(denied),
              "late_descendant_allows":sum(d["allow"] for d in denied), "control_allows":sum(d["allow"] for d in controls),
              "physical":physical, "local_revoke_call_seconds":local_revoke_seconds,
              "timing_boundary":"includes selected subprocess startup/crash/retry, excludes collector; not a policy latency comparison",
              "observations":observations, "grant_refusal_records":refusals,
              "revoke_refusal_records":revoke_refusals, "processes":process}
    (folder/"result.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result


def export_table(summary, path):
    lines = [r"\begin{tabular}{@{}llrrrr@{}}", r"\toprule",
             r"Cohort & Policy & Grants & Acks & Close & Allows\\", r"\midrule"]
    for x in summary["cases"]:
        lines.append(f'{x["cohort"]} & {x["policy"]} & {x["admitted_grants_per_gateway"][0]} & {x["receipts"]} & '+
                     ("42" if x["closed_after_recovery"] else "open")+f' & {x["late_descendant_allows"]}/10'+r"\\")
    path.write_text("\n".join(lines+[r"\bottomrule",r"\end{tabular}"])+"\n", encoding="utf-8")


def verify(folder):
    summary = json.loads((folder/"summary.json").read_text(encoding="utf-8"))
    if summary["case_count"] != 6 or len(summary["cases"]) != 6 or {(x["cohort"],x["policy"]) for x in summary["cases"]} != {
            (c,p) for c in ("common","saturated") for p in ("append","reservation","replacement")}:
        raise ValueError("case denominator")
    for x in summary["cases"]:
        case_folder = folder/f'{x["cohort"]}-{x["policy"]}'
        if json.loads((case_folder/"result.json").read_text(encoding="utf-8")) != x:
            raise ValueError("case/summary mismatch")
        plan = json.loads((case_folder/"inputs.json").read_text(encoding="utf-8"))
        if any(not receipt_authenticated(r) or r["target"] != plan["target"]["id"] or
               r["revocation"] != plan["revoke"]["id"] for r in plan["receipts"]):
            raise ValueError("receipt binding")
        expected = not (x["cohort"] == "saturated" and x["policy"] == "append")
        recovery = x["processes"][-1]
        if recovery["action"] != "recover" or recovery["exit_code"] != 0:
            raise ValueError("recovery process outcome")
        recovered = recovery["result"]
        decisions = recovered["decisions"]
        expected_product = {(i,g["id"]) for i in range(5)
                            for g in plan["children"]+[plan["control"]]}
        if (len(decisions) != 15 or len(expected_product) != 15 or
                {(d["gateway"],d["target"]) for d in decisions} != expected_product):
            raise ValueError("recovery decision product")
        if any(type(d["allow"]) is not bool or type(d["gateway"]) is not int for d in decisions):
            raise ValueError("recovery decision types")
        child_ids = {g["id"] for g in plan["children"]}
        descendants = [d for d in decisions if d["target"] in child_ids]
        controls = [d for d in decisions if d["target"] == plan["control"]["id"]]
        counts = {"late_descendant_checks":len(descendants),
                  "late_descendant_allows":sum(d["allow"] for d in descendants),
                  "control_allows":sum(d["allow"] for d in controls)}
        if any(x[k] != value for k,value in counts.items()):
            raise ValueError("recovery decision/counter mismatch")
        # At recovered clock 43, the open append control admits descendants
        # only at the three long-deadline gateways. Closed cases admit none;
        # the independently granted control remains live at all five.
        if any(d["allow"] != (d["target"] == plan["control"]["id"] or
                              (not expected and d["gateway"] < 3)) for d in decisions):
            raise ValueError("recovery authorization outcome")
        if (x["closed_after_recovery"] != expected or recovered["status"]["closed"] != expected
                or x["receipts"] != len(plan["receipts"]) or x["receipts"] != (3 if expected else 0)
                or x["late_descendant_checks"] != 10 or x["late_descendant_allows"] != (0 if expected else 6)
                or x["control_allows"] != 5 or recovered["integrity_checks"] != 7):
            raise ValueError("contract count")
        if any(o["journal"] != o["reference"] for o in x["observations"]):
            raise ValueError("same-information reference")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--worker", choices=("gateway-commit","collector-commit","recover"))
    ap.add_argument("--policy", choices=("append","reservation","replacement"))
    ap.add_argument("--table", type=Path)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    out = owned(a.out)
    if a.verify:
        summary = verify(out)
        if a.table:
            export_table(summary,a.table)
        print("verified six integrated cases, authentic receipt bindings, reference agreement and full recovery product")
    elif a.worker:
        worker(out,a.worker,a.policy)
    else:
        out.mkdir(parents=True, exist_ok=False)
        cases = [case(out, cohort, policy) for cohort in ("common","saturated")
                 for policy in ("append","reservation","replacement")]
        summary = {"case_count":len(cases), "budget":BUDGET,"early_credits":UNSEEN,"epsilon":EPSILON,
                   "cases":cases, "scope":"owned local experiment; not an independent deployment"}
        (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
        if a.table:
            export_table(summary,a.table)
        print(json.dumps({"cases":len(cases),"late_checks":sum(c["late_descendant_checks"] for c in cases),
                          "postclosure_denials":sum(c["late_descendant_checks"] for c in cases if c["closed_after_recovery"]),
                          "process_exits_70":sum(p["exit_code"]==70 for c in cases for p in c["processes"])}))
