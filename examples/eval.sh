#!/usr/bin/env bash
# Metadata-Aware Code Generation with DataHub — one-command reproduction.
#
# Runs the full 20-question A/B benchmark (metadata vs plain), then a
# metadata write-back pass, and writes a canonical EVAL.json.
#
# Usage:
#   bash examples/eval.sh                 # defaults below
#   LLM_URL=... LLM_MODEL=... bash examples/eval.sh
#
# Env (all optional):
#   LLM_URL      [OI]-compatible endpoint (default http://127.0.0.1:4000/v1/chat/completions)
#   LLM_MODEL     model name (default deepseek-v4-flash)
#   DATAHUB_SERVER  GMS base URL (default http://127.0.0.1:8080)
#   EVAL_OUT     output JSON path (default EVAL.json in repo root)
#   BEST_OF      attempts per question (default 3)
set -euo pipefail

# Resolve repo root (this script lives in <root>/examples/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LLM_URL="${LLM_URL:-http://127.0.0.1:4000/v1/chat/completions}"
LLM_MODEL="${LLM_MODEL:-deepseek-v4-flash}"
DATAHUB_SERVER="${DATAHUB_SERVER:-http://127.0.0.1:8080}"
EVAL_OUT="${EVAL_OUT:-$REPO_ROOT/EVAL.json}"
BEST_OF="${BEST_OF:-3}"

PY="${PY:-.venv-datahub/bin/python}"
if [ ! -x "$PY" ]; then PY="python3"; fi

echo "== DataHub 2026 repro =="
echo "  LLM_URL       = $LLM_URL"
echo "  LLM_MODEL     = $LLM_MODEL"
echo "  DATAHUB_SERVER= $DATAHUB_SERVER"
echo "  best_of       = $BEST_OF"
echo "  python        = $PY"

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq required" >&2; exit 2
fi

# 1) Full A/B benchmark (metadata vs plain), SQL accuracy only (no write-back
#    so a clean reproducibility run doesn't pollute a shared graph).
echo "== [1/3] running 20-question A/B benchmark =="
LLM_URL="$LLM_URL" LLM_MODEL="$LLM_MODEL" LLM_NO_DIRECT=1 \
  DATAHUB_SERVER="$DATAHUB_SERVER" \
  "$PY" evals/benchmark.py --mode both --best-of "$BEST_OF" --no-writeback \
    --q-timeout 180 --out "$REPO_ROOT/evals/repro_run.json"

# 2) Metadata write-back pass — prove the contribute-back loop (Insight docs
#    written back into the graph). Small deterministic subset to keep it quick.
echo "== [2/3] metadata write-back pass =="
LLM_URL="$LLM_URL" LLM_MODEL="$LLM_MODEL" LLM_NO_DIRECT=1 \
  DATAHUB_SERVER="$DATAHUB_SERVER" \
  "$PY" evals/benchmark.py --mode metadata --ids h1,h2,h3 \
    --best-of 1 --q-timeout 120 --out "$REPO_ROOT/evals/repro_writeback.json"

# 3) Assemble EVAL.json
echo "== [3/3] assembling EVAL.json =="
"$PY" - "$REPO_ROOT" "$BEST_OF" <<'PYEOF'
import json, sys, os
root, best_of = sys.argv[1], int(sys.argv[2])
bench = json.load(open(os.path.join(root, "evals", "benchmark.json")))
ab = json.load(open(os.path.join(root, "evals", "repro_run.json")))
wb = json.load(open(os.path.join(root, "evals", "repro_writeback.json")))

meta = ab["modes"]["metadata"]["details"]
plain = ab["modes"]["plain"]["details"]
by = {d["id"]: d for d in plain}
md = {d["id"]: d for d in meta}

writeback_urns = []
for d in wb["modes"]["metadata"]["details"]:
    if d.get("write_back"):
        writeback_urns.append(d["write_back"])

pairs = [{
    "id": i, "dataset": md[i]["dataset"],
    "metadata_score": md[i]["score"], "plain_score": by[i]["score"],
    "delta": round(md[i]["score"] - by[i]["score"], 2),
    "metadata_sql": md[i]["sql"], "plain_sql": by[i]["sql"],
} for i in md if i in by]

eval_json = {
    "schema_version": "datahub-2026-eval-v1",
    "frozen": bench.get("frozen"),
    "best_of": best_of,
    "headline": {
        "metadata": ab["modes"]["metadata"]["accuracy"],
        "plain": ab["modes"]["plain"]["accuracy"],
        "paired_delta": ab.get("paired_delta"),
    },
    "per_question": pairs,
    "control_delta": ab.get("control_delta"),
    "write_back": {"verified": len(writeback_urns) > 0, "urns": writeback_urns},
    "repro": {
        "llm_url": os.environ.get("LLM_URL", ""),
        "llm_model": os.environ.get("LLM_MODEL", ""),
        "datahub_server": os.environ.get("DATAHUB_SERVER", ""),
        "cmd": "bash examples/eval.sh",
    },
}
out = os.environ.get("EVAL_OUT", os.path.join(root, "EVAL.json"))
json.dump(eval_json, open(out, "w"), indent=2)
print("EVAL.json written ->", out)
print("headline:", eval_json["headline"])
print("write-back verified:", eval_json["write_back"]["verified"])
PYEOF

echo "== DONE =="
