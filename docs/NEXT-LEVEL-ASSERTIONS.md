# Next-level plan: assertion-aware staleness (implemented — mechanically proven; metadata stays 0.95)

**Outcome (see addendum):** the assertion lever was implemented and mechanically proven,
but it does **not** flip t3 (a SQL codegen gap), so metadata stays **0.95**. It is kept as
a genuine DataHub-native demonstration. This file is the planning record; the verified
result is in the addendum below.

## Why this is the highest-value "next level"

Your seed currently has **zero assertions** on the planted-bug datasets, and the harness
doesn't read `get_dataset_assertions` (the MCP tool exists but is unused). The signature
DataHub move is: a **FRESHNESS assertion** on `mart_daily_summary` (it's 9 days behind
raw_trips) and quality/volume assertions on the healthcare bugs. A metadata agent reading
assertions answers "is the mart stale / is this table trustworthy?" **directly** — the one
thing a blind agent fundamentally cannot do. This:

- makes the submission unmistakably DataHub-native, not "SQL + a catalog"
- is a genuine DataHub-native capability (real platforms assert on stale tables)
- was hoped to flip **t3** → 1.0, but (see addendum) does not — t3 is a codegen gap

## The honest framing (why it is NOT test-gaming)

- Real DataHub deployments define assertions on production datasets. We are adding normal
  platform content, not moving the goalposts on the SQLite data.
- Both modes still answer the *same* 20 questions against the *same* SQLite data. The only
  change is the **DataHub context a metadata agent can read** — which is precisely the
  variable the whole submission measures. A blind agent still can't see assertions.
- t3's gold (9) is unchanged; the agent just derives it from an assertion instead of
  recomputing `julianday()`.

## Implementation (grounded in the API surface I verified)

1. **Create the assertions** via DataHub GraphQL on `:8080/api/graphql`:
   - `createTest` mutation to define a **freshness** test on `mart_daily_summary`
     (cron-based freshness check; the "behind by 9d" is its failing state).
   - `createTest` for **volume / field** tests on `mart_billing` (negative amounts) and
     `mart_demographics` (invalid ages, NULL names).
   - Attach tests to the datasets as **assertions** (via `updateDataset` with the
     `assertions` aspect, or the `reportAssertionResult` flow).
   - Confirmed available mutations: `createTest`, `updateTest`, `reportAssertionResult`,
     `upsertCustomAssertion`.
2. **Wire `get_dataset_assertions` into `build_context`** (`src/agent.py`) so assertion
   name/status/type is added to the metadata prompt (mirroring how tags/docs are added).
3. **Re-run the full `eval.sh`** → expect metadata **1.0**, write-back still True.

## Risks / open items

- **Version compatibility**: `acryl-datahub==1.6.0.6` assertion ingestion via GraphQL
  must be validated on the live instance (probe first, in a scratch script under `work/`).
- **Determinism**: assertion *status* (passing/failing) must reflect the planted bug.
  Freshness is computed against "now" — the 9-day gap must be encoded so the assertion
  deterministically reads as failing regardless of wall-clock time.
- **Scope creep**: keep it to 3–4 assertions (staleness + 2 healthcare quality) — not a
  full quality-programme facade.

## Decision

- [ ] **Approve**: I probe assertion creation on the live instance, wire the reader,
      re-run, and report the new number.
- [ ] **Decline**: keep the current honest 0.95 (only t3, documented); polish submission
      instead.


---

## PROBED 2026-08-05 — outcome (ground truth)

I ran the full probe on the live instance. **Findings:**

1. **The native path WORKS.** Assertion creation via `acryl-datahub` MCE
   (`MetadataChangeProposalWrapper` + `DatahubRestEmitter.emit()`, NOT
   `MetadataChangeProposalClass` + `emit_mcp()` which hits an avro-serialization bug)
   creates a FRESHNESS assertion that `get_dataset_assertions` reads back. GraphQL
   `createTest` was a dead end (no clean dataset-association); the MCE path is correct.
   - Scratch proof: `work/probe_assertion.py` (committed `70a283d`).
   - Note the ~seconds search-index lag before `get_dataset_assertions` sees it —
     fine for seed-time creation.

2. **Wired the reader.** `build_context` now calls `get_dataset_assertions` per table and
   renders `assertion: <TYPE> <STATUS> :: <description>` into the metadata prompt.
   Verified the FRESHNESS FAILURE signal renders only on
   `nyc_taxi_pipeline.main.mart_daily_summary`.

3. **BUT the assertion does NOT flip t3.** t3 is a SQL date-arithmetic skill gap, not a
   metadata gap: the agent writes `CAST(trip_date AS DATE)` (returns a year integer in
   SQLite) instead of `julianday(...) - julianday(...)`. The metadata already tells it
   the mart is stale; the assertion adds nothing the agent can act on without the exact
   method or the exact lag — and giving either is answer-leaking. Result: **metadata
   stays 0.95** (only t3 fails), on a 6-question taxi re-run: t1,t2,t4,t5,t6 correct.

**Conclusion:** the assertion lever is *mechanically* proven and is a genuine, honest
DataHub-native capability (seeded assertions are exactly what a real platform has on a
stale table), but it does **not** inflate the score. It strengthens the "Use of DataHub"
narrative without test-gaming. Keep it as a demonstration; do not claim metadata 1.0.
