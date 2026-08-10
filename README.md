# DataHub as a Factory's Institutional Memory

**Category #2 — Metadata-aware Code Generation**

> DataHub becomes a factory's institutional memory — every part, machine, and
> decision leaves a lineage trail, and an agent uses that memory to say **yes to
> profitable work, no to money-losers**, and to **get smarter with every job**.

This submission builds a **manufacturing knowledge graph** on DataHub and proves the
platform's core loop — *read context, reason, write back* — at every stage of a
machine shop's decision chain: quoting, manufacturability review, machining safety,
tool maintenance, and closed-loop learning.

The same substrate that powers the original SQL benchmark (0.95 vs 0.70) now powers
**decision-grade agents** on a self-accumulating catalog.

---

## The one-line story

A machine shop gets an RFQ (request for quote). Before anyone touches a machine,
an agent reads DataHub — material properties, machine envelope, DFM risks,
tool-wear state, prior jobs on similar parts — and returns a decision:

| Decision | Example | Why |
|---|---|---|
| **Quote** | Brass plate, 3 ops, in-envelope | material known, risk low, quote generated from graph |
| **No-bid** | Inconel/Titanium part | exotic material, high DFM risk, would lose money |
| **Needs review** | Stainless + missing thread spec | missing info — human in the loop |

Every decision is **written back** into DataHub as a searchable document linked to
the RFQ. The next RFQ that resembles it starts from a smarter graph.

---

## The build: 10 ideas, one substrate

All 10 ideas from the brainstorm are shipped as layers on **one DataHub substrate**
(`mfg.*` platform namespace — fully isolated from the benchmark data).

### Substrate — I1: Shop Graph
`mfg/scripts/seed_mfg.py` seeds the factory's institutional memory:
- **11 materials** (aluminum 6061, brass 360, delrin, steel 1018/1045/4140,
  stainless 304/316, titanium 6Al-4V, Inconel, magnesium, graphite EDM) with
  cutting parameters and cost
- **Machine profiles** (Haas VF-2 3-axis + controller dialects: NGC, GRBL, PathPilot, Fanuc 0i)
- **21 RFQ fixtures** with real geometry, tolerances, operations, expected DFM risks
- **2 decision kernels** (proof-tapped-holes, no-bid-Inconel)
- **Lineage**: `RFQ → material`, `RFQ → machine_profile`, `RFQ → operation_plan`

Verified live: 36 mfg datasets, lineage confirmed via GraphQL.

### Layer 1 — I3: No-Bid Agent (`mfg/scripts/no_bid_agent.py`)
Deterministic decision gate reading the graph:
- exotic materials (Inconel/Titanium/Magnesium/Graphite) → **no_bid**
- stainless + missing info + MEDIUM/HIGH DFM risks → **needs_review**
- otherwise → **quote_ready**
- **22/22 accuracy** vs ground truth; decisions written back as `Decision` docs
  linked to RFQ URNs.

### Layer 2 — I2 + I4 + I9: Quality, Quotes, Safety (`mfg/scripts/quality_engine.py`)
- **I2 Manufacturability assertions**: DFM score 0–100 per RFQ (thin-wall −, exotic −30 hard fail)
- **I4 QuoteDesk**: graph-walk quote — setup hours + ops hours + material cost + margin
- **I9 Safety layer**: digital-twin envelope fit + machine-execution authorization gate
  (`kernel-001` → **BLOCKED** because `machine_execution_authorized: False`)
- All 22 RFQs written back as `Analysis` docs (score, quote, gate).

### Layer 3 — I5 + I6: Freshness & Learning (`mfg/scripts/freshness_learning.py`)
- **I5 Tool-wear freshness**: per-operation tool life vs hours used →
  FRESH / WORN / OVERDUE (a freshness-style assertion on the tool catalog)
- **I6 Learning loop**: closed-job reports — planned vs actual hours + lesson,
  written back as `Summary` docs so the next quote learns from the last job.

### Layer 4 — I7: PartSnap, second domain (`mfg/scripts/partsnap.py`)
The *same* mechanics, a *different* domain: automotive part lookup
(Subaru OEM parts, repair difficulty, alternates). 8 part datasets seeded on
platform `partsnap`, lookup agent returns found/needs-review — proving the
graph pattern generalizes beyond machining.

### Evidence — I8: SQL core (unchanged, unregressed)
The original benchmark is intact and **re-verified** this week:
metadata-aware SQL **0.95 vs 0.70 plain (+0.25)** on the frozen 20-question
benchmark (h1–h3 subset re-run 1.0/1.0 after the manufacturing layer was added —
**no regression**).

### Enrichment — B8: controlled vocabulary (`mfg/scripts/enrich_graph.py`)
The graph is **tagged, glossaried, domained, and owned** — the same layer a real
factory data team would build first:

| Vocabulary | Count | Applied to |
|---|---|---|
| Tags (`manufacturing`, `quote-ready`, `no-bid`, `exotic-material`, `automotive`, …) | 9 | all mfg + partsnap datasets, per-decision tags on RFQs |
| Glossary terms (`Request for Quote`, `AutomotiveParts`, …) | 6 | RFQ/kernel + partsnap datasets |
| Domains (`manufacturing_shop`, `automotive`) | 2 | 35 mfg + 8 partsnap datasets |
| Owners (`bryan@example.com` technical owner) | 1 | all mfg + partsnap datasets |
| Structured properties (decision, manufacturability score, quote amount, safety gate, repair difficulty) | 5 | defined on the graph |

Verified end-to-end via GraphQL (e.g. `rfq.fixture-010-odd-material-brass` →
tags `[manufacturing, quote-ready]`, term `request_for_quote`, domain
`manufacturing_shop`).

---

## How to reproduce

```bash
# 1) Seed the Shop Graph (mfg.* + partsnap.* platforms)
python mfg/scripts/seed_mfg.py --all

# 2) Run the No-Bid Agent over all RFQs
python mfg/scripts/no_bid_agent.py --all --write-back

# 3) Quality + quotes + safety gates
python mfg/scripts/quality_engine.py --all --write-back

# 4) Freshness + learning loop
python mfg/scripts/freshness_learning.py --all --write-back

# 5) PartSnap (second domain)
python mfg/scripts/partsnap.py --seed

# 6) Frozen decision eval (22 cases — GATE PASS 22/22)
python mfg/scripts/eval_mfg.py

# 7) Original SQL benchmark (no regression)
bash examples/eval.sh

# 8) Enrich the graph (tags, glossary, domains, owners — idempotent)
python mfg/scripts/enrich_graph.py --all
```

### Entity model

```
                    ┌──────────────────────────────────────────────┐
                    │            DataHub (one substrate)           │
                    │  mfg.*  ·  partsnap.*  ·  healthcare.* …     │
                    └───────┬──────────────────────────┬───────────┘
                            │                          │
   ┌────────────────────────▼──────────┐   ┌───────────▼──────────────┐
   │   mfg.*  Shop Graph (36 entities) │   │ partsnap.* (8 entities)  │
   │  material.<family> (11)           │   │ part-001..part-008       │
   │  machine_profile.default_3axis    │   │  (Subaru OEM parts)      │
   │  operation_plan.master            │   └───────────▲──────────────┘
   │  rfq.<fixture> (21)  ─────────────┼───────────────┘ same substrate
   │  kernel-* (2)                     │        different domain
   └───────────┬───────────────────────┘
               │ lineage (RFQ → material · RFQ → machine · RFQ → op plan)
               ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  Agents read the graph, reason, and WRITE BACK:                 │
   │   Decision docs (22) · Analysis docs (22) · Summary docs (22)   │
   │   tags · glossary terms · domains · owners (B8 enrichment)      │
   └─────────────────────────────────────────────────────────────────┘
```

## Repo layout

```
mfg/
  data/            vendored manufacturing intelligence + operations plans
  fixtures/        RFQ fixtures + decision kernels + bakeoff manifest
  materials/       11 material YAML profiles
  machine_profiles/ default_3axis + controller dialects
  scripts/         seed_mfg, no_bid_agent, quality_engine,
                   freshness_learning, partsnap, eval_mfg, enrich_graph
evals/           frozen decision eval (EVAL_MFG.json) + A/B results
                   (AB-RESULTS.md, repro10_fresh_20260808.json)
  ENTITY_MODEL.md  the mfg.* platform schema + lineage model
  PROVENANCE.md    vendored-data provenance (sha256-pinned snapshot)
  EVAL_MFG.json    frozen 22-case decision eval
examples/eval.sh   original SQL benchmark (frozen, unregressed)
src/agent.py       original metadata-aware SQL agent
```

## Gallery

Real captures from the live graph:

- `docs/gallery/mfg_shop_graph.png` — 36 mfg datasets in DataHub search
- `docs/gallery/rfq_010_brass.png` — RFQ fixture dataset (brass plate, 3 ops)
- `docs/gallery/partsnap_brake_pad.png` — PartSnap automotive domain

## Evidence trail

- **`docs/AB-RESULTS.md`** — the SQL A/B benchmark (0.95 vs 0.70)
- **`evals/AB-RESULTS.md`** — A/B results incl. fresh 2026-08-08 reproducibility run (metadata 9/10 vs plain 5/9)
- **`docs/gallery/`** — live-graph captures used in the 3:25 demo video
- **`docs/CONTRIBUTE-BACK.md`** — the write-back loop proof
- **`docs/DEVPOST_SUBMISSION.md`** — full submission narrative
- **`mfg/EVAL_MFG.json`** — frozen 22-case decision eval (GATE PASS)

---

## Why this is a DataHub story

DataHub is the *memory*. Every part, material, machine, and decision is an entity
with lineage, properties, and documents. The agents are thin — they read the graph,
reason, and write back. The value compounds: **every RFQ answered makes the next
answer better**, exactly like metadata-aware SQL beats blind SQL by +25 points.
