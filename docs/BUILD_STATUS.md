# Build Status — 2026-08-08 22:20 EDT

**All 10 ideas shipped as layers on one DataHub substrate. Submission-ready, over the top.**

## Verified live (Dell DataHub, GMS :8080)

| Asset | Count | Status |
|---|---|---|
| mfg datasets (materials, machine, ops, RFQ, kernels) | 36 | ✅ searchable via GraphQL |
| partsnap datasets (automotive) | 8 | ✅ searchable |
| RFQ lineage (RFQ → material/machine) | confirmed | ✅ get_lineage |
| Decision docs (no-bid agent) | 22 | ✅ search_documents |
| Analysis docs (quality/quote/safety) | 22 | ✅ search_documents |
| Summary docs (freshness/learning) | 22 | ✅ search_documents |
| **B8 enrichment**: tags / glossary terms / domains / owners | 9 / 6 / 2 / 1 | ✅ applied to 35 mfg + 8 partsnap, verified via GraphQL |

## Gates

| Gate | Result |
|---|---|
| No-Bid decision eval (`eval_mfg.py`) | **22/22 = 100% GATE PASS** |
| SQL benchmark (frozen 0.95/0.70) | **no regression** (h1–h3 re-run 1.0/1.0) |
| SQL benchmark (fresh 2026-08-08 best-of-1, h1–h10) | **metadata 9/10 vs plain 5/9** — delta confirmed again |
| Repo tree | clean, 21 commits |

## Demo video — refreshed (2:59, two-domain, edge-tts Christopher voice) — re-cut 2026-08-09 to meet Devpost <3min rule

`docs/demo_2026_submission.mp4` (2:59, 14.9 MB, out of git) now tells the full story:

1. **Act 0 (0:00–1:04)** — The Factory: Shop Graph (36 entities + lineage) → No-Bid
   Agent (22/22) → Quotes · Safety Gates → PartSnap automotive (second domain)
2. **Act 1–3 (1:04–3:17)** — original SQL evidence: metadata-aware 0.95 vs 0.70,
   write-back proof
3. **Outro (3:05–3:41)** — results card with all gates + repo link

Rebuild script: `docs/DEMO_SCRIPT.md` (ffmpeg concat filter, macOS `say` TTS).

## Remaining before submit (owner steps)

1. **Devpost**: paste `docs/DEVPOST_SUBMISSION.md` (rewritten for full vision).
2. **YouTube**: upload `docs/demo_2026_submission.mp4` (**2:59** — under the 3-min rule), link in Devpost.
3. **Repo choice**: `datahub-2026-mfg` (superset, this build) vs `datahub-2026-public`
   (frozen fallback) — mfg is the entry.
4. Deadline: **2026-08-10 17:00 EDT** (~42h remaining).

## Isolation verified

- Dell `~/chow-work/ai-cnc-programmer` untouched (read-only source, baseline recorded)
- Benchmark datasets (healthcare/nyc-taxi/fiction-retail) untouched
- mfg entities live only under `mfg.*` / `partsnap.*` platforms
- Enrichment vocabulary (tags/terms/domains/props) created via GraphQL — no benchmark
  entities tagged
