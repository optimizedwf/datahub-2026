# OSS contribution draft — `datahub-project/analytics-agent`

**Target repo:** `github.com/datahub-project/analytics-agent` (Apache-2.0, the current home of
DataHub's agent tooling — NOT the old `datahub-agent-context` repo, which is no longer the
active surface). Verified structure: `backend/src/analytics_agent/skills/<name>/SKILL.md`
(YAML frontmatter + markdown body) with a Python impl in `datahub_skills.py`, wrapped as a
LangChain StructuredTool by `skills/loader.py`.

**Why this and not a loop demo:** the repo already ships `search-business-context`,
`publish-analysis`, `save-correction`, `improve-context`. The one gap a metadata-aware agent
still has is reading **data-quality / freshness assertions** before writing SQL. That is
exactly the capability I built and verified in this hackathon (`get_dataset_assertions` +
prompting "assertion: FRESHNESS FAILURE"). Packaging it as a skill is adoptable, small, and
aligned with the repo's own design.

---

## Candidate: `check-data-quality` skill

### `backend/src/analytics_agent/skills/check-data-quality/SKILL.md`

```markdown
---
name: check_data_quality
description: >
  Call this whenever the user asks about a dataset's trustworthiness, freshness,
  staleness, known data-quality issues (negative values, NULLs, out-of-range),
  or before querying a table that may be stale or known-broken. Reads DataHub
  assertions for the candidate table(s) and surfaces any FAILING freshness or
  quality checks so you can reason about stale / planted-bug data before writing
  SQL — instead of blindly trusting a table that is known to lag its source.
metadata:
  author: analytics-agent
  version: "1.0"
---

## Data Quality & Freshness Check

Run this workflow **before writing SQL** any time the question involves staleness,
freshness, trust, or a planted/known data-quality problem on a specific table
(e.g. "how many rows have a negative amount", "is this mart behind its source",
"is this table trustworthy", "how stale is X").

Do **not** skip this to go straight to `list_tables` or `execute_sql`. Assertions
are the DataHub-native signal for known-broken or stale data.

---

### Step 1 — Resolve the candidate dataset URN

From the tables you've already discovered via `search` / `get_entities`, call
`get_dataset_assertions` for each candidate mart/table the question targets:

```
get_dataset_assertions(urn="<dataset_urn>", count=10)
```

`dataset_urn` is the `urn:li:dataset:(...)` from your earlier catalog lookups.

### Step 2 — Read the assertion summary

For each assertion returned, note `type` (e.g. `FRESHNESS`, `VOLUME`, `FIELD`),
the `latestResultType` (`SUCCESS` / `FAILURE` / `NO_RUN`), and the description.

- A **`FRESHNESS` assertion with `FAILURE`** means the table lags its source —
  the freshness SLA was breached. For staleness questions this is the signal to
  compute the lag between the raw source and the mart.
- A **`VOLUME` / `FIELD` assertion with `FAILURE`** means a known data-quality
  problem is planted in this table (e.g. negative amounts, NULL names) — exactly
  the kind of "planted bug" question you should answer directly.

### Step 3 — Fold the signal into the query

- For **staleness / days-behind** questions: the failing freshness assertion tells
  you *which* table is stale. Query both the raw source and the mart, and compute
  the difference (e.g. `julianday(max(raw_ts)) - julianday(max(mart_date))`) —
  preferring `julianday`/`date()` over `CAST(... AS DATE)`, which is unreliable for
  text dates.
- For **data-quality count** questions: use the failing assertion as confirmation
  that a filter like `WHERE amount < 0` is the right answer surface.

**Cite what you find.** When you answer a staleness or quality question, reference
the assertion that led you there. If a table has no assertions, say so and note the
gap (suggest `/improve-context`).
```

### Supporting implementation (optional, in `datahub_skills.py`)

If the repo wants a first-class tool rather than a prompt-only skill, the Python impl
is a thin wrapper (already verified against a live DataHub):

```python
def check_data_quality(dataset_urn: str) -> dict:
    """Read DataHub assertions for a dataset and summarize status."""
    from datahub_agent_context.context import get_datahub_client
    from datahub_agent_context.mcp_tools import get_dataset_assertions

    client = get_datahub_client()
    r = get_dataset_assertions(urn=dataset_urn, count=10)
    out = []
    for a in (r or {}).get("data", {}).get("assertions", []):
        out.append({
            "type": a.get("type"),
            "latestResult": a.get("latestResultType"),
            "description": (a.get("description") or "")[:160],
        })
    return {"dataset": dataset_urn, "assertions": out}
```

---

## PR description (as opened — **PR #96**)

```
## Summary
Adds a `check_data_quality` skill so the agent reads DataHub assertions
(freshness / volume / field) before writing SQL — surfacing stale or
known-broken tables instead of blindly trusting them. Mirrors the existing
`search-business-context` skill structure (SKILL.md frontmatter + markdown body)
and reuses the already-available `get_dataset_assertions` MCP tool.

## Why
A metadata-aware agent is only as good as the signals it reads. Assertions are
the DataHub-native way to know "this table is 9 days stale" or "this table has a
planted negative-amount bug". This skill makes the agent reason about data
trustworthiness explicitly, which is a common gap in analytics agents.

## What it adds
- `backend/src/analytics_agent/skills/check-data-quality/SKILL.md`
- optional `check_data_quality()` impl in `datahub_skills.py`

## Validation
Verified end-to-end against a live DataHub instance: a seeded FRESHNESS assertion
on a stale mart is read by `get_dataset_assertions` and rendered into the prompt
as `assertion: FRESHNESS FAILURE`. A 20-question A/B benchmark (metadata context
vs plain) shows the assertion signal is surfaced only where intended.

Diff < 100 lines. No new dependencies (uses the existing `datahub_agent_context`
toolset). Apache-2.0.
```

---

## Status — PR **#96** is OPEN

Forked to `optimizedwf/analytics-agent`, added `check-data-quality/SKILL.md`, opened
**PR #96** → <https://github.com/datahub-project/analytics-agent/pull/96>. One follow-up a
maintainer may want: confirm the skill/loader allowlist wiring in `skills/loader.py` (the
`get_dataset_assertions` tool lives in `datahub_agent_context.mcp_tools`, but the repo's
runtime allowlist wasn't exhaustively verified before opening). Link it in the Devpost
"Open-source contributions" field.
