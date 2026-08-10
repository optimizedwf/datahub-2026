"""Unit tests for the deterministic parts of the benchmark — no DataHub, no LLM.

Run:  python3 -m pytest tests/ -q
"""
import json
import os
import sys
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evals"))
import benchmark  # noqa: E402


def load_items():
    root = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(root, "evals", "benchmark.json")) as f:
        return json.load(f)["questions"]


# ── scoring (pure) ────────────────────────────────────────────────────────

def test_scalar_exact():
    assert benchmark.score_row({"kind": "count", "answer": 208675}, [(208675,)]) == 1.0

def test_scalar_float_tolerance():
    assert benchmark.score_row({"kind": "avg", "answer": 1500.0}, [(1500.02,)]) == 1.0
    assert benchmark.score_row({"kind": "avg", "answer": 1500.0}, [(1600.0,)]) == 0.0

def test_pair_join():
    assert benchmark.score_row({"kind": "pair", "answer": "208675 vs 250000"}, [(208675, 250000)]) == 1.0

def test_maxdate_tolerance():
    assert benchmark.score_row({"kind": "maxdate", "answer": "2016-06-30"}, [("2016-06-30 00:00:00",)]) == 1.0

def test_normalize_float():
    assert benchmark.normalize(5.0) == "5"


# ── benchmark surface (no LLM/DataHub needed) ─────────────────────────────

def test_benchmark_has_20_questions():
    items = load_items()
    assert len(items) == 20
    ids = [q["id"] for q in items]
    assert len(set(ids)) == 20
    assert all(q["dataset"] in ("healthcare", "nyc-taxi-pipeline", "fiction-retail") for q in items)

def test_all_questions_have_gold_answers():
    items = load_items()
    for q in items:
        assert q.get("answer") is not None, f"{q['id']} missing gold answer"
        assert q.get("kind") in ("count", "sum", "int", "avg", "pair", "maxdate", "top1", "date"), f"{q['id']} bad kind"

def test_repro_run_matches_frozen_scores():
    root = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(root, "evals", "repro_run.json")) as f:
        run = json.load(f)
    assert run["modes"]["metadata"]["accuracy"] == 0.95
    assert run["modes"]["plain"]["accuracy"] == 0.70
    assert run["paired_delta"] == 0.25


# ── dataset generators are importable / parse (no CSV needed) ─────────────

def test_dataset_scripts_exist():
    """Datasets are fetched by examples/fetch_datasets.sh (sha256-pinned);
    skip if not fetched yet so CI stays green on a lean checkout."""
    root = os.path.join(os.path.dirname(__file__), "..")
    if not os.path.isdir(os.path.join(root, "datasets")):
        pytest.skip("datasets/ not present — run examples/fetch_datasets.sh first")
    for ds in ("healthcare", "nyc-taxi", "fiction-retail"):
        for fn in ("create_db.py", "add_lineage.py", "add_metadata.py", "ingest.yaml"):
            if fn == "create_db.py" and ds == "fiction-retail":
                continue  # fiction-retail is fetched prebuilt (no source CSV in repo)
            assert os.path.exists(os.path.join(root, "datasets", ds, fn)), f"{ds}/{fn} missing"
