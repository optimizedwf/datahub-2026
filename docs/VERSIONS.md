# DataHub 2026 — Pinned versions (frozen D2 2026-08-05)

## Runtime
- DataHub quickstart v1.6.0 (GMS REST :8080, frontend :9002) — docker compose pinned
- acryl-datahub==1.6.0.6 (CLI + ingestion)
- datahub-agent-context==1.7.0 (MCP kit: search/get_entities/get_lineage/list_schema_fields/add_tags/save_document...)
- SQLite source: requires `acryl-datahub[sqlalchemy,datahub-rest]` (sql_generic module)
- full env pinned in requirements.lock.txt

## LLM (SQL generation)
- deepseek.v3.2 — temp=0 (canonical model used for the frozen results)
- endpoint/model overridable via LLM_URL / LLM_MODEL; any [OI]-compatible endpoint works

## Sample datasets (datahub-project/static-assets, cloned 2026-08-05)
| dataset | file | sha256 |
|---|---|---|
| healthcare | datasets/healthcare/healthcare.db | 287a47c53216c2322074ae802976c6c7196e2e17dc77272c6a6bd38af34ec488 |
| nyc-taxi clean | datasets/nyc-taxi/nyc_taxi.db | fef53dcc005294046da76e0484f099e81d809a05dfa433fe3e38bc1b7f46537d |
| nyc-taxi staleness | datasets/nyc-taxi/nyc_taxi_pipeline.db | 35573de0d1d05ffe4e03d3339385da3c69c986539e3d4ef24790a91a054c9871 |
| fiction-retail | datasets/fiction-retail/fiction-retail.db | 9f95373e46219e880ae54f995b6f2c2c439c3746e500e484fe3ab2bf9ac55754 |

## Submission checklist (from strategy notes)
- [x] README.md (what/why/how + A/B numbers + reproduce)
- [x] LICENSE (Apache-2.0)
- [x] examples/eval.sh one-command repro (running; EVAL.json emitted)
- [x] 3-act demo video (`demo_3act_final.mp4`, 2:35, real DataHub UI)
- [x] Contribute-back PR to datahub-project — **#96** `feat: add check-data-quality skill`
- [ ] devpost submission before 2026-08-10 17:00 EDT
