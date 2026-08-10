# Contribute-back plan — open-source contribution (judged bonus)

**Why this is the highest-leverage contribution:** the category is "use DataHub + write
back to the graph," and judges are DataHub insiders who reward *adoptable* artifacts — not
screenshots. A small, clean, documented, upstream-shaped artifact is worth more than polish
on the harness.

**Authoritative artifact:** [`docs/OSS_PROPOSAL.md`](OSS_PROPOSAL.md) — the corrected,
verified plan. This file is kept as a short pointer so the two don't drift.

---

## Recommended target: `datahub-project/analytics-agent`

The active upstream home for DataHub's agent tooling is **`datahub-project/analytics-agent`**
(Apache-2.0). It ships skills under `backend/src/analytics_agent/skills/<name>/SKILL.md`
(YAML frontmatter + markdown body) with a Python impl in `datahub_skills.py`, wrapped by
`skills/loader.py`. (The older `datahub-agent-context` / `datahub-skills` repos are not the
current skills surface — the agent-context tooling now lives behind analytics-agent.)

## Candidate 1 (recommended) — `check-data-quality` skill (reads assertions)

A new skill that reads DataHub **assertions** (`get_dataset_assertions`) before writing SQL
and surfaces stale / known-broken tables as `assertion: FRESHNESS FAILURE`. This is the one
capability the existing analytics-agent skills (`search-business-context`, `publish-analysis`,
`save-correction`, `improve-context`) don't cover, and it is exactly what this hackathon
built and verified. Full SKILL.md + optional impl + PR description are drafted in
[`docs/OSS_PROPOSAL.md`](OSS_PROPOSAL.md).

## Candidate 2 — the benchmark as an eval-gate recipe

`evals/benchmark.py` + `evals/benchmark.json` is a deterministic, gold-answer, A/B scorer
(metadata vs blind). Package it as a documented "agent eval-gate" recipe — reusable by
anyone building a metadata-aware agent.

## Bonus artifact — `examples/contribute_back_loop.py`

A single-file, stdlib + `datahub-agent-context` loop (read `mart_billing` → lineage → write
an Insight doc back → re-find via `search_documents`). Verified end-to-end on a live DataHub.
Good as a companion example to the skill.

## PR status — **OPEN**

1. Forked `datahub-project/analytics-agent` → `optimizedwf/analytics-agent`.
2. Added `backend/src/analytics_agent/skills/check-data-quality/SKILL.md` (single-file, < 100 lines).
3. PR title: `feat: add check-data-quality skill (DataHub assertions before writing SQL)`.
4. PR description links the +0.25 A/B evidence and points to the verification.
5. **PR #96** — <https://github.com/datahub-project/analytics-agent/pull/96> (open).

## Status

- [x] Verify target repo is `datahub-project/analytics-agent` (its skills/ layout confirmed)
- [x] Write + self-test `examples/contribute_back_loop.py` on Dell against live DataHub
- [x] Draft `check-data-quality` skill + PR description (`docs/OSS_PROPOSAL.md`)
- [x] Open contribute-back PR — **datahub-project/analytics-agent #96** (`feat: add check-data-quality skill`)
- [ ] Link PR in Devpost submission (Devpost field)
