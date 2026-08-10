"""DataHub 2026 — metadata-aware SQL generation agent (thin harness).

Pipeline per question: optional MCP metadata reads -> LLM writes SQL ->
execute on local mirror (SQLite) -> validate/diagnose -> retry up to N ->
(metadata mode) write-back an Insight document.

Modes:
  - metadata: LLM sees DataHub context (schema, lineage, tags, glossary, docs)
  - plain:    LLM sees only table/column names (no DataHub context)

A/B runner in evals/benchmark.py drives this with both modes on shared items.
"""
from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

LLM_URL = os.environ.get("LLM_URL", "http://127.0.0.1:4000/v1/chat/completions")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek.v3.2")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "45"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))

MIRRORS = {
    "healthcare": "datasets/healthcare/healthcare.db",
    "nyc-taxi-pipeline": "datasets/nyc-taxi/nyc_taxi_pipeline.db",
    "nyc-taxi": "datasets/nyc-taxi/nyc_taxi.db",
    "fiction-retail": "datasets/fiction-retail/fiction-retail.db",
}

# Substrings used to filter catalog tables to the current dataset. DataHub
# search("nyc-taxi-pipeline") returns unrelated sqlite datasets too (healthcare
# tables are in the same DataHub instance), which pollutes the metadata prompt.
DATASET_TABLE_HINTS = {
    "healthcare": ["billing", "patient", "demographics"],
    "nyc-taxi-pipeline": ["trip", "summary"],
    "nyc-taxi": ["trip", "summary"],
    "fiction-retail": ["order", "supplier", "inventory", "product", "customer", "review"],
}


@dataclass
class Result:
    question_id: str
    question: str
    mode: str
    sql: Optional[str] = None
    rows: Optional[list] = None
    error: Optional[str] = None
    attempts: int = 0
    used_metadata: bool = False
    write_back: Optional[str] = None
    trace: list = field(default_factory=list)


def llm_complete(system: str, user: str, model: Optional[str] = None) -> str:
    """Call the LLM with retry + backoff.

    An [OI]-compatible chat-completions endpoint (litellm or any OpenAI-style
    proxy). Retries up to 3 times on transient failures (empty completion,
    timeout, 429/5xx), with backoff + jitter between attempts.
    """
    models = [model or LLM_MODEL]
    last_err = "empty completion"
    for m in models:
        for attempt in range(1, 4):
            body = json.dumps({
                "model": m,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "max_tokens": 2000,
            }).encode()
            req = urllib.request.Request(LLM_URL, data=body, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as r:
                    data = json.load(r)
                content = data["choices"][0]["message"].get("content") or ""
                if content.strip():
                    return content
                last_err = "empty completion (transient)"
            except Exception as e:
                last_err = str(e)
            if attempt < 3:
                time.sleep(2 * attempt + random.random() * 1.5)  # backoff + jitter
    raise RuntimeError(f"LLM returned no content after retries ({models}): {last_err}")


def _extract_sql(text: str) -> Optional[str]:
    """Pull SQL out of an LLM response (code fence or bare statement)."""
    if not text:
        return None
    if "```" in text:
        parts = text.split("```")
        for chunk in reversed(parts):
            chunk = chunk.strip()
            if chunk.lower().startswith(("sql", "sqlite")):
                chunk = chunk.split("\n", 1)[1] if "\n" in chunk else chunk
            if chunk and any(k in chunk.upper() for k in ("SELECT", "WITH", "SHOW", "PRAGMA")):
                return chunk
    for line in text.splitlines():
        s = line.strip()
        if s.upper().startswith(("SELECT", "WITH", "SHOW", "PRAGMA")):
            return s.rstrip(";")
    return None


def execute_sql(db_path: str, sql: str) -> tuple[Optional[list], Optional[str]]:
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        con.close()
        return rows, None
    except Exception as e:
        try:
            con.close()
        except Exception:
            pass
        return None, str(e)


def _ensure_venv() -> None:
    """If datahub packages aren't importable, re-exec under .venv-datahub.

    The harness requires the datahub SDK + agent-context MCP kit, which live in
    the build's .venv-datahub (not system python). If we were started with the
    wrong interpreter, silently re-exec once with the venv python so metadata
    reads actually work. Guarded by _DATAHUB_VENV_OK to avoid re-exec loops.
    """
    try:
        import importlib.util
        if importlib.util.find_spec("datahub") is not None:
            return
    except Exception:
        return
    if os.environ.get("_DATAHUB_VENV_OK"):
        return
    venv_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".venv-datahub", "bin", "python")
    if os.path.exists(venv_py):
        os.environ["_DATAHUB_VENV_OK"] = "1"
        os.execv(venv_py, [venv_py] + sys.argv)



def _summarize_assertions(assertions: list) -> list:
    """Collapse a get_dataset_assertions payload into one line per assertion."""
    out = []
    for a in assertions or []:
        a_type = a.get("type") or "UNKNOWN"
        status = a.get("latestResultType") or "NO_RUN"
        desc = (a.get("description") or "").strip()
        line = f"{a_type} {status}"
        if desc:
            line += f" :: {desc[:160]}"
        out.append(line)
    return out

def build_context(dataset: str) -> dict:
    """Assemble DataHub context: schema fields + lineage + tags/glossary + docs."""
    _ensure_venv()
    ctx = {"dataset": dataset, "tables": {}, "lineage": [], "tags": {}, "glossary": {}, "docs": []}
    try:
        from datahub.sdk.main_client import DataHubClient
        from datahub_agent_context.context import DataHubContext
        from datahub_agent_context.mcp_tools import (
            search, get_entities, get_lineage, search_documents, get_dataset_assertions,
        )
    except Exception:
        return ctx
    try:
        client = DataHubClient(server=os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080"), token="")
        with DataHubContext(client):
            s = search(query=dataset, num_results=100)
            urns = []
            for r in s.get("searchResults", []):
                e = r.get("entity", {})
                if e.get("platform", {}).get("name") == "sqlite" and e.get("type") == "DATASET":
                    urns.append(e["urn"])
            if urns:
                ents = get_entities(urns=urns[:20])
                hints = DATASET_TABLE_HINTS.get(dataset, [])
                for ent in ents:
                    name = ent.get("name") or ""
                    if name.startswith("v_"):
                        continue
                    # Filter out tables that belong to a different dataset
                    # (DataHub search returns unrelated sqlite datasets too).
                    if hints and not any(h in name.lower() for h in hints):
                        continue
                    schema = ent.get("schemaMetadata") or {}
                    fields = []
                    for f in schema.get("fields", []):
                        fp = f.get("fieldPath")
                        if fp:
                            ndt = f.get("nativeDataType") or ""
                            fields.append(fp if not ndt else f"{fp}:{ndt}")
                    if fields:
                        ctx["tables"][name] = {
                            "fields": fields,
                            "tags": [t.get("tag", {}).get("properties", {}).get("name") for t in (ent.get("tags") or {}).get("tags", [])],
                            "glossary": [g.get("term", {}).get("properties", {}).get("name") for g in (ent.get("glossaryTerms") or {}).get("terms", [])],
                        }
            for name, urn in [(e.get("name"), e["urn"]) for e in ents if e.get("name")]:
                if name.startswith("v_"):
                    continue
                if hints and not any(h in name.lower() for h in hints):
                    continue
                try:
                    lin = get_lineage(urn=urn, upstream=True, max_hops=2)
                    ups = lin.get("upstreams", {}).get("searchResults", [])
                    if ups:
                        srcs = [u["entity"].get("name") for u in ups if u.get("entity", {}).get("name")]
                        ctx["lineage"].append({"table": name, "upstream": srcs})
                except Exception:
                    pass
                # Assertions: data-quality / freshness signals that DataHub native
                # deployments attach to datasets. Surface any failing assertions so the
                # metadata prompt can reason about planted data-quality / staleness bugs.
                try:
                    ar = get_dataset_assertions(urn=urn, count=10)
                    data = ar.get("data", {}) if isinstance(ar, dict) else {}
                    a_list = data.get("assertions", [])
                    if a_list and name in ctx["tables"]:
                        ctx["tables"][name]["assertions"] = _summarize_assertions(a_list)
                except Exception:
                    pass
            try:
                sd = search_documents(query=dataset, num_results=5)
                for r in sd.get("searchResults", []):
                    e = r.get("entity", {})
                    t = e.get("info", {}).get("title") or e.get("properties", {}).get("name")
                    txt = e.get("info", {}).get("description") or ""
                    if t:
                        ctx["docs"].append({"title": t, "snippet": txt[:500]})
            except Exception:
                pass
    except Exception as e:
        ctx["_error"] = str(e)[:200]
    return ctx


def context_to_prompt(ctx: dict) -> str:
    parts = []
    if ctx.get("tables"):
        parts.append("DATAHUB CATALOG (schema + metadata, format col:TYPE):")
        for name, info in ctx["tables"].items():
            tags = ", ".join(info["tags"]) if info["tags"] else "-"
            gloss = ", ".join(info["glossary"]) if info["glossary"] else "-"
            parts.append(f"  {name}  columns: {', '.join(info['fields'])}")
            parts.append(f"    tags: {tags} | glossary: {gloss}")
            if info.get("assertions"):
                for a in info["assertions"]:
                    parts.append(f"    assertion: {a}")
    if ctx.get("lineage"):
        parts.append("LINEAGE (upstream dependencies):")
        for l in ctx["lineage"]:
            parts.append(f"  {l['table']} <- {', '.join(l['upstream'])}")
        # Guidance: mart_* tables are the cleaned/analytics layer derived from raw_*/staging_*.
        # Prefer them for analysis questions unless the question explicitly targets raw data.
        marts = sorted({l["table"] for l in ctx["lineage"] if l["table"].startswith("mart_")})
        raws = sorted({u for l in ctx["lineage"] for u in l["upstream"] if u.startswith(("raw_", "staging_"))})
        if marts:
            parts.append("GUIDANCE: analytics-grade tables are " + ", ".join(marts))
            parts.append("   (they are derived/cleaned versions of " + ", ".join(raws) + "; prefer them for analysis)")
    if ctx.get("docs"):
        parts.append("DOCUMENTS:")
        for d in ctx["docs"]:
            parts.append(f"  - {d['title']}: {d['snippet']}")
    return "\n".join(parts)


SYSTEM_SQL = """You are a SQL analyst. Write a SINGLE SQLite query that answers the user's question. Return ONLY the SQL statement inside a ```sql code block. Do not explain. If the question needs multiple comparisons, use subqueries. Only use tables/columns that are listed. When a question compares two values with "vs" (e.g. "X vs Y"), return EXACTLY those two values as two columns, in the order requested, with no extra derived columns."""

SYSTEM_SQL_NO_META = SYSTEM_SQL + " You have no catalog; infer schema from the table names given."


def _mirror_tables(dataset: str) -> list:
    db_path = MIRRORS.get(dataset)
    if not db_path:
        return []
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        tabs = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'v_%' ORDER BY name")]
        con.close()
        return tabs
    except Exception:
        return []


def plan_sql(question: str, dataset: str, metadata: bool, context: dict) -> tuple[Optional[str], str]:
    if metadata:
        table_hint = ", ".join(sorted(context.get("tables", {}).keys())) or "unknown"
    else:
        table_hint = ", ".join(_mirror_tables(dataset)) or "unknown"
    if metadata:
        ctx_txt = context_to_prompt(context)
        user = f"DATASET: {dataset}\nTABLES AVAILABLE (in catalog): {table_hint}\n\n{ctx_txt}\n\nQUESTION: {question}\n\nWrite the SQLite query."
    else:
        user = f"DATASET: {dataset}\nTABLES (names only, unknown schema): {table_hint}\n\nQUESTION: {question}\n\nWrite the SQLite query. You may have to guess column names."
    try:
        out = llm_complete(SYSTEM_SQL if metadata else SYSTEM_SQL_NO_META, user)
    except Exception as e:
        return None, f"{user}\n\n[LLM ERROR: {e}]"
    return _extract_sql(out), user


def _extract_tables_from_sql(sql: str) -> list:
    """Return table names referenced in a SELECT (best-effort)."""
    if not sql:
        return []
    out = []
    for m in re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql):
        if m not in out:
            out.append(m)
    return out


def _resolve_table_urn(dataset: str, table: str) -> Optional[str]:
    """Resolve a table name to its DataHub dataset URN in the given dataset."""
    try:
        from datahub.sdk.main_client import DataHubClient
        from datahub_agent_context.context import DataHubContext
        from datahub_agent_context.mcp_tools import search
        client = DataHubClient(server=os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080"), token="")
        with DataHubContext(client):
            s = search(query=table, num_results=20)
            for r in s.get("searchResults", []):
                e = r.get("entity", {})
                urn = e.get("urn", "")
                name = e.get("name", "")
                if name == table and e.get("type") == "DATASET":
                    # prefer the exact table in this dataset's platform instance
                    return urn
        return None
    except Exception:
        return None


def annotate_table(dataset: str, table: str, note: str) -> Optional[str]:
    """Append a finding to a table's DataHub description (write back to the graph)."""
    if not table:
        return None
    try:
        from datahub.sdk.main_client import DataHubClient
        from datahub_agent_context.context import DataHubContext
        from datahub_agent_context.mcp_tools import update_description
        urn = _resolve_table_urn(dataset, table)
        if not urn:
            return f"ERR no urn for {table}"
        client = DataHubClient(server=os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080"), token="")
        with DataHubContext(client):
            r = update_description(entity_urn=urn, operation="append", description=note)
        return urn
    except Exception as e:
        return f"ERR {str(e)[:100]}"


def write_back(question: str, question_id: str, sql: str, rows: list, dataset: str) -> Optional[str]:
    """Persist an Insight doc AND annotate the primary analytics table in the graph."""
    results = []
    try:
        from datahub.sdk.main_client import DataHubClient
        from datahub_agent_context.context import DataHubContext
        from datahub_agent_context.mcp_tools import save_document
        client = DataHubClient(server=os.environ.get("DATAHUB_SERVER", "http://127.0.0.1:8080"), token="")
        with DataHubContext(client):
            content = f"Question: {question}\nSQL: {sql}\nResult rows: {len(rows)}"
            d = save_document(document_type="Insight", title=f"[eval] {question_id}: {question[:60]}", content=content)
            if isinstance(d, dict) and d.get("urn"):
                results.append(d["urn"])
    except Exception as e:
        results.append(f"ERR doc {str(e)[:80]}")

    # Graph write-back: annotate the primary analytics table referenced in the SQL.
    tables = _extract_tables_from_sql(sql)
    primary = next((t for t in tables if t.startswith("mart_")), tables[0] if tables else None)
    if primary:
        note = f"[eval {question_id}] {question[:80]} -> {len(rows)} row(s)"
        res = annotate_table(dataset, primary, note)
        if res:
            results.append(f"annotated:{res}")

    return "; ".join(results) if results else None


def answer(question_id: str, question: str, dataset: str, metadata: bool = True,
           max_retries: int = MAX_RETRIES, do_write_back: bool = True) -> Result:
    res = Result(question_id=question_id, question=question, mode="metadata" if metadata else "plain")
    db_path = MIRRORS.get(dataset)
    if not db_path or not os.path.exists(db_path):
        res.error = f"no mirror for {dataset}"
        return res

    context = build_context(dataset) if metadata else {}
    res.used_metadata = bool(metadata and context.get("tables"))

    try:
        sql, prompt = plan_sql(question, dataset, metadata, context)
    except Exception as e:
        res.error = f"plan failed: {str(e)[:200]}"
        return res
    res.trace.append({"step": "plan", "prompt_excerpt": prompt[:400]})
    if not sql:
        res.error = "no SQL produced"
        return res

    for attempt in range(1, max_retries + 1):
        res.attempts = attempt
        rows, err = execute_sql(db_path, sql)
        res.trace.append({"step": "exec", "attempt": attempt, "sql": sql, "err": err})
        if err is None:
            res.sql = sql
            res.rows = rows
            if metadata and do_write_back:
                res.write_back = write_back(question, question_id, sql, rows, dataset)
            return res
        if attempt < max_retries:
            fix_user = f"Your SQL failed with: {err}\nQuestion: {question}\nContext:\n{prompt}\n\nFix the SQL. Return only the corrected ```sql block."
            try:
                fix = llm_complete(SYSTEM_SQL, fix_user)
                sql = _extract_sql(fix) or sql
            except Exception as e:
                res.trace.append({"step": "fix", "attempt": attempt, "err": str(e)[:200]})
                # backend down; keep last sql, next attempt will fail too but
                # we preserve the error instead of crashing the runner
    res.error = "all attempts failed"
    return res


def run_batch(items: list[dict], metadata: bool = True, write_back: bool = True) -> list[Result]:
    return [answer(it["id"], it["q"], it["dataset"], metadata=metadata, do_write_back=write_back) for it in items]


if __name__ == "__main__":
    import sys
    import json as _j
    qid = sys.argv[1] if len(sys.argv) > 1 else "h1"
    b = _j.load(open("evals/benchmark.json"))
    it = next(q for q in b["questions"] if q["id"] == qid)
    mode = "plain" if (len(sys.argv) > 2 and sys.argv[2] == "plain") else "metadata"
    r = answer(it["id"], it["q"], it["dataset"], metadata=(mode == "metadata"), do_write_back=False)
    print(_j.dumps({
        "id": r.question_id, "mode": r.mode, "sql": r.sql, "error": r.error,
        "rows": r.rows, "attempts": r.attempts, "used_metadata": r.used_metadata,
    }, indent=2, default=str))
