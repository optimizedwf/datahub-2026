#!/usr/bin/env bash
# Fetch the three seed SQLite datasets from datahub-project/static-assets
# (the official DataHub sample-data repo). Each file is also reproducible
# from source CSVs via datasets/<name>/create_db.py (see datasets/README.md).
#
# Usage:  bash examples/fetch_datasets.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="https://raw.githubusercontent.com/datahub-project/static-assets/master/datasets"

fetch() {
    local path="$1" out="$2"
    mkdir -p "$(dirname "$out")"
    if [ -f "$out" ] && [ -s "$out" ]; then
        echo "  exists: $out"
    else
        echo "  fetching $path"
        curl -fL --retry 3 --max-time 300 "$BASE/$path" -o "$out"
    fi
}

echo "== Fetching DataHub sample datasets (datahub-project/static-assets) =="
fetch healthcare/healthcare.db           "$REPO_ROOT/datasets/healthcare/healthcare.db"
fetch nyc-taxi/nyc_taxi.db               "$REPO_ROOT/datasets/nyc-taxi/nyc_taxi.db"
fetch nyc-taxi/nyc_taxi_pipeline.db      "$REPO_ROOT/datasets/nyc-taxi/nyc_taxi_pipeline.db"
fetch fiction-retail/fiction-retail.db   "$REPO_ROOT/datasets/fiction-retail/fiction-retail.db"

echo
echo "== Verifying sha256 (see docs/VERSIONS.md) =="
check() {
    local file="$1" want="$2"
    local got
    got=$(shasum -a 256 "$file" | awk '{print $1}')
    if [ "$got" = "$want" ]; then
        echo "  ok   $(basename "$file")"
    else
        echo "  MISMATCH $(basename "$file"): got $got want $want" >&2
        return 1
    fi
}
check "$REPO_ROOT/datasets/healthcare/healthcare.db"          287a47c53216c2322074ae802976c6c7196e2e17dc77272c6a6bd38af34ec488
check "$REPO_ROOT/datasets/nyc-taxi/nyc_taxi.db"              fef53dcc005294046da76e0484f099e81d809a05dfa433fe3e38bc1b7f46537d
check "$REPO_ROOT/datasets/nyc-taxi/nyc_taxi_pipeline.db"     35573de0d1d05ffe4e03d3339385da3c69c986539e3d4ef24790a91a054c9871
check "$REPO_ROOT/datasets/fiction-retail/fiction-retail.db" 9f95373e46219e880ae54f995b6f2c2c439c3746e500e484fe3ab2bf9ac55754
echo "== All datasets verified =="
