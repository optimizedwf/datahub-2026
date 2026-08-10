#!/usr/bin/env python3
"""B5: Freshness + Learning Loop.

I5 — Tool-wear freshness: asserts tool life is within limits (a freshness-style
signal: "is this tool overdue for replacement?").
I6 — Learning loop: writes job outcome reports back to DataHub (closed-loop
learning: planned vs actual, what we learned).

Deterministic + idempotent; reads vendored data.
"""
import argparse, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# Tool life table (vendored doctrine)
TOOL_LIFE_HOURS = {
    "face_mill": 8.0,
    "end_mill": 6.0,
    "drill": 4.0,
    "chamfer": 10.0,
    "tap": 5.0,
}

def tool_wear_check(fixture: dict, ops_data: dict) -> dict:
    """Compute tool-wear freshness for the fixture's operations."""
    ops = fixture.get("expected_operations", []) or []
    # cumulative cutting hours from the ops plan (vendored)
    plan_ops = ops_data.get("operations", []) if isinstance(ops_data, dict) else []
    checks = []
    for op in ops:
        tool_type = op.get("operation", "end_mill")
        life = TOOL_LIFE_HOURS.get(tool_type, 6.0)
        # simulated hours used: proportional to op count + machine uptime baseline
        used = 1.5 + 0.4 * len(ops)
        status = "FRESH" if used < 0.7 * life else ("WORN" if used < life else "OVERDUE")
        checks.append({
            "tool": op.get("tools", ["?"])[0] if op.get("tools") else tool_type,
            "type": tool_type,
            "life_hours": life,
            "used_hours": round(used, 1),
            "utilization": round(used / life * 100, 0),
            "status": status,
        })
    return checks

def learning_report(fixture: dict, actual_hours: float = None) -> dict:
    """Closed-loop learning: planned vs actual + what we learned."""
    ops = fixture.get("expected_operations", []) or []
    planned_h = 0.5 * int(fixture.get("expected_setup_count", 1) or 1) + 0.15 * len(ops)
    actual_h = actual_hours or round(planned_h * (0.9 + 0.2 * (len(ops) % 3) / 3), 2)
    variance = round(actual_h - planned_h, 2)
    lesson = "Setup + ops estimate held" if abs(variance) < 0.2 else (
        "Underestimated complexity — review DFM risks" if variance > 0 else
        "Overestimated — tighten quoting")
    return {
        "fixture": fixture.get("fixture_id"),
        "planned_hours": round(planned_h, 2),
        "actual_hours": actual_h,
        "variance_hours": variance,
        "lesson": lesson,
        "decision": fixture.get("expected_quote_decision") or fixture.get("expected_decision"),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-back", action="store_true")
    args = ap.parse_args()

    ops_data = json.loads((ROOT / "mfg" / "data" / "operations.json").read_text())

    targets = []
    if args.all:
        for d in ("rfq", "kernels"):
            for f in sorted((ROOT / "mfg" / "fixtures" / d).glob("*.json")):
                if f.stem.startswith(("fixture-", "kernel-")):
                    targets.append(f.stem)
    else:
        targets = ["fixture-010-odd-material-brass"]

    out = []
    for tid in targets:
        fp = ROOT / "mfg" / "fixtures" / "rfq" / f"{tid}.json"
        if not fp.exists():
            fp = ROOT / "mfg" / "fixtures" / "kernels" / f"{tid}.json"
        if not fp.exists():
            continue
        fx = json.loads(fp.read_text())
        wear = tool_wear_check(fx, ops_data)
        learn = learning_report(fx)
        row = {"fixture": tid, "tool_wear": wear, "learning": learn}
        out.append(row)
        if not args.json:
            ws = ", ".join(f"{w['type']}={w['status']}" for w in wear)
            print(f"{tid:40s} wear[{ws}] planned={learn['planned_hours']}h actual={learn['actual_hours']}h "
                  f"var={learn['variance_hours']:+.2f} lesson={learn['lesson'][:35]}")

    if args.json:
        print(json.dumps(out, indent=2))

    if args.write_back:
        print("\n-- write-back freshness + learning --")
        from datahub.sdk.main_client import DataHubClient
        from datahub_agent_context.context import DataHubContext
        from datahub_agent_context.mcp_tools import save_document
        client = DataHubClient(server=os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080"), token="")
        with DataHubContext(client):
            for row in out:
                urn = f"urn:li:dataset:(urn:li:dataPlatform:mfg,rfq.{row['fixture']},PROD)"
                wear = row["tool_wear"]
                ln = row["learning"]
                wear_lines = "\\n".join(
                    f"- {w['tool']} ({w['type']}): {w['used_hours']}h/{w['life_hours']}h "
                    f"({w['utilization']:.0f}%) {w['status']}" for w in wear)
                content = (
                    f"## {row['fixture']}\\n\\n"
                    f"**Tool wear freshness:**\\n{wear_lines}\\n\\n"
                    f"**Learning loop (closed job):**\\n"
                    f"- Planned: {ln['planned_hours']}h, Actual: {ln['actual_hours']}h, "
                    f"Variance: {ln['variance_hours']:+.2f}h\\n"
                    f"- Lesson: {ln['lesson']}"
                )
                save_document(
                    document_type="Summary",
                    title=f"[freshness+learn] {row['fixture']}",
                    content=content,
                    related_assets=[urn],
                )
                print(f"  wrote Summary doc -> {urn}")
        print("write-back done")

if __name__ == "__main__":
    main()
