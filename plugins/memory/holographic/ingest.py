"""LanceDB embedding ingest for Mercury / Cortex.

Builds a local vector index over:
  - Schaefer-400 / Brainnetome region descriptions (from D:/cortex/scripts/regions.py)
  - Cortex training-data assistant answers (from D:/cortex/data/cortex_train_v2.jsonl)
  - Mercury session memories (from C:/Users/soumi/.mercury/state.db, if present)
  - Optional offline neuroscience reference dumps under D:/cortex/data/refs/

Embedder: Ollama embeddinggemma:300m at localhost:11434 (already pulled).
Output:   C:/Users/soumi/.mercury/vectors/cortex.lance/

Usage:
  python -m plugins.memory.holographic.ingest                  # full re-ingest
  python -m plugins.memory.holographic.ingest --source regions # one source only
  python -m plugins.memory.holographic.ingest --query "face area"  # smoke-test retrieval
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterator

# ---- paths customized for this box ----
MERCURY_HOME    = Path(os.environ.get("MERCURY_HOME", r"C:/Users/soumi/.mercury"))
VECTOR_DIR      = MERCURY_HOME / "vectors"
TABLE_NAME      = "cortex"
CORTEX_REPO     = Path(r"D:/cortex")
TRAIN_JSONL_V1  = CORTEX_REPO / "data" / "cortex_train.jsonl"
TRAIN_JSONL_V2  = CORTEX_REPO / "data" / "cortex_train_v2.jsonl"
REFS_DIR        = CORTEX_REPO / "data" / "refs"
MERCURY_STATE   = MERCURY_HOME / "state.db"
OLLAMA_URL      = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL     = "embeddinggemma:300m"
EMBED_DIM       = 768  # embeddinggemma 300m output

# ---------------------------------------------------------------------------
# Embedding (Ollama)
# ---------------------------------------------------------------------------

def embed_one(text: str) -> list[float]:
    import urllib.request

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embeddings",
        data=json.dumps({"model": EMBED_MODEL, "prompt": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))["embedding"]


def embed_batch(texts: list[str]) -> list[list[float]]:
    # Ollama doesn't have a real batch endpoint — sequential is fine for our scale.
    return [embed_one(t) for t in texts]


# ---------------------------------------------------------------------------
# Source iterators — each yields {id, text, source, metadata}
# ---------------------------------------------------------------------------

def source_regions() -> Iterator[dict]:
    """Atlas region narratives — one chunk per region per facet."""
    sys.path.insert(0, str(CORTEX_REPO))
    from scripts.regions import REGIONS  # type: ignore

    for region in REGIONS:
        meta = {
            "region": region.name,
            "abbr": region.abbreviation,
            "network": region.network.value,
            "brodmann": region.brodmann,
        }
        # one chunk per facet keeps each embedding focused
        if region.functions:
            yield {
                "id": f"region::{region.abbreviation}::functions",
                "text": (
                    f"{region.name} ({region.abbreviation}) — {region.network.value} network, "
                    f"Brodmann {region.brodmann}. Functions: " + "; ".join(region.functions)
                ),
                "source": "atlas:functions",
                "metadata": meta,
            }
        if region.stimuli:
            yield {
                "id": f"region::{region.abbreviation}::stimuli",
                "text": (
                    f"{region.name} ({region.abbreviation}) reliably activates to: "
                    + "; ".join(region.stimuli)
                ),
                "source": "atlas:stimuli",
                "metadata": meta,
            }
        if region.clinical:
            yield {
                "id": f"region::{region.abbreviation}::clinical",
                "text": (
                    f"Clinical notes on {region.name} ({region.abbreviation}): "
                    + "; ".join(region.clinical)
                ),
                "source": "atlas:clinical",
                "metadata": meta,
            }


def source_training(jsonl_path: Path) -> Iterator[dict]:
    """Each assistant answer becomes a retrievable narration."""
    if not jsonl_path.exists():
        return
    for i, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            ex = json.loads(line)
        except json.JSONDecodeError:
            continue
        # find the assistant turn
        ans = next(
            (m["value"] for m in ex.get("conversations", []) if m.get("from") == "assistant"),
            "",
        )
        if not ans or len(ans) < 80:
            continue
        yield {
            "id": f"train::{ex.get('id', f'idx{i}')}",
            "text": ans,
            "source": f"training:{jsonl_path.stem}",
            "metadata": ex.get("metadata", {}),
        }


def source_mercury_sessions() -> Iterator[dict]:
    """Past Hermes/Mercury session memories (if SQLite store present)."""
    if not MERCURY_STATE.exists():
        return
    try:
        conn = sqlite3.connect(f"file:{MERCURY_STATE}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur]
    except sqlite3.Error:
        return
    finally:
        conn.close()

    # Mercury's table layout varies across versions; do a best-effort pass over
    # anything that looks like a messages/sessions table.
    candidates = [t for t in tables if any(k in t.lower() for k in ("message", "session", "memory"))]
    if not candidates:
        return
    conn = sqlite3.connect(f"file:{MERCURY_STATE}?mode=ro", uri=True, timeout=5)
    try:
        for tbl in candidates:
            try:
                cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{tbl}")')]
            except sqlite3.Error:
                continue
            text_cols = [c for c in cols if c.lower() in ("content", "text", "body", "message")]
            id_cols   = [c for c in cols if c.lower() in ("id", "rowid", "uuid")]
            if not text_cols:
                continue
            id_col = id_cols[0] if id_cols else "rowid"
            try:
                rows = conn.execute(f'SELECT {id_col}, {text_cols[0]} FROM "{tbl}" LIMIT 5000')
            except sqlite3.Error:
                continue
            for rid, txt in rows:
                if not txt or len(str(txt)) < 60:
                    continue
                yield {
                    "id": f"mercury::{tbl}::{rid}",
                    "text": str(txt)[:4000],  # cap chunk size
                    "source": f"mercury:{tbl}",
                    "metadata": {},
                }
    finally:
        conn.close()


def source_refs() -> Iterator[dict]:
    """Optional offline reference docs under D:/cortex/data/refs/*.txt"""
    if not REFS_DIR.exists():
        return
    for p in REFS_DIR.glob("**/*.txt"):
        text = p.read_text(encoding="utf-8", errors="replace")
        # crude paragraph chunker — split on blank lines, keep chunks ~600-1200 chars
        buf, idx = [], 0
        for para in text.split("\n\n"):
            para = para.strip()
            if not para:
                continue
            buf.append(para)
            joined = "\n\n".join(buf)
            if len(joined) >= 600:
                yield {
                    "id": f"ref::{p.stem}::{idx:04d}",
                    "text": joined,
                    "source": f"ref:{p.stem}",
                    "metadata": {"path": str(p)},
                }
                buf, idx = [], idx + 1
        if buf:
            yield {
                "id": f"ref::{p.stem}::{idx:04d}",
                "text": "\n\n".join(buf),
                "source": f"ref:{p.stem}",
                "metadata": {"path": str(p)},
            }


SOURCES = {
    "regions":  source_regions,
    "training": lambda: source_training(TRAIN_JSONL_V2 if TRAIN_JSONL_V2.exists() else TRAIN_JSONL_V1),
    "mercury":  source_mercury_sessions,
    "refs":     source_refs,
}


# ---------------------------------------------------------------------------
# LanceDB writer
# ---------------------------------------------------------------------------

def open_table():
    import lancedb  # imported lazily

    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(VECTOR_DIR))
    if TABLE_NAME in db.table_names():
        return db, db.open_table(TABLE_NAME)
    # Create with a tiny seed so schema is fixed
    seed = [{
        "id": "__seed__",
        "text": "seed",
        "source": "seed",
        "metadata_json": "{}",
        "vector": [0.0] * EMBED_DIM,
    }]
    tbl = db.create_table(TABLE_NAME, data=seed)
    tbl.delete("id = '__seed__'")
    return db, tbl


def ingest(sources: list[str], dry_run: bool = False) -> dict:
    db, tbl = open_table()
    existing = set()
    try:
        for r in tbl.search().select(["id"]).limit(10**7).to_list():
            existing.add(r["id"])
    except Exception:
        pass

    counts = {s: 0 for s in sources}
    skipped = 0
    batch: list[dict] = []
    BATCH_SIZE = 32

    def flush():
        nonlocal batch
        if not batch:
            return
        texts = [b["text"] for b in batch]
        if not dry_run:
            vecs = embed_batch(texts)
            rows = [{
                "id":   b["id"],
                "text": b["text"][:8000],
                "source": b["source"],
                "metadata_json": json.dumps(b.get("metadata", {}), ensure_ascii=False),
                "vector": v,
            } for b, v in zip(batch, vecs)]
            tbl.add(rows)
        batch = []

    started = time.time()
    for src in sources:
        if src not in SOURCES:
            print(f"[ingest] unknown source: {src}", file=sys.stderr)
            continue
        for item in SOURCES[src]():
            if item["id"] in existing:
                skipped += 1
                continue
            batch.append(item)
            counts[src] += 1
            if len(batch) >= BATCH_SIZE:
                flush()
                elapsed = time.time() - started
                total = sum(counts.values())
                print(f"[ingest] {total} new  ({skipped} skipped)  {elapsed:.1f}s")
    flush()
    return {"counts": counts, "skipped": skipped, "total_new": sum(counts.values())}


# ---------------------------------------------------------------------------
# Smoke-test retrieval
# ---------------------------------------------------------------------------

def query(text: str, k: int = 5) -> list[dict]:
    _, tbl = open_table()
    vec = embed_one(text)
    return tbl.search(vec).limit(k).to_list()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> int:
    ap = argparse.ArgumentParser(description="Mercury LanceDB embedding ingest")
    ap.add_argument("--source", action="append", choices=list(SOURCES) + ["all"], default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--query", default=None, help="run a retrieval smoke-test instead of ingesting")
    args = ap.parse_args()

    if args.query:
        results = query(args.query, k=5)
        for r in results:
            score = r.get("_distance", "n/a")
            print(f"\n[{score}] {r['source']}  id={r['id']}")
            print((r["text"][:300] + "...") if len(r["text"]) > 300 else r["text"])
        return 0

    if not args.source or "all" in args.source:
        sources = list(SOURCES.keys())
    else:
        sources = args.source

    print(f"[ingest] sources={sources}  dry_run={args.dry_run}")
    print(f"[ingest] vectors -> {VECTOR_DIR}")
    print(f"[ingest] embed model: {EMBED_MODEL}  ({EMBED_DIM}d)")
    result = ingest(sources, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
