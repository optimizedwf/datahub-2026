#!/usr/bin/env python3
"""B3 eval runner: mfg RFQ decision eval + SQL benchmark regression gate.

1. Runs the deterministic decision gate over all frozen RFQ cases (EVAL_MFG.json)
   and reports accuracy vs ground truth.
2. Optional: re-runs the SQL benchmark (EVAL.json) to guard against regression.

Usage:
  python3 eval_mfg.py                 # decision accuracy only
  python3 eval_mfg.py --sql           # + SQL benchmark regression check
  python3 eval_mfg.py --write-back    # + write Decision docs (idempotent)
"""
import argparse, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "mfg" / "scripts"))
from no_bid_agent import decide

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql", action="store_true")
    ap.add_argument("--write-back", action="store_true")
    args = ap.parse_args()

    eval_path = ROOT / "mfg" / "EVAL_MFG.json"
    data = json.loads(eval_path.read_text())
    cases = data["cases"]
    print(f"MFG EVAL: {len(cases)} cases ({data['frozen']})")

    # Load fixtures + decide
    results = []
    n_ok = 0
    for c in cases:
        d = "rfq" if (ROOT / "mfg" / "fixtures" / "rfq" / f"{c['id']}.json").exists() else "kernels"
        fp = ROOT / "mfg" / "fixtures" / d / f"{c['id']}.json"
        fx = json.loads(fp.read_text())
        pred = decide(fx)["decision"]
        ok = pred == c["expected_decision"]
        n_ok += ok
        results.append({**c, "predicted": pred, "ok": ok})
        flag = "OK " if ok else "FAIL"
        print(f"  [{flag}] {c['id']:40s} gt={c['expected_decision']:12s} pred={pred:12s}")

    acc = n_ok / len(cases)
    print(f"\nDecision accuracy: {n_ok}/{len(cases)} = {acc:.2%}")
    gate_pass = acc == 1.0
    print(f"GATE: {'PASS' if gate_pass else 'FAIL'} (require 100%)")
    if not gate_pass:
        sys.exit(1)

    if args.sql:
        # SQL benchmark regression check (reuse existing eval.sh)
        import subprocess as sp
        print("\nSQL benchmark regression check...")
        r = sp.run(["bash", str(ROOT / "examples" / "eval.sh")], capture_output=True, text=True, cwd=ROOT)
        print(r.stdout[-1200:])
        # parse headline from output/EVAL.json
        ev = json.loads((ROOT / "EVAL.json").read_text())
        h = ev.get("headline", {})
        print(f"SQL headline: metadata={h.get('metadata')} plain={h.get('plain')} delta={h.get('paired_delta')}")
        if h.get("metadata", 0) < 0.95:
            print("GATE FAIL: metadata score regressed below 0.95")
            sys.exit(1)
        print("GATE PASS: no SQL regression")

    if args.write_back:
        print("\nWrite-back Decision docs...")
        from datahub.sdk.main_client import DataHubClient
        from datahub_agent_context.context import DataHubContext
        from datahub_agent_context.mcp_tools import save_document
        client = DataHubClient(server=os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080"), token="")
        with DataHubContext(client):
            for res in results:
                urn = f"urn:li:dataset:(urn:li:dataPlatform:mfg,rfq.{res['id']},PROD)"
                content = (f"## {res['id']}\n\n**Decision:** {res['predicted']}\n"
                           f"**Ground truth:** {res['expected_decision']}\n"
                           f"**Match:** {'yes' if res['ok'] else 'no'}")
                save_document(document_type="Decision",
                              title=f"[eval] {res['id']}: {res['predicted']}",
                              content=content, related_assets=[urn])
        print("write-back done")

if __name__ == "__main__":
    main()
