# MFG Entity Model — DataHub as the Shop's Institutional Memory

## Design principle
Every artifact the shop already produces becomes a **DataHub entity** with lineage.
DataHub's native concepts (dataset, assertion, doc, structured property, lineage,
glossary term) map 1:1 onto manufacturing concepts.

## Entity map (platform: mfg)

| DataHub entity | Platform/name | Source artifact | Key metadata |
|---|---|---|---|
| Dataset | `mfg.rfq` | fixtures/rfq/*.json | material, quantity, tolerance, finish, missing_info, expected_decision |
| Dataset | `mfg.material` | materials/*.yaml | family, hardness, feeds/speeds, coolant, notes |
| Dataset | `mfg.machine_profile` | machine_profiles/*.yaml | controller, axes, spindle, feed, work_offset |
| Dataset | `mfg.operation_plan` | data/operations.json | op sequence, cutting params, reasoning |
| Dataset | `mfg.dfm_packet` | (referenced) | PART_SPEC, CAM_PLAN, SETUP_SHEET, SHOP_NOTE |
| Dataset | `mfg.decision` | agent write-back | accept/decline/needs-review + reasoning |

## Lineage (the story)

```
RFQ ──► Job ──► DFM packet ──► CAM plan ──► toolpath ──► G-code ──► simulation
 │        │           │            │            │            │            │
 └─ material / machine_profile / operation_plan feeding every stage
```

## Assertions (data quality on the shop floor)

| Assertion | Target | Meaning |
|---|---|---|
| manufacturability_score >= 80 | mfg.dfm_packet | DFM review passed |
| envelope_fit = PASS | mfg.job | digital twin AABB check |
| tool_wear_freshness | mfg.tool | tool life within limits |
| no_bid_risk = LOW | mfg.rfq | no exotic material / thin-wall / tight-tol flags |

## Write-back targets
- Decision doc per RFQ: `save_document` with accept/decline/needs-review + reasoning
- Structured properties on RFQ dataset: decision, confidence, risk_categories,
  review_gates, scope_status
- Learning report per closed job (closed_loop schema): planned vs actual
