# A/B Benchmark Results — fresh evidence

## Canonical (frozen 2026-08-05, EVAL.json, 20 questions, best-of-3)
- **metadata: 0.95** (19/20) vs **plain: 0.70** (14/20) — paired delta **+0.25**
- 3 datasets: healthcare (10), nyc-taxi-pipeline (6), fiction-retail (4)
- Write-back verified: agent findings published as docs in the graph

## Fresh reproducibility run (2026-08-08 ~21:53 EDT)
- Engine: `LLM_URL=http://127.0.0.1:4000/v1/chat/completions LLM_MODEL=deepseek-v4-flash`
- Mode: best-of-1, both modes, no-writeback, ids h1–h10
- **metadata: 9/10** (h1–h8, h10 correct; h9 LLM-throttle timeout)
- **plain: 5/9** (h1, h2, h5, h6, h7 correct; h3/h4/h8 wrong-table or LLM-fail, h9 LLM-throttle; h10 not reached)
- Delta direction confirmed: reading the graph first helps (metadata ≥ plain on every completed pair except h9 throttle)
- Failure modes observed: h3/h4/h8 plain mode picked `raw_*` tables (no metadata = wrong table choice) — exactly the gap the demo narrates
- Run terminated after GMS deadlock (known socket-leak issue, see BUILD_STATUS.md); evidence preserved in `evals/repro10_fresh_20260808.json`

## How to re-run
```bash
cd ~/chow-work/agent-comp/builds/datahub-2026
LLM_URL=http://127.0.0.1:4000/v1/chat/completions LLM_MODEL=deepseek-v4-flash \
  .venv-datahub/bin/python evals/benchmark.py --mode both --best-of 1 --no-writeback \
  --q-timeout 180 --ids h1,h2,h3,h4,h5,h6,h7,h8,h9,h10 --out /tmp/repro10_run.json
```
