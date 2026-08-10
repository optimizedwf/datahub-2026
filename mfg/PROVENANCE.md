# Provenance

**Source:** `chow@100.111.182.5:~/chow-work/ai-cnc-programmer` (READ-ONLY source)
**Captured:** 2026-08-08T16:54:00Z
**Method:** read-only `tar` of benchmark/, materials/, machine_profiles/,
operations.json, manufacturing-intelligence.json; copied to this repo.
**tgz sha256:** ca68ea8bcbf2bafffd8222f97ab70fca6990b4b7d2b49bcc98061153fafa12b7

## Contents
- `fixtures/rfq/` — 20 RFQ fixtures (cnc-fixtures), ground-truth decisions
- `fixtures/kernels/` — 2 manufacturing-kernel fixtures (incl. no-bid Inconel)
- `fixtures/bakeoff-manifest.json` — cnc-agi-bakeoff manifest
- `materials/` — 11 material profiles (aluminum, brass, delrin, titanium, steels…)
- `machine_profiles/` — Haas VF-2 profile + 4 controller profiles
- `data/operations.json` — operation plans with cutting params + reasoning
- `data/manufacturing-intelligence.json` — manufacturability scores

## Isolation guarantee
- **Zero writes** to `~/chow-work/ai-cnc-programmer`. This repo is a vendored
  snapshot for the DataHub 2026 experiment only.
- The main manufacturing AGI project is untouched: git HEAD was `767467f`
  (Wave 200) before and after capture; no files modified by this experiment.
