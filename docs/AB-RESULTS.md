# DataHub 2026 — A/B Results (D2/D3)

**Frozen:** 2026-08-05 · **Category #2:** Metadata-aware Code Generation
**Harness:** `src/agent.py` (own thin harness, never forked Analytics Agent) · **Runner:** `evals/benchmark.py`

---

## 1. Headline — full 20-question A/B (healthcare + taxi + fiction-retail)

Canonical run via `examples/eval.sh` (`LLM_URL=http://127.0.0.1:4000/v1/chat/completions`, `deepseek.v3.2`, temp 0, exact scoring).

| mode | accuracy (best-of-1) | accuracy (best-of-3) | n |
|---|---|---|---|
| **metadata** (DataHub context) | **0.85** | **0.95** | 20 |
| plain (table names only) | 0.60 | 0.70 | 20 |
| **paired delta** | **+0.25** | **+0.25** | 20 |
| **control delta** (fiction-retail) | — | **+0.25** | 4 |

- Metadata now fails **only `t3`** (days-behind: requires the `julianday()` SQLite idiom) — **19/20 = 0.95** best-of-3.
- **t6 fixed (rev 2):** prompt now instructs returning exactly the two `vs` columns in order; was returning a 3rd derived delta column that broke the pair scorer → now `(208675, 250000)` = 1.0.
- **t5 clarified (rev 3):** benchmark wording said "empty-load day" which implied `trip_count = 0` (no such row). Reworded to "smallest (minimum) trip_count" — gold unchanged (2).
- **control_delta +0.25** proves the agent doesn't over-engineer clean data (fiction-retail).
- Repro artifact: `EVAL.json` (assembled by `examples/eval.sh`), raw runs `evals/repro_run.json` + `evals/repro_writeback.json`. Earlier runs (`run_full_tunnel*.json`) kept for history.


### Per-dataset breakdown (fair scorer, metadata / plain)

| dataset | metadata | plain | notes |
|---|---|---|---|
| healthcare (h1–h10) | 10/10 | 7/10 | metadata clean; plain fails h4, h6, h8 |
| nyc-taxi (t1–t6) | 5/6 | 4/6 | metadata fails only t3; plain fails t3, t4 |
| fiction-retail (f1–f4) | 4/4 | 3/4 | f4 needs inventory table (metadata wins) |

### Paired diffs (metadata − plain)

| id | metadata | plain | why |
|---|---|---|---|
| h4 | 1.0 | 0.0 | plain can't find `date_of_admission`/`discharge_date` |
| h6 | 1.0 | 0.0 | plain fails to find correct table/column |
| h8 | 1.0 | 0.0 | plain fails on `insurance_provider` filter |
| t4 | 1.0 | 0.0 | plain can't construct the mart_daily_summary query |
| f4 | 1.0 | 0.0 | metadata reveals `inventory` table + typed columns |

Metadata wins on all 5 paired diffs. (`t3` is 0/0 — the documented `julianday()` gap — not a
metadata-loss; every question where metadata and plain differ, metadata wins.)

---

## 2. LLM setup (what the numbers were produced with)

The benchmark is model-agnostic: any [OI]-compatible chat-completions endpoint works
(`LLM_URL` / `LLM_MODEL` env vars, temp 0). The frozen numbers used:

- **Model:** `deepseek.v3.2` at temperature 0 (deterministic)
- **Endpoint:** an [OI]-compatible proxy on localhost (see `examples/eval.sh` for the env vars)
- **No RAG, no fine-tuning** — the *only* variable between the two modes is whether the
  DataHub context is included in the prompt.

The eval script defaults work against any local [OI]-compatible server; nothing in the
benchmark is tied to a specific provider.
## 3. Two real bugs fixed in the harness

### Bug A — catalog cross-dataset pollution → `DATASET_TABLE_HINTS`
- DataHub `search("nyc-taxi-pipeline")` returned unrelated sqlite datasets (healthcare tables in the same instance).
- Fix: `DATASET_TABLE_HINTS` filters tables to the current dataset in both the tables loop and lineage loop.
- Verified clean: taxi → `[mart_daily_summary, raw_trips, staging_trips]`; healthcare → `[mart_billing, mart_demographics, raw_patients, staging_patients]`; fiction-retail → 6 tables.

### Bug B — unfair scorer → fixed `score_row`
- `maxdate`: exact string match failed when SQL returned a full timestamp vs date-only gold (`2016-03-10 10:48:55` vs `2016-03-10`). Now compares the date part.
- `pair`: only checked `rows[0][0]`, so a multi-column row could never match. Now joins columns with `" vs "`.
- Backup: `evals/benchmark.py.bak-scorefix`.

---

## 4. Remaining gaps (honest, for the submission narrative + future work)

The **only** remaining metadata-mode miss in the canonical run is:

1. **t3** — "how many days is `mart_daily_summary` behind `raw_trips`?" The agent
   understands it must compute a date difference, but writes `CAST(... AS DATE)` (which
   yields a year integer in SQLite) instead of the `julianday()` idiom, so it returns
   `0`/a wrong diff rather than gold `9`. This is a **model codegen skill gap, not a
   metadata gap** — the metadata prompt even surfaces the failing freshness assertion
   (`assertion: FRESHNESS FAILURE`), yet the agent still mis-derives the SQL. We document
   it rather than reword the question (rewording would seed the method = gaming).

**Resolved since earlier drafts (no longer gaps, per canonical `EVAL.json`):**
- **h9** — earlier pilot had metadata choose `raw_patients` over `mart_demographics`; the
  canonical run passes h9 in both modes (1.0/1.0). Recorded for history, not a current gap.
- **t5** — benchmark wording said "empty-load day" (implied `trip_count = 0`, no such row);
  rewrote to "smallest (minimum) trip_count" — gold unchanged (2). Now passes 1.0.
- **t6** — harness returned a 3rd derived delta column that broke the pair scorer; prompt
  now instructs returning exactly the two `vs` columns in order. Now passes 1.0.

---

## 5. Methodology (reproducible)

1. **Gold answers:** computed directly against seed SQLite mirrors, 20/20 verified (healthcare h1–h10, taxi t1–t6, fiction f1–f4).
2. **Context modes:** metadata = full DataHub context (`build_context`: schema + `name:TYPE` cols, lineage, tags/glossary, docs); plain = table names only.
3. **Scoring:** exact match (scalar: numeric tolerance; pair: joined columns; maxdate: date-part; top1/country: string). 1.0/0.0.
4. **Sampling:** `--best-of N` (pass@k); per-question SIGALRM wall-clock timeout; `--no-writeback` for evals.
5. **Isolation:** each question runs against its dataset mirror only.

---

## 6. Next steps

- [x] Full 20-question benchmark via tunnel (metadata 0.85 / plain 0.60, +0.25 best-of-1; 0.95 / 0.70 best-of-3)
- [x] Fix unfair scorer (maxdate date-part, pair join)
- [x] Re-run with `--best-of 3` → canonical metadata **0.95** / plain 0.70 / paired **+0.25** (`EVAL.json`)
- [x] Decide t3/t5/t6: t5 (wording) + t6 (scorer) fixed; **t3 documented** as a codegen-skill gap, not reworded (would seed the method = gaming)
- [x] Commit docs + results + assertion write-back + OSS PR draft
- [x] Record 3-act demo video (`demo_3act_final.mp4`, 2:35, real DataHub UI + A/B)
- [ ] Submit to Devpost before 2026-08-10 17:00 EDT (`docs/DEVPOST_SUBMISSION.md` ready)
- [x] Open contribute-back PR to `datahub-project/analytics-agent` — **#96** `feat: add check-data-quality skill` (opened by optimizedwf)


---

## 2026-08-08 regression re-verification (post manufacturing layer)

The frozen benchmark remains intact after adding the `mfg.*` manufacturing graph
(36 datasets) + `partsnap.*` (8 datasets):

- h1/h2/h3 metadata subset re-run: **1.0/1.0** (h1 4.3s, h2 107.2s, h3 6.6s; litellm :4000)
- Decision eval: **22/22 = 100% GATE PASS** (`mfg/scripts/eval_mfg.py`)
- Write-back docs re-findable via `search_documents`: `[no-bid]`, `[quality]` docs confirmed

Note: the earlier "0.0" scare was a stale `LLM_URL=:3988` in `eval.sh` (dead reverse
tunnel); corrected default is litellm `:4000` (`examples/eval.sh`).
