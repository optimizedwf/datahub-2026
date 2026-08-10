#!/usr/bin/env python3
"""Metadata-aware codegen loop example — read -> act -> write-back (single file).

Demonstrates the DataHub "contribute-back" loop that any metadata-aware agent can copy:
  1. read   — search / get_lineage against a running DataHub
  2. act    — (here) surface what the lineage tells you
  3. write-back — save an Insight document back into the graph

Deps: pip install datahub-agent-context  (pulls datahub.sdk)
Usage:
    DATAHUB_SERVER=http://127.0.0.1:8080 python3 contribute_back_loop.py "mart_billing"
"""
import os
import sys

from datahub.sdk.main_client import DataHubClient
from datahub_agent_context.context import DataHubContext
from datahub_agent_context.mcp_tools import get_lineage, save_document, search


def _extract_urns(hits: dict) -> list:
    """search() returns {'searchResults': [{'entity': {'urn': ...}, ...}]}."""
    out = []
    for item in (hits or {}).get("searchResults", []) or []:
        ent = (item or {}).get("entity", {})
        urn = ent.get("urn") if isinstance(ent, dict) else None
        if urn:
            out.append(urn)
    return out


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "mart_billing"
    server = os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080")

    client = DataHubClient(server=server, token="")
    with DataHubContext(client):
        # 1) READ: find the entity and its lineage
        hits = search(query)
        urns = _extract_urns(hits)
        if not urns:
            print(f"no DataHub entities found for {query!r}")
            return 1
        urn = urns[0]
        print(f"[read] found {urn}")

        lineage = get_lineage(urn)
        ups = getattr(lineage, "upstreams", None) or (lineage or {}).get("upstreams", []) or []
        print(f"[read] upstreams: {len(ups)}")

        # 2) ACT: summarize what the graph tells us (a real agent would write SQL here)
        summary = f"query={query!r} urn={urn} upstreams={len(ups)}"

        # 3) WRITE-BACK: persist the finding as an Insight document
        doc = save_document(
            document_type="Insight",
            title=f"[contribute-back] {query}",
            content=summary,
        )
        doc_urn = doc.get("urn") if isinstance(doc, dict) else doc
        print(f"[write-back] saved {doc_urn}")
        print("[ok] read->act->write-back loop completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
