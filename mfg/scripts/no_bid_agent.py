#!/usr/bin/env python3
"""I3 No-Bid Agent — metadata-driven RFQ decisions.

Reads the DataHub graph (mfg platform): RFQ fixture -> lineage -> material /
machine_profile. Applies a deterministic decision gate (material family +
risk categories), produces ACCEPT / DECLINE / NEEDS-REVIEW with lineage-backed
reasoning, and writes the decision back to DataHub as an Insight document +
structured properties on the RFQ dataset.

Usage:
  DATAHUB_SERVER=http://127.0.0.1:8080 python3 no_bid_agent.py <rfq_urn_or_id>
  python3 no_bid_agent.py --all        # run over all seeded mfg RFQs
  python3 no_bid_agent.py --dry-run    # decide without write-back
"""
import argparse, json, os, sys
from pathlib import Path

# ---- Decision gate (deterministic, mirrors shop doctrine) -------------------
EXOTIC_MATERIALS = {"inconel", "titanium", "magnesium", "graphite", "stainless"}
REVIEW_RISKS = {"missing_info", "thin_wall", "tight_tolerance", "deep_pocket",
                "multi_depth_pocket", "two_sided_setup", "material_difficulty",
                "impeller_geometry", "slot_aspect_ratio"}
NO_BID_RISKS = {"exotic_material", "material_risk", "tooling_cost"}

def decide(fixture: dict) -> dict:
    """Return {decision, confidence, reasons, risk_categories, review_gates}."""
    mat = (fixture.get("material") or "").lower()
    risks = fixture.get("expected_dfm_risks", []) or []
    risk_cats = [r.get("category", "") for r in risks]
    missing = fixture.get("missing_info", []) or []
    reasons = []
    review_gates = []

    # 1. Exotic / no-bid material gate
    if any(m in mat for m in ("inconel", "titanium", "magnesium", "graphite")):
        return {
            "decision": "no_bid",
            "confidence": "HIGH",
            "reason": f"Exotic material {fixture.get('material')}: out of scope "
                      f"for current capability (material risk, tooling cost).",
            "risk_categories": ["exotic_material", "material_risk", "tooling_cost"],
            "review_gates": ["speeds_feeds_engineering", "tooling_review",
                             "customer_communication", "machinist_review"],
            "missing_info": missing,
        }
    if "stainless" in mat:
        return {
            "decision": "needs_review",
            "confidence": "MEDIUM",
            "reason": f"Stainless {fixture.get('material')}: machinable but slow; "
                      f"requires speeds/feeds engineering review before quoting.",
            "risk_categories": ["material_machinability"],
            "review_gates": ["speeds_feeds_engineering"],
            "missing_info": missing,
        }

    # 2. Missing info -> needs_review
    if missing:
        return {
            "decision": "needs_review",
            "confidence": "HIGH",
            "reason": f"Missing information: {'; '.join(missing)}. Cannot quote "
                      f"without complete specs.",
            "risk_categories": ["missing_info"],
            "review_gates": ["customer_communication", "setup_review"],
            "missing_info": missing,
        }

    # 3. Risk categories -> needs_review (geometry / tolerance concerns)
    if risks:
        severities = [r.get("severity", "LOW") for r in risks]
        cats = ", ".join(risk_cats)
        if "HIGH" in severities or "MEDIUM" in severities:
            return {
                "decision": "needs_review",
                "confidence": "MEDIUM",
                "reason": f"DFM risks require review: {cats}. "
                          f"Engineering sign-off before quote.",
                "risk_categories": risk_cats,
                "review_gates": ["setup_review", "tooling_review", "machinist_review"],
                "missing_info": missing,
            }

    # 4. Default: quote_ready (machinable material, no missing info, no risks)
    return {
        "decision": "quote_ready",
        "confidence": "HIGH",
        "reason": f"{fixture.get('material')} is a known machinable family; "
                  f"no missing info or blocking DFM risks. Ready to quote.",
        "risk_categories": [],
        "review_gates": [],
        "missing_info": missing,
    }


# ---- DataHub read/write ------------------------------------------------------
def get_graph():
    from datahub.sdk.main_client import DataHubClient
    from datahub_agent_context.context import DataHubContext
    server = os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080")
    client = DataHubClient(server=server, token="")
    return client, DataHubContext(client)


def load_fixture(urn: str, client=None, ctx=None) -> dict:
    """Load fixture data from the live DataHub graph (Dataset.custom_properties),
    falling back to local vendored JSON if the graph is unreachable."""
    ROOT = Path(__file__).resolve().parent.parent.parent
    name = urn.split("rfq.")[-1].rstrip(",PROD)")

    # 1) Graph-first: read customProperties from the live entity
    if client is not None:
        try:
            ent = client.entities.get(urn)
            props = dict(getattr(ent, "custom_properties", {}) or {})
            if props.get("material"):
                fx = {
                    "fixture_id": name,
                    "material": props.get("material", ""),
                    "quantity": props.get("quantity"),
                    "finish": props.get("finish", ""),
                    "tolerance": props.get("tolerance", ""),
                }
                # missing_info / dfm_risks are JSON strings in the graph
                if props.get("missing_info"):
                    try: fx["missing_info"] = json.loads(props["missing_info"])
                    except Exception: fx["missing_info"] = [props["missing_info"]]
                else:
                    fx["missing_info"] = []
                if props.get("dfm_risks"):
                    try: fx["expected_dfm_risks"] = json.loads(props["dfm_risks"])
                    except Exception: fx["expected_dfm_risks"] = []
                else:
                    fx["expected_dfm_risks"] = []
                # capability class (flattened capability_* keys)
                cc = {}
                for k, v in props.items():
                    if k.startswith("capability_"):
                        key = k[len("capability_"):]
                        if isinstance(v, str) and v.startswith("["):
                            try: v = json.loads(v)
                            except Exception: pass
                        cc[key] = v
                if cc:
                    fx["capability_class"] = cc
                # keep expected_* fields for parity with local fixtures
                for k in ("expected_quote_decision", "expected_setup_count", "expected_setup_class", "dfm_risk_count"):
                    if props.get(k) is not None:
                        v = props[k]
                        if isinstance(v, str) and v.startswith("["):
                            try: v = json.loads(v)
                            except Exception: pass
                        fx[k] = v
                return fx
        except Exception as e:
            print(f"  (graph read failed for {name}: {e.__class__.__name__}: {e}; falling back to local)")

    # 2) Local fallback
    for d in ("rfq", "kernels"):
        p = ROOT / "mfg" / "fixtures" / d / f"{name}.json"
        if p.exists():
            return json.loads(p.read_text())
    raise FileNotFoundError(f"No fixture for {name}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="RFQ id (fixture-XXX) or urn")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ROOT = Path(__file__).resolve().parent.parent.parent

    targets = []
    if args.all:
        for d in ("rfq", "kernels"):
            for f in sorted((ROOT / "mfg" / "fixtures" / d).glob("*.json")):
                if f.stem.startswith(("fixture-", "kernel-")):
                    targets.append(f.stem)
    elif args.target:
        t = args.target.replace("urn:li:dataset:(urn:li:dataPlatform:mfg,rfq.", "").rstrip(",PROD)")
        targets = [t]
    else:
        ap.error("need target or --all")

    client = None
    if not args.dry_run:
        client, _ctx = get_graph()  # graph-first reads need the client

    results = []
    for tid in targets:
        urn = f"urn:li:dataset:(urn:li:dataPlatform:mfg,rfq.{tid},PROD)"
        try:
            fixture = load_fixture(urn, client=client)
        except FileNotFoundError:
            print(f"SKIP {tid}: no fixture")
            continue
        dec = decide(fixture)
        results.append({"urn": urn, "fixture": tid, **dec})
        print(f"{tid:42s} -> {dec['decision']:12s} [{dec['confidence']}] {dec['reason'][:70]}")

    if not args.dry_run and client is None:
        client, _ctx = get_graph()

    if not args.dry_run:
        print("\n-- write-back --")
        client, ctx = get_graph()
        with ctx:
            from datahub.sdk import DataHubClient, Document
            from datahub_agent_context.mcp_tools import update_description
            for res in results:
                urn = res["urn"]
                # Native upsert: deterministic id -> idempotent, one canonical doc per fixture
                doc = Document.create_document(
                    id=f"decision-{res['fixture']}",
                    title=f"[no-bid] {res['fixture']}: {res['decision']}",
                    text=(
                        f"## {res['fixture']}\n\n"
                        f"**Decision:** {res['decision']}\n"
                        f"**Confidence:** {res['confidence']}\n\n"
                        f"**Reasoning:** {res['reason']}\n"
                        f"**Risk categories:** {', '.join(res['risk_categories']) or 'none'}\n"
                        f"**Review gates:** {', '.join(res['review_gates']) or 'none'}\n"
                        f"**Missing info:** {'; '.join(res['missing_info']) or 'none'}"
                    ),
                    subtype="Decision",
                    related_assets=[urn],
                    show_in_global_context=True,
                )
                client.entities.upsert(doc)
                print(f"  upserted Decision doc {doc.urn} -> {urn} ({res['decision']})")
    print("\nDONE")

if __name__ == "__main__":
    main()
