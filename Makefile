# DataHub 2026 — Metadata-Aware Code Generation
.PHONY: help setup datasets ingest eval test lint video

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install pinned Python deps
	python3 -m pip install -r requirements.lock.txt

datasets: ## Fetch + verify seed databases (one command)
	bash examples/fetch_datasets.sh

ingest: ## Ingest all three datasets into DataHub (needs DATAHUB_SERVER)
	@for d in healthcare nyc-taxi fiction-retail; do \
		echo "== $$d =="; \
		(cd datasets/$$d && datahub ingest -c ingest.yaml) || exit 1; \
		(cd datasets/$$d && python3 add_lineage.py) || exit 1; \
		(cd datasets/$$d && python3 add_metadata.py) || exit 1; \
	done

eval: ## Full A/B + write-back → EVAL.json (needs LLM endpoint + DataHub)
	bash examples/eval.sh

test: ## Unit tests (no DataHub/LLM needed)
	python3 -m pytest tests/ -q

lint: ## Syntax check + test
	python3 -m py_compile src/agent.py evals/benchmark.py datasets/*/*.py
	python3 -m pytest tests/ -q

video: ## Render the demo video (see docs/DEMO_SCRIPT.md)
	python3 work/demo/build_3act.py
