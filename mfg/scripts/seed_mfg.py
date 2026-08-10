#!/usr/bin/env python3
"""Seed the DataHub graph with manufacturing (mfg) entities + lineage.

B1 / Shop Graph substrate: creates datasets for RFQ fixtures, materials,
machine profiles, operation plans; wires lineage. Native datahub emitter,
idempotent upsert (re-runnable).

Usage:
  DATAHUB_GMS_HOST=127.0.0.1 DATAHUB_GMS_PORT=8080 python3 seed_mfg.py
"""
import argparse, json, os, sys
from pathlib import Path

from datahub.emitter.mce_builder import make_dataset_urn
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    DatasetSnapshotClass, MetadataChangeEventClass,
    DatasetPropertiesClass, StatusClass, UpstreamLineageClass,
    UpstreamClass, DatasetLineageTypeClass,
)

GMS = os.environ.get("DATAHUB_GMS_HOST", "127.0.0.1")
PORT = int(os.environ.get("DATAHUB_GMS_PORT", "8080"))
ROOT = Path(__file__).resolve().parent.parent.parent

def urn(platform: str, name: str) -> str:
    return make_dataset_urn(platform, name, "PROD")

def mfg_urn(name: str) -> str:
    return urn("mfg", name)

def dataset_mce(ds_urn: str, name: str, desc: str, custom: dict = None,
                upstreams: list = None) -> MetadataChangeEventClass:
    aspects = [
        DatasetPropertiesClass(
            name=name, description=desc,
            customProperties=custom or {},
        ),
        StatusClass(removed=False),
    ]
    if upstreams:
        aspects.append(UpstreamLineageClass(
            upstreams=[
                UpstreamClass(dataset=u, type=DatasetLineageTypeClass.TRANSFORMED)
                for u in upstreams
            ]
        ))
    return MetadataChangeEventClass(
        proposedSnapshot=DatasetSnapshotClass(urn=ds_urn, aspects=aspects)
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    emitter = DatahubRestEmitter(gms_server=f"http://{GMS}:{PORT}")
    print(f"GMS {GMS}:{PORT} connected")

    # ---- Materials ---------------------------------------------------------
    mat_dir = ROOT / "mfg" / "materials"
    materials = {}  # family stem -> urn
    for f in sorted(mat_dir.glob("*.yaml")):
        u = mfg_urn(f"material.{f.stem}")
        materials[f.stem] = u
        if not args.dry_run:
            emitter.emit_mce(dataset_mce(
                u, f.stem, f"Material profile: {f.stem}",
                {"source": "materials/" + f.name, "family": f.stem},
            ))
        print("MATERIAL", u)

    # ---- Machine profiles --------------------------------------------------
    mp_dir = ROOT / "mfg" / "machine_profiles"
    machines = {}
    for f in sorted(mp_dir.glob("*.yaml")):
        u = mfg_urn(f"machine_profile.{f.stem}")
        machines[f.stem] = u
        if not args.dry_run:
            emitter.emit_mce(dataset_mce(
                u, f.stem, f"Machine profile: {f.stem}",
                {"source": "machine_profiles/" + f.name},
            ))
        print("MACHINE", u)

    # ---- Operation plans ---------------------------------------------------
    ops_path = ROOT / "mfg" / "data" / "operations.json"
    if ops_path.exists():
        ops = json.loads(ops_path.read_text())
        u = mfg_urn("operation_plan.master")
        if not args.dry_run:
            emitter.emit_mce(dataset_mce(
                u, "operations.json", "Master operation plans with cutting params",
                {"source": "data/operations.json", "count": str(len(ops) if isinstance(ops, list) else 0)},
            ))
        print("OPERATIONS", u)
    else:
        print("WARN no operations.json")

    # ---- RFQ fixtures ------------------------------------------------------
    rfq_dir = ROOT / "mfg" / "fixtures" / "rfq"
    for f in sorted(rfq_dir.glob("fixture-*.json")):
        data = json.loads(f.read_text())
        fid = data.get("fixture_id", f.stem)
        u = mfg_urn(f"rfq.{fid}")
        custom = {
            "material": str(data.get("material", "")),
            "quantity": str(data.get("quantity", "")),
            "tolerance": str(data.get("tolerance", "")),
            "finish": str(data.get("finish", "")),
            "expected_quote_decision": str(data.get("expected_quote_decision", "")),
            "expected_setup_count": str(data.get("expected_setup_count", "")),
            "source": "fixtures/rfq/" + f.name,
        }
        cc = data.get("capability_class", {})
        for k, v in cc.items():
            custom["capability_" + k] = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
        missing = data.get("missing_info", [])
        if missing:
            custom["missing_info"] = json.dumps(missing, ensure_ascii=False)
        risks = data.get("expected_dfm_risks", [])
        if risks:
            custom["dfm_risk_count"] = str(len(risks))
            custom["dfm_risks"] = json.dumps(risks, ensure_ascii=False)

        desc = data.get("description") or data.get("name", f.stem)
        upstreams = []
        mat = data.get("material", "").lower()
        for stem in materials:
            if stem in mat or mat.split()[0] in stem:
                upstreams.append(materials[stem])
                break
        # link to default machine profile
        if "default_3axis" in machines:
            upstreams.append(machines["default_3axis"])
        if not args.dry_run:
            emitter.emit_mce(dataset_mce(u, fid, desc, custom, upstreams))
        print("RFQ", u, "<-", [x for x in upstreams])

    # ---- Kernels (decision fixtures) ---------------------------------------
    kern_dir = ROOT / "mfg" / "fixtures" / "kernels"
    for f in sorted(kern_dir.glob("kernel-*.json")):
        data = json.loads(f.read_text())
        fid = data.get("fixture_id", f.stem)
        u = mfg_urn(f"rfq.{fid}")
        custom = {
            "material": str(data.get("material", "")),
            "quantity": str(data.get("quantity", "")),
            "tolerance": str(data.get("tolerance", "")),
            "expected_decision": str(data.get("expected_decision", "")),
            "expected_scope_status": str(data.get("expected_scope_status", "")),
            "expected_confidence_band": str(data.get("expected_confidence_band", "")),
            "source": "fixtures/kernels/" + f.name,
        }
        rc = data.get("expected_risk_categories", [])
        if rc: custom["risk_categories"] = json.dumps(rc, ensure_ascii=False)
        rg = data.get("expected_review_gates", [])
        if rg: custom["review_gates"] = json.dumps(rg, ensure_ascii=False)
        mi = data.get("missing_info", [])
        if mi: custom["missing_info"] = json.dumps(mi, ensure_ascii=False)
        s = data.get("safety", {})
        for k, v in s.items(): custom["safety_" + k] = str(v)
        if not args.dry_run:
            emitter.emit_mce(dataset_mce(u, fid, data.get("description", fid), custom))
        print("KERNEL", u)

    print("DONE")

if __name__ == "__main__":
    main()
