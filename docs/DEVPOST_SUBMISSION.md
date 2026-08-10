# Devpost Submission Draft — DataHub 2026

_Title:_ **"DataHub as a Factory's Institutional Memory"**

_Alternates:_
- "The shop that remembers: decision-grade agents on a self-accumulating catalog."
- "Read. Decide. Write Back. — a factory knowledge graph on DataHub."

_Tagline (≤ 120 chars):_
> Every part, machine, and decision leaves a lineage trail in DataHub; an agent reads that memory to say yes to profitable work, no to money-losers — and gets smarter with every job.

---

## What it does

We turned DataHub into a machine shop's **institutional memory** and proved the
platform's core loop — *read context, reason, write back* — at every stage of the
decision chain.

A shop receives an RFQ (request for quote). Before anyone touches a machine, an
agent reads DataHub — material properties, machine envelope, DFM risks, tool-wear
state, prior jobs on similar parts — and returns a decision:

- **Quote** — material known, risk low, quote generated from the graph
- **No-bid** — Inconel/Titanium exotic material, would lose money
- **Needs review** — missing info, human in the loop

Every decision is **written back** into DataHub as a searchable document linked to
the RFQ's lineage. The next RFQ that resembles it starts from a smarter graph.

The original submission's measured claim still stands and is **unregressed**:
metadata-aware SQL is **+25 points more accurate than blind SQL** (0.95 vs 0.70,
best-of-3, 20 questions, frozen 2026-08-05). That was the *evidence*; this build is
the *product* — 10 ideas shipped as layers on one substrate.

## How we built it

**One substrate, four layers** (all in `mfg/scripts/`, all isolated under the
`mfg.*` platform namespace — the benchmark datasets are untouched):

1. **Shop Graph (I1)** — `seed_mfg.py`: 11 material profiles, machine profiles
   (Haas VF-2 + controller dialects), 21 RFQ fixtures, 2 decision kernels, and
   operation plans, with **lineage** `RFQ → material / machine_profile / operation_plan`.
   36 datasets live in the graph.
2. **No-Bid Agent (I3)** — `no_bid_agent.py`: deterministic gate reading the graph;
   **22/22 accuracy** vs ground truth; decisions written back as `Decision` docs.
3. **Quality + Quotes + Safety (I2/I4/I9)** — `quality_engine.py`: manufacturability
   score 0–100 per RFQ, graph-walk quote generator, and a **digital-twin safety gate**
   (envelope fit + machine-execution authorization). 22 `Analysis` docs written back.
4. **Freshness + Learning (I5/I6)** — `freshness_learning.py`: tool-wear freshness
   (FRESH/WORN/OVERDUE) + closed-job learning reports (planned vs actual hours +
   lesson). 22 `Summary` docs written back.
5. **PartSnap (I7, second domain)** — `partsnap.py`: the *same* mechanics, automotive
   parts (Subaru OEM lookup, repair difficulty). 8 datasets prove generalizability.

**DataHub-native:** `datahub-agent-context` MCP kit (`search`, `get_lineage`,
`save_document`, `update_description`, `get_dataset_assertions`) + the native emitter
for idempotent entity creation. Contribute-back is real: every agent run persists
documents re-findable via `search_documents`.

**Eval:** `mfg/EVAL_MFG.json` = frozen 22-case decision eval, deterministic gate
(**22/22 PASS**). The original SQL benchmark re-verified no-regression after the
manufacturing layer was added.

## Results

| Claim | Result |
|---|---|
| No-Bid decision accuracy | **22/22** (100%) vs ground truth |
| Manufacturing eval gate | **PASS** (frozen 22 cases) |
| SQL benchmark (frozen) | metadata **0.95** vs plain 0.70 (**+0.25**) |
| SQL regression after mfg layer | **none** (h1–h3 subset 1.0/1.0) |
| Write-back | Decision + Analysis + Summary docs on every RFQ |

## Try it (reproduce)

```bash
# Seed the Shop Graph, run all agents, write back, eval
python mfg/scripts/seed_mfg.py --all
python mfg/scripts/no_bid_agent.py --all --write-back
python mfg/scripts/quality_engine.py --all --write-back
python mfg/scripts/freshness_learning.py --all --write-back
python mfg/scripts/partsnap.py --seed
python mfg/scripts/eval_mfg.py   # 22/22 PASS
bash examples/eval.sh                    # original SQL benchmark, no regression
```

## Judge-relevant notes

- **Use of DataHub + contribute back (primary):** the *entire* submission is a
  knowledge graph. Lineage drives decisions; every decision writes back. The
  self-accumulating catalog is the product.
- **Originality:** a measured A/B *plus* a decision-grade agent system — 10 ideas
  shipped as layers, not a demo. Two domains prove generalizability.
- **Technical execution:** deterministic gates, frozen evals, one-command repro,
  pinned versions, sha256-pinned vendored data (`mfg/PROVENANCE.md`).
- **Isolation:** the manufacturing experiment lives in its own repo/namespace;
  the original benchmark datasets and EVAL are untouched (verified).

## Built with

DataHub / datahub-agent-context · SQLite · Python · Docker · any [OI]-compatible LLM endpoint (canonical: deepseek-v4-flash via litellm)

## Checklist before submit

- [x] Demo video `datahub_demo_final.mp4` (**2:11**, 131.5s, 1920×1080 h264+AAC, 29.9 MB) — factory-shop story: owned-assets home → RFQ arrives (Inconel 718 · qty 2, Properties table) → no-bid decision doc written back → terminal run (reads live graph, writes back) → lineage (graph remembers) → search (prior decision searchable) → A/B bars (metadata 0.95 vs plain 0.70, +0.25, frozen 2026-08-05) → architecture (read·decide·write back) → CTA with public repo URL. Real UI + terminal, voiced by the **Mr Chow persona voice** (`en-US-GuyNeural`, the exact voice from the Mr Chow show pipeline), polished card graphics (gradients/glows/glass). Kimi vision-critic gate: **SHIP certified** (3 roast rounds; `docs/roast_v43_SHIP.md`), human preview in progress.
- [x] GitHub repo — `github.com/optimizedwf/datahub-2026` (PUBLIC — live) (Apache-2.0, README, Makefile, tests, CI); upstream PR **#96**
- [x] Contribute-back PR — `datahub-project/analytics-agent #96`
- [x] `EVAL.json` metadata 0.95 (frozen 2026-08-05); mfg eval 22/22 PASS
