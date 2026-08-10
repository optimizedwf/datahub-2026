#!/usr/bin/env python3
"""B6: PartSnap — second domain (automotive parts) on the same DataHub substrate.

Proves generalizability: the RFQ decision mechanics from manufacturing now
serve automotive part lookup. A PartSnap dataset carries OEM part info,
availability, repair difficulty; the agent reads the graph and answers.

Deterministic + idempotent.
"""
import argparse, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# Vendored Subaru part catalog (subset from partsnap/api/parts_lookup.py)
PARTS = [
    {"id": "part-001", "name": "Front Wheel Bearing Hub Assembly", "oem": "28373FG000",
     "category": "drivetrain", "hours": 1.8, "difficulty": "6/10",
     "alternates": ["28373FG010", "28373FG020"], "related": ["knuckle bolt", "axle nut", "dust seal"]},
    {"id": "part-002", "name": "Front Disc Brake Pad Set", "oem": "26296AL020",
     "category": "brakes", "hours": 0.9, "difficulty": "2/10",
     "alternates": ["26296AL021"], "related": ["brake rotor", "caliper bolt"]},
    {"id": "part-003", "name": "Engine Oil Filter", "oem": "15208AA12A",
     "category": "engine", "hours": 0.3, "difficulty": "1/10",
     "alternates": ["15208AA15A"], "related": ["drain plug washer", "oil"]},
    {"id": "part-004", "name": "Drive Belt", "oem": "809222060",
     "category": "engine", "hours": 0.7, "difficulty": "3/10",
     "alternates": ["809222070"], "related": ["belt tensioner", "idler pulley"]},
    {"id": "part-005", "name": "Oxygen Sensor (Front)", "oem": "22641AA180",
     "category": "engine", "hours": 0.6, "difficulty": "4/10",
     "alternates": ["22641AA191"], "related": ["exhaust gasket"]},
    {"id": "part-006", "name": "Front Strut Assembly", "oem": "20310AJ000",
     "category": "suspension", "hours": 2.2, "difficulty": "7/10",
     "alternates": ["20310AJ010"], "related": ["strut mount", "sway bar link"]},
    {"id": "part-007", "name": "Spark Plug (Set of 4)", "oem": "22401AA711",
     "category": "engine", "hours": 1.1, "difficulty": "3/10",
     "alternates": ["22401AA720"], "related": ["ignition coil", "boot"]},
    {"id": "part-008", "name": "Radiator", "oem": "45111AJ010",
     "category": "cooling", "hours": 2.5, "difficulty": "6/10",
     "alternates": ["45111AJ020"], "related": ["coolant", "hose clamp"]},
]

def lookup(query: str) -> dict:
    """Deterministic part lookup against the vendored catalog."""
    q = query.lower()
    # exact / fuzzy match
    for p in PARTS:
        if q in p["name"].lower() or q in p["oem"].lower() or q in p["category"]:
            return {"found": True, "part": p,
                    "recommendation": "replace" if p["difficulty"].split("/")[0] in ("6","7") else "inspect/replace"}
    # fallback: category search
    for p in PARTS:
        if q in p["category"]:
            return {"found": True, "part": p, "recommendation": "inspect/replace"}
    return {"found": False, "part": None, "recommendation": "needs_human_review"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default="wheel bearing")
    ap.add_argument("--seed", action="store_true", help="seed part datasets into DataHub")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.seed:
        print("-- seeding partsnap datasets --")
        from datahub.emitter.mce_builder import make_dataset_urn
        from datahub.emitter.rest_emitter import DatahubRestEmitter
        from datahub.metadata.schema_classes import (
            DatasetSnapshotClass, DatasetPropertiesClass, StatusClass,
        )
        emitter = DatahubRestEmitter(gms_server=os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080"))
        for p in PARTS:
            urn = make_dataset_urn("partsnap", p["id"], "PROD")
            props = {k: str(v) for k, v in p.items() if k not in ("id",)}
            snapshot = DatasetSnapshotClass(
                urn=urn,
                aspects=[
                    DatasetPropertiesClass(name=f"{p['name']} ({p['oem']})",
                                           description=(
                                               f"OEM {p['oem']} | category {p['category']} | "
                                               f"~{p['hours']}h install | difficulty {p['difficulty']} | "
                                               f"alternates {', '.join(p['alternates'])}"
                                           ),
                                           customProperties=props),
                    StatusClass(removed=False),
                ],
            )
            from datahub.metadata.schema_classes import MetadataChangeEventClass
            emitter.emit_mce(MetadataChangeEventClass(proposedSnapshot=snapshot))
            print(f"  seeded {urn}")
        print("seed done")
        return

    res = lookup(args.query)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        p = res.get("part")
        if p:
            print(f"{p['name']} ({p['oem']})")
            print(f"  category={p['category']}  install~{p['hours']}h  difficulty={p['difficulty']}")
            print(f"  recommendation: {res['recommendation']}")
            print(f"  alternates: {', '.join(p['alternates'])}")
        else:
            print("no match — needs_human_review")

if __name__ == "__main__":
    main()
