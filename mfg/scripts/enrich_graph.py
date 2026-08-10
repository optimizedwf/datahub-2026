#!/usr/bin/env python3
"""B8: Graph enrichment — tags, glossary, domain, structured props, owners.

Turns the raw mfg/partsnap datasets into a *rich* DataHub platform:
  - controlled vocabulary: tags (material-family, risk, status), glossary terms
    (Manufacturing / Automotive domain terms), structured properties (score,
    envelope, decision), ownership (shop-ops team)
  - applied across all mfg.* and partsnap.* datasets

Idempotent: entity creation is upsert via emitter; attachment via MCP tools.
"""
import argparse, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# Controlled vocabulary
TAGS = {
    "manufacturing": "urn:li:tag:manufacturing",
    "automotive": "urn:li:tag:automotive",
    "critical": "urn:li:tag:critical",
    "high-risk": "urn:li:tag:high-risk",
    "exotic-material": "urn:li:tag:exotic-material",
    "quote-ready": "urn:li:tag:quote-ready",
    "needs-review": "urn:li:tag:needs-review",
    "no-bid": "urn:li:tag:no-bid",
    "in-envelope": "urn:li:tag:in-envelope",
}

GLOSSARY = {
    "Manufacturing": "urn:li:glossaryTerm:manufacturing.domain",
    "RFQ": "urn:li:glossaryTerm:rfq.request_for_quote",
    "DFM": "urn:li:glossaryTerm:dfm.design_for_manufacturability",
    "DigitalTwin": "urn:li:glossaryTerm:digital_twin.envelope_safety",
    "ToolWear": "urn:li:glossaryTerm:tool_wear.freshness",
    "AutomotiveParts": "urn:li:glossaryTerm:automotive.parts_lookup",
}

DOMAIN_MFG = "urn:li:domain:manufacturing_shop"
DOMAIN_AUTO = "urn:li:domain:automotive"

OWNER_SHOP_OPS = "urn:li:corpuser:b2fd91.bryan@example.com"
OWNER_ENG = "urn:li:corpuser:b2fd91.bryan@example.com"

# Structured property definitions (qualified name -> (valueType, entityTypes))
STRUCTURED_PROPS = {
    "mfg.manufacturability_score": ("urn:li:dataType:datahub.Number", ["DATASET"]),
    "mfg.quote_amount_usd": ("urn:li:dataType:datahub.Number", ["DATASET"]),
    "mfg.safety_gate": ("urn:li:dataType:datahub.String", ["DATASET"]),
    "mfg.decision": ("urn:li:dataType:datahub.String", ["DATASET"]),
    "partsnap.repair_difficulty": ("urn:li:dataType:datahub.String", ["DATASET"]),
}

# Decision per fixture (from ground truth)
DECISIONS = {}

def load_fixtures():
    for d in ("rfq", "kernels"):
        for fp in sorted((ROOT / "mfg" / "fixtures" / d).glob("*.json")):
            if fp.stem.startswith("proof-manifest"):
                continue  # manifest, not a fixture
            fx = json.loads(fp.read_text())
            fid = fp.stem
            DECISIONS[fid] = fx.get("expected_quote_decision") or fx.get("expected_decision", "quote_ready")

def _gql(query, variables):
    import urllib.request
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        f"{os.environ.get('DATAHUB_SERVER', 'http://127.0.0.1:8080')}/api/graphql",
        data=body, headers={"Content-Type": "application/json",
                            "X-DataHub-Actor": "urn:li:corpuser:datahub"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def create_vocabulary():
    """Create tags, glossary terms, domains, structured props via GraphQL mutations."""
    # Tags
    for name, urn in TAGS.items():
        try:
            _gql("""mutation($id:String!,$name:String!,$desc:String!){createTag(input:{id:$id,name:$name,description:$desc})}""",
                 {"id": urn.replace("urn:li:tag:", ""), "name": name, "desc": f"mfg tag: {name}"})
        except Exception as e:
            print(f"  tag {name}: {e}")
    print(f"  created {len(TAGS)} tags")

    # Glossary terms
    for name, urn in GLOSSARY.items():
        try:
            _gql("""mutation($id:String!,$name:String!,$desc:String!){createGlossaryTerm(input:{id:$id,name:$name,description:$desc})}""",
                 {"id": urn.replace("urn:li:glossaryTerm:", ""), "name": name, "desc": f"mfg glossary term: {name}"})
        except Exception as e:
            print(f"  term {name}: {e}")
    print(f"  created {len(GLOSSARY)} glossary terms")

    # Domains
    for name, urn in (("manufacturing_shop", DOMAIN_MFG), ("automotive", DOMAIN_AUTO)):
        try:
            _gql("""mutation($id:String!,$name:String!,$desc:String!){createDomain(input:{id:$id,name:$name,description:$desc})}""",
                 {"id": urn.replace("urn:li:domain:", ""), "name": name, "desc": f"{name} domain"})
        except Exception as e:
            print(f"  domain {name}: {e}")
    print("  created 2 domains")

    # Structured properties
    for qn, (vt, ets) in STRUCTURED_PROPS.items():
        try:
            _gql("""mutation($qn:String!,$dn:String!,$desc:String!,$vt:String!,$ets:[String!]!){
                      createStructuredProperty(input:{qualifiedName:$qn,displayName:$dn,description:$desc,valueType:$vt,entityTypes:$ets})}""",
                 {"qn": qn, "dn": qn.split(".")[-1], "desc": f"mfg structured property: {qn}",
                  "vt": vt, "ets": ets})
        except Exception as e:
            print(f"  prop {qn}: {e}")
    print(f"  created {len(STRUCTURED_PROPS)} structured properties")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vocab", action="store_true", help="create controlled vocabulary")
    ap.add_argument("--apply", action="store_true", help="apply tags/terms/domain/props to datasets")
    ap.add_argument("--all", action="store_true", help="vocab + apply")
    args = ap.parse_args()
    if args.all:
        args.vocab = args.apply = True

    load_fixtures()

    if args.vocab:
        print("-- creating controlled vocabulary --")
        create_vocabulary()
        print("vocabulary done")

    if args.apply:
        print("-- applying enrichment to mfg + partsnap datasets --")
        import urllib.request
        from datahub.sdk.main_client import DataHubClient
        from datahub_agent_context.context import DataHubContext
        from datahub_agent_context.mcp_tools import add_tags, add_glossary_terms, set_domains, add_owners

        def search_urns(q):
            """Return (name -> urn) for all datasets matching q."""
            body = json.dumps({"query": """query($q:String!){search(input:{type:DATASET,query:$q,start:0,count:100}){searchResults{entity{urn ... on Dataset{name}}}}}""",
                               "variables": {"q": q}}).encode()
            req = urllib.request.Request(
                f"{os.environ.get('DATAHUB_SERVER', 'http://127.0.0.1:8080')}/api/graphql",
                data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            out = {}
            for sr in ((d.get("data") or {}).get("search") or {}).get("searchResults") or []:
                ent = sr["entity"]
                out[ent.get("name")] = ent["urn"]
            return out

        mfg_ents = search_urns("mfg")
        ps_ents = search_urns("partsnap")
        print(f"  live: {len(mfg_ents)} mfg datasets, {len(ps_ents)} partsnap datasets")

        all_mfg = list(mfg_ents.values())
        rfq_urns = [u for n, u in mfg_ents.items() if n.startswith("fixture-") or n.startswith("kernel-")]
        mat_urns = [u for n, u in mfg_ents.items() if n.startswith("material.")]
        ps_urns = list(ps_ents.values())

        client = DataHubClient(server=os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080"), token="")
        with DataHubContext(client):
            # base enrichment: manufacturing tag + mfg domain + shop-ops owners on everything mfg
            add_tags(tag_urns=[TAGS["manufacturing"]], entity_urns=all_mfg)
            set_domains(domain_urn=DOMAIN_MFG, entity_urns=all_mfg)
            from datahub_agent_context.mcp_tools.owners import OwnershipType
            add_owners(owner_urns=[OWNER_SHOP_OPS], entity_urns=all_mfg, ownership_type=OwnershipType.TECHNICAL_OWNER)
            # glossary: RFQ on rfq/kernel urns
            add_glossary_terms(term_urns=[GLOSSARY["RFQ"]], entity_urns=rfq_urns)

            # decision tags per rfq (match by fixture stem in urn)
            for n, u in mfg_ents.items():
                if not (n.startswith("fixture-") or n.startswith("kernel-")):
                    continue
                # normalize: fixture-001 vs fixture-001-face-drill-plate vs kernel-001-proof-tapped-holes
                stem = n
                if stem.startswith("kernel-"):
                    stem = "kernel-" + stem.split("-", 2)[2] if stem.count("-") >= 2 else stem
                dec = None
                for fid, d in DECISIONS.items():
                    if stem == fid or stem.startswith(fid.split("-", 1)[0] + "-") and fid in n:
                        dec = d
                        break
                if dec is None:
                    # fallback: match by numeric id
                    for fid, d in DECISIONS.items():
                        if fid.split("-")[1] == n.split("-")[1]:
                            dec = d
                            break
                if dec is None:
                    continue
                tag = {"quote_ready": "quote-ready", "needs_review": "needs-review",
                       "no_bid": "no-bid"}.get(dec, "needs-review")
                add_tags(tag_urns=[TAGS[tag]], entity_urns=[u])

            # exotic material tag
            for n, u in mfg_ents.items():
                if any(k in n for k in ("inconel", "titanium")):
                    add_tags(tag_urns=[TAGS["exotic-material"]], entity_urns=[u])

            # partsnap: automotive tag + glossary + domain + owners
            add_tags(tag_urns=[TAGS["automotive"]], entity_urns=ps_urns)
            add_glossary_terms(term_urns=[GLOSSARY["AutomotiveParts"]], entity_urns=ps_urns)
            set_domains(domain_urn=DOMAIN_AUTO, entity_urns=ps_urns)
            add_owners(owner_urns=[OWNER_ENG], entity_urns=ps_urns, ownership_type=OwnershipType.TECHNICAL_OWNER)

            print(f"  applied to {len(all_mfg)} mfg + {len(ps_urns)} partsnap datasets")
        print("enrichment done")

if __name__ == "__main__":
    main()
