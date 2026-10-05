"""Seed the food_embedding table with BGE-M3 vectors for all ACTIVE foods.

Idempotent: upserts on canonical_food_id, safe to re-run after adding foods
or swapping the embedding model. Run while the inference service is up:

    # local docker inference container
    $env:INFERENCE_URL = "http://localhost:8000"
    python scripts/seed_food_embeddings.py

    # Railway UAT (start Inference-UAT first)
    $env:INFERENCE_URL = "https://<temporary-domain>"   # or via API-UAT integration

Env: DATABASE_URL (postgresql:// or postgresql+asyncpg://), INFERENCE_URL.
Options: --batch N (default 32), --only-missing, --limit N (smoke test).
"""
from __future__ import annotations

import argparse
import asyncio
import os

import asyncpg
import httpx

EMBED_MODEL = "BAAI/bge-m3"
BATCH = 32


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip().strip('"').strip("'")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if not url:
        raise SystemExit("DATABASE_URL is not set.")
    return url


def _inference_url() -> str:
    url = os.environ.get("INFERENCE_URL", "").strip().rstrip("/")
    if not url:
        raise SystemExit("INFERENCE_URL is not set.")
    return url


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=int, default=BATCH)
    parser.add_argument("--only-missing", action="store_true", help="skip foods that already have an embedding")
    parser.add_argument("--limit", type=int, default=None, help="process at most N foods (smoke test)")
    args = parser.parse_args()

    conn = await asyncpg.connect(_database_url())
    try:
        query = (
            "select f.canonical_food_id, f.canonical_name, f.canonical_name_ms "
            "from canonical_food f "
            "where f.status = 'ACTIVE'"
        )
        if args.only_missing:
            query += " and not exists (select 1 from food_embedding e where e.canonical_food_id = f.canonical_food_id)"
        query += " order by f.canonical_food_id"
        if args.limit:
            query += f" limit {int(args.limit)}"
        rows = await conn.fetch(query)
        print(f"embedding {len(rows)} foods via {_inference_url()} ...")

        upserted = 0
        async with httpx.AsyncClient(timeout=120.0) as client:
            for start in range(0, len(rows), args.batch):
                chunk = rows[start : start + args.batch]
                texts = [
                    # BGE-M3 is multilingual: combining the English canonical name
                    # with the Malay name matches both receipt OCR (Malay) and
                    # recipe text (English) queries.
                    f"{r['canonical_name']} {r['canonical_name_ms'] or ''}".strip()
                    for r in chunk
                ]
                resp = await client.post(
                    f"{_inference_url()}/embed", json={"texts": texts}
                )
                resp.raise_for_status()
                vectors = resp.json()["vectors"]
                for row, vector in zip(chunk, vectors):
                    await conn.execute(
                        """
                        insert into food_embedding (canonical_food_id, embedding, model, dim)
                        values ($1, $2, $3, $4)
                        on conflict (canonical_food_id) do update
                        set embedding = excluded.embedding,
                            model = excluded.model,
                            dim = excluded.dim,
                            updated_at = now()
                        """,
                        row["canonical_food_id"],
                        [float(v) for v in vector],
                        EMBED_MODEL,
                        len(vector),
                    )
                    upserted += 1
                print(f"  {upserted}/{len(rows)} done")
        print(f"OK: {upserted} embeddings upserted (model={EMBED_MODEL}).")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
