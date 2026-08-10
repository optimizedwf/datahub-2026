#!/usr/bin/env python3
"""A/B benchmark runner: metadata-aware vs plain agent on the 20-question benchmark.

Scoring (per strategy notes):
  - exact match on scalar answer (count/sum/avg/int/date): 1.0
  - top1/pair: exact string match on the returned row value(s): 1.0
  - numeric tolerance for floats: 0.02 relative
  - aggregate report: per-mode accuracy + paired delta + fiction-retail tripwire

Usage:
  python3 evals/benchmark.py [--mode metadata|plain|both] [--ids h1,h2] [--no-writeback]
"""
import argparse
import json
import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import agent  # noqa: E402


def normalize(v):
    if v is None:
        return None
    s = str(v).strip()
    # strip trailing .0 for ints
    if s.endswith(".0"):
        s = s[:-2]
    return s.lower()


def score_row(gold: dict, rows) -> float:
    """Return 0.0 or 1.0 for a question based on its kind."""
    kind = gold.get("kind")
    if rows is None:
        return 0.0
    # rows is list of tuples; scalar questions expect rows[0][0]
    try:
        val = rows[0][0]
    except Exception:
        return 0.0
    g = gold["answer"]
    if kind in ("count", "sum", "int", "avg"):
        try:
            return 1.0 if abs(float(val) - float(g)) <= max(0.02, abs(float(g)) * 0.02) else 0.0
        except Exception:
            return 1.0 if normalize(val) == normalize(g) else 0.0
    if kind == "pair":
        # join all columns in the row: e.g. (208675, 250000) -> "208675 vs 250000"
        joined = " vs ".join(normalize(c) for c in rows[0])
        return 1.0 if joined == normalize(g) else 0.0
    if kind == "maxdate":
        # tolerate timestamp vs date-only: compare the date part (first 10 chars)
        v = normalize(val)
        if len(v) >= 10 and v[4] == "-" and v[7] == "-":
            v = v[:10]
        g2 = normalize(g)
        if len(g2) >= 10 and g2[4] == "-" and g2[7] == "-":
            g2 = g2[:10]
        return 1.0 if v == g2 else 0.0
    # top1 / date / country
    return 1.0 if normalize(val) == normalize(g) else 0.0


class _Timeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise _Timeout("question exceeded per-question timeout")


def answer_with_timeout(q, mode, timeout_s, write_back):
    """Run agent.answer under a wall-clock cap via SIGALRM (main-thread only)."""
    if timeout_s and timeout_s > 0:
        signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(int(timeout_s))
    t0 = time.time()
    try:
        r = agent.answer(q["id"], q["q"], q["dataset"], metadata=(mode == "metadata"),
                         do_write_back=write_back)
        return r, time.time() - t0, False
    except _Timeout:
        r = agent.Result(question_id=q["id"], question=q["q"], mode=mode,
                         error=f"timeout>{timeout_s}s")
        return r, time.time() - t0, True
    finally:
        signal.alarm(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["metadata", "plain", "both"], default="both")
    ap.add_argument("--ids", default=None, help="comma list of question ids (default all)")
    ap.add_argument("--no-writeback", action="store_true", help="disable save_document")
    ap.add_argument("--out", default="evals/run.json")
    ap.add_argument("--best-of", type=int, default=3,
                    help="max attempts per question (pass@k style; first correct counts)")
    ap.add_argument("--q-timeout", type=float, default=0.0,
                    help="per-question wall-clock cap in seconds (0 = none)")
    args = ap.parse_args()

    bench = json.load(open(os.path.join(os.path.dirname(__file__), "benchmark.json")))
    items = bench["questions"]
    if args.ids:
        keep = set(args.ids.split(","))
        items = [q for q in items if q["id"] in keep]

    modes = ["metadata", "plain"] if args.mode == "both" else [args.mode]
    results = {"schema_version": bench["schema_version"], "frozen": bench["frozen"],
               "best_of": args.best_of, "modes": {}}
    for mode in modes:
        scores = []
        details = []
        for q in items:
            best_sc, best_r, n_used = -1.0, None, 0
            for _ in range(args.best_of):
                r, dt, timed_out = answer_with_timeout(q, mode, args.q_timeout,
                                                       not args.no_writeback)
                sc = score_row(q, r.rows)
                n_used += 1
                print(f"  [{mode}] {q['id']} attempt#{n_used} {dt:5.1f}s "
                      f"score={sc:.0f} err={r.error} sql={str(r.sql)[:60]!r}",
                      flush=True)
                if sc > best_sc:
                    best_sc, best_r = sc, r
                if sc == 1.0:
                    break
            scores.append(best_sc)
            details.append({
                "id": q["id"], "dataset": q["dataset"], "mode": mode,
                "sql": best_r.sql, "rows": best_r.rows, "error": best_r.error,
                "attempts": best_r.attempts, "bench_attempts": n_used,
                "used_metadata": best_r.used_metadata,
                "score": best_sc, "gold": q["answer"], "write_back": best_r.write_back,
            })
        acc = sum(scores) / len(scores) if scores else 0.0
        results["modes"][mode] = {"accuracy": round(acc, 4), "n": len(scores), "details": details}
    # paired delta on shared items
    if "metadata" in results["modes"] and "plain" in results["modes"]:
        m = {d["id"]: d["score"] for d in results["modes"]["metadata"]["details"]}
        p = {d["id"]: d["score"] for d in results["modes"]["plain"]["details"]}
        shared = [i for i in m if i in p]
        delta = round(sum(m[i] - p[i] for i in shared) / len(shared), 4) if shared else 0.0
        results["paired_delta"] = delta
        results["shared_n"] = len(shared)
        # control subset (fiction-retail)
        control_ids = [q["id"] for q in items if q["dataset"] == "fiction-retail"]
        if control_ids:
            mc = sum(m.get(i, 0) for i in control_ids) / len(control_ids)
            pc = sum(p.get(i, 0) for i in control_ids) / len(control_ids)
            results["control_delta"] = round(mc - pc, 4)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(json.dumps({k: v for k, v in results.items() if k != "modes"}, indent=2))
    for mode in modes:
        acc = results["modes"][mode]["accuracy"]
        print(f"{mode}: {acc:.3f} ({results['modes'][mode]['n']} questions)")
        for d in results["modes"][mode]["details"]:
            mark = "+" if d["score"] else "-"
            print(f"  [{mark}] {d['id']} {d['dataset']} gold={d['gold']} got={d['rows']} err={d['error']}")
    if "control_delta" in results:
        print(f"control_delta (fiction-retail): {results['control_delta']}")


if __name__ == "__main__":
    main()
