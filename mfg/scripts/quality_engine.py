#!/usr/bin/env python3
"""B4: Manufacturing quality layer — assertions, quoting, safety gates.

Adds DataHub-native quality concepts on top of the mfg graph:
  1. Manufacturability assertions (score >= threshold) on DFM packets
  2. QuoteDesk: graph-walk quote generation (material + machine + operations)
  3. Digital-twin safety workflow: envelope/authorization gates before machining

Everything deterministic + idempotent; reads vendored data (never the source repo).
"""
import argparse, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# --------------------------------------------------------------------------
# 1. Manufacturability scoring (mirrors manufacturing-intelligence.json)
# --------------------------------------------------------------------------
def manufacturability_score(fixture: dict) -> dict:
    """Score a fixture 0-100 on manufacturability (DFM review)."""
    score = 100
    notes = []
    risks = fixture.get("expected_dfm_risks", []) or []
    sev_weight = {"LOW": 2, "MEDIUM": 6, "HIGH": 15}
    for r in risks:
        sev = r.get("severity", "LOW")
        score -= sev_weight.get(sev, 2)
        notes.append(f"{sev} {r.get('category','?')}: {r.get('message','')[:60]}")
    missing = fixture.get("missing_info", [])
    score -= 5 * len(missing)
    if missing:
        notes.append(f"{len(missing)} missing info items")
    # exotic materials are a hard fail
    mat = (fixture.get("material") or "").lower()
    if any(m in mat for m in ("inconel", "titanium", "magnesium")):
        score = min(score, 30)
        notes.append("exotic material — out of scope")
    score = max(0, min(100, score))
    return {"score": score, "notes": notes}

# --------------------------------------------------------------------------
# 2. Quote generator (graph walk: material + machine + operations)
# --------------------------------------------------------------------------
def generate_quote(fixture: dict, machine: dict, material: dict) -> dict:
    """Deterministic quote: setup hours + op hours + material cost + margin."""
    ops = fixture.get("expected_operations", []) or []
    setup_count = int(fixture.get("expected_setup_count", 1) or 1)
    qty = int(fixture.get("quantity", 1) or 1)
    # hours: 0.5h setup per setup + 0.15h per operation (per piece)
    setup_h = 0.5 * setup_count
    op_h = 0.15 * len(ops)
    per_piece_h = setup_h + op_h
    total_h = per_piece_h * qty
    # material cost: use specific cutting energy / density proxies
    mat_cost_per_kg = material.get("cost_per_kg", 20) if isinstance(material, dict) else 20
    est_kg = 0.5 + 0.1 * qty  # rough stock weight proxy
    material_cost = mat_cost_per_kg * est_kg
    # shop rate
    rate = machine.get("shop_rate_per_hour", 95) if isinstance(machine, dict) else 95
    labor_cost = total_h * rate
    tooling = 50 + 25 * len(ops)  # tooling amortization
    total_cost = material_cost + labor_cost + tooling
    margin = 0.35
    quote = total_cost * (1 + margin)
    return {
        "quantity": qty,
        "setup_hours": round(setup_h, 2),
        "operation_hours": round(op_h, 2),
        "total_hours": round(total_h, 2),
        "material_cost": round(material_cost, 2),
        "labor_cost": round(labor_cost, 2),
        "tooling_cost": round(tooling, 2),
        "total_cost": round(total_cost, 2),
        "margin_pct": margin,
        "quote_amount": round(quote, 2),
    }

# --------------------------------------------------------------------------
# 3. Digital-twin safety workflow (envelope + authorization gates)
# --------------------------------------------------------------------------
def safety_gate(fixture: dict, machine: dict) -> dict:
    """Check digital-twin envelope fit + authorization before machining."""
    # envelope from machine profile (AABB)
    env = machine.get("work_envelope_mm", {}) if isinstance(machine, dict) else {}
    max_x = env.get("x", 762)  # Haas VF-2: 762mm
    max_y = env.get("y", 406)
    max_z = env.get("z", 508)
    # fixture stock dims from operations.json-like data
    stock = fixture.get("stock", {}) or {}
    sx = float(stock.get("length_mm", 120))
    sy = float(stock.get("width_mm", 90))
    sz = float(stock.get("height_mm", 15))
    fits = sx <= max_x and sy <= max_y and sz <= max_z
    auth = bool(fixture.get("safety", {}).get("machine_execution", True))
    return {
        "envelope_fit": "PASS" if fits else "FAIL",
        "stock_mm": [sx, sy, sz],
        "envelope_mm": [max_x, max_y, max_z],
        "machine_execution_authorized": auth,
        "gate": "OPEN" if (fits and auth) else "BLOCKED",
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fixture", nargs="?", default="fixture-010-odd-material-brass")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-back", action="store_true",
                    help="push quality results as Decision docs into DataHub")
    args = ap.parse_args()

    # load vendored data
    mfg_data = json.loads((ROOT / "mfg" / "data" / "manufacturing-intelligence.json").read_text())
    ops_data = json.loads((ROOT / "mfg" / "data" / "operations.json").read_text())
    machine = {
        "name": ops_data.get("machine", {}).get("name", "Haas VF-2"),
        "max_spindle_rpm": ops_data.get("machine", {}).get("max_spindle_rpm", 8100),
        "max_feed_mm_per_min": ops_data.get("machine", {}).get("max_feed_mm_per_min", 12700),
        "shop_rate_per_hour": 95,
        "work_envelope_mm": {"x": 762, "y": 406, "z": 508},
    }
    # material cost table (vendored)
    mat_costs = {"aluminum": 12, "brass": 18, "delrin": 8, "steel": 6, "stainless": 10,
                 "titanium": 60, "inconel": 80, "magnesium": 15, "graphite": 25}

    targets = []
    if args.all:
        for d in ("rfq", "kernels"):
            for f in sorted((ROOT / "mfg" / "fixtures" / d).glob("*.json")):
                if f.stem.startswith(("fixture-", "kernel-")):
                    targets.append(f.stem)
    else:
        targets = [args.fixture]

    out = []
    for tid in targets:
        fp = ROOT / "mfg" / "fixtures" / "rfq" / f"{tid}.json"
        if not fp.exists():
            fp = ROOT / "mfg" / "fixtures" / "kernels" / f"{tid}.json"
        if not fp.exists():
            continue
        fx = json.loads(fp.read_text())
        mat = (fx.get("material") or "unknown").split()[0].lower()
        material = {"name": fx.get("material"), "cost_per_kg": mat_costs.get(mat, 20)}
        ms = manufacturability_score(fx)
        quote = generate_quote(fx, machine, material)
        sg = safety_gate(fx, machine)
        row = {"fixture": tid, "decision": fx.get("expected_quote_decision") or fx.get("expected_decision"),
               "manufacturability": ms, "quote": quote, "safety": sg}
        out.append(row)
        if not args.json:
            print(f"{tid:40s} mfg_score={ms['score']:3d} quote=${quote['quote_amount']:8.2f} "
                  f"gate={sg['gate']} env={sg['envelope_fit']} auth={sg['machine_execution_authorized']}")
    if args.json:
        print(json.dumps(out, indent=2))

    if args.write_back:
        print("\n-- write-back quality docs --")
        from datahub.sdk.main_client import DataHubClient
        from datahub_agent_context.context import DataHubContext
        from datahub_agent_context.mcp_tools import save_document
        client = DataHubClient(server=os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080"), token="")
        with DataHubContext(client):
            for row in out:
                urn = f"urn:li:dataset:(urn:li:dataPlatform:mfg,rfq.{row['fixture']},PROD)"
                ms = row["manufacturability"]
                q = row["quote"]
                sg = row["safety"]
                content = (
                    f"## {row['fixture']}\n\n"
                    f"**Manufacturability score:** {ms['score']}/100\n"
                    f"**Notes:** {'; '.join(ms['notes']) or 'none'}\n\n"
                    f"**Quote:** ${q['quote_amount']:,.2f} (qty {q['quantity']}, "
                    f"{q['total_hours']:.1f}h, margin {q['margin_pct']:.0%})\n"
                    f"**Safety gate:** {sg['gate']} (envelope {sg['envelope_fit']}, "
                    f"authorized {sg['machine_execution_authorized']})\n"
                    f"**Decision:** {row['decision']}"
                )
                save_document(
                    document_type="Analysis",
                    title=f"[quality] {row['fixture']}: score {ms['score']} quote ${q['quote_amount']:,.0f}",
                    content=content,
                    related_assets=[urn],
                )
                print(f"  wrote Analysis doc -> {urn}")

if __name__ == "__main__":
    main()
