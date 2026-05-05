from __future__ import annotations

from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone
import asyncio

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
import os
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.properties import PropertyAmenity, Amenity
from .compose import build_embedding_text, build_metadata
from .embedding_client import embed
from .store import (
    compute_text_hash,
    get_existing_hash,
    upsert_embedding,
    read_watermark,
    write_watermark,
    acquire_advisory_lock,
    release_advisory_lock,
)

logger = get_logger(__name__)


async def _fetch_changed_properties(db: AsyncSession, since: datetime | None, limit: int) -> List[Dict[str, Any]]:
    # Pull necessary columns for composing text/metadata
    cols = [
        "id", "title", "description", "property_type", "purpose", "status",
        "latitude", "longitude", "city", "state", "country", "pincode", "locality", "sub_locality", "landmark", "full_address",
        "area_type",
        "base_price", "price_per_sqft", "monthly_rent", "daily_rate", "security_deposit", "maintenance_charges",
        "area_sqft", "bedrooms", "bathrooms", "balconies", "parking_spaces", "floor_number", "total_floors", "age_of_property",
        "max_occupancy", "minimum_stay_days",
        "features", "main_image_url", "virtual_tour_url", "floor_plan_url", "video_tour_url", "tags", "search_keywords",
        "owner_id", "owner_name", "owner_contact", "builder_name",
        "is_available", "available_from", "calendar_data", "view_count", "like_count", "interest_count",
        "created_at", "updated_at"
    ]

    where = "WHERE TRUE"
    params: Dict[str, int | datetime] = {}
    if since is not None:
        where += " AND ((p.updated_at IS NOT NULL AND p.updated_at > :since) OR (p.updated_at IS NULL AND p.created_at > :since))"
        params["since"] = since

    q = text(
        f"SELECT {', '.join(['p.' + c for c in cols])} "
        "FROM public.properties p "
        f"{where} ORDER BY p.updated_at ASC NULLS LAST LIMIT :limit"
    )
    params["limit"] = limit
    res = await db.execute(q, params)
    rows = res.mappings().all()
    return [dict(r) for r in rows]


async def _fetch_amenities_and_tags(db: AsyncSession, property_ids: List[int]) -> Tuple[Dict[int, List[str]], Dict[int, List[str]]]:
    if not property_ids:
        return {}, {}
    # Amenities titles by property
    stmt = (
        select(PropertyAmenity.property_id, Amenity.title)
        .join(Amenity, PropertyAmenity.amenity_id == Amenity.id)
        .where(PropertyAmenity.property_id.in_(property_ids))
    )
    res = await db.execute(stmt)
    amap: Dict[int, List[str]] = {}
    for pid, title in res.all():
        amap.setdefault(pid, []).append(title)

    # Tags are stored in properties.tags JSON; fetch in outer query maps
    tmap: Dict[int, List[str]] = {}
    # We'll rely on the 'tags' column already fetched per property; this function only fills amenities
    return amap, tmap


async def _process_batch(db: AsyncSession, props: List[Dict[str, Any]]) -> None:
    if not props:
        return
    pids = [int(p["id"]) for p in props]
    amenity_map, _ = await _fetch_amenities_and_tags(db, pids)

    # Build embeddable texts and metadata
    texts: List[str] = []
    metas: List[Dict[str, Any]] = []
    hashes: List[str] = []
    need_embed_flags: List[bool] = []

    for p in props:
        pid = int(p["id"])
        amenities = amenity_map.get(pid, [])
        tags = p.get("tags") or []
        if isinstance(tags, list):
            tag_list = [str(t) for t in tags]
        else:
            tag_list = []
        text = build_embedding_text(p, amenities, tag_list)
        meta = build_metadata(p, amenities, tag_list)
        h = compute_text_hash(text)
        existing = await get_existing_hash(db, pid)
        need_embed = (existing != h)
        texts.append(text)
        metas.append(meta)
        hashes.append(h)
        need_embed_flags.append(need_embed)

    # Embed only where needed, preserve ordering
    texts_to_embed = [t for t, f in zip(texts, need_embed_flags) if f]
    vectors: List[List[float]] = []
    if texts_to_embed:
        try:
            vectors = await embed(texts_to_embed)
        except Exception as e:  # noqa: BLE001
            # Propagate failures so the batch is retried and the watermark
            # is not advanced while embeddings are stale.
            logger.error("Embedding API failed for batch of %s: %s", len(texts_to_embed), e)
            raise
        if not vectors or len(vectors) != len(texts_to_embed):
            # Defensive: avoid marking hashes as up-to-date if the embedding
            # service returns an unexpected number of vectors.
            logger.error(
                "Embedding API returned %d vectors for %d inputs; aborting batch",
                len(vectors),
                len(texts_to_embed),
            )
            raise RuntimeError("Embedding API returned inconsistent vector count")

    # Iterate and upsert
    vec_iter = iter(vectors)
    for p, meta, h, need_embed in zip(props, metas, hashes, need_embed_flags):
        pid = int(p["id"])
        emb = next(vec_iter) if need_embed and vectors else None
        await upsert_embedding(db, pid, emb, meta, h)


async def run_property_vector_sync() -> Dict[str, int | bool]:
    """Entry point to run one incremental sync pass.

    Returns stats for logging/metrics.
    """
    stats = {"scanned": 0, "embedded": 0, "updated": 0}
    async with AsyncSessionLocal() as db:
        # Acquire lock to avoid concurrent workers duplicating work
        force = os.getenv("VECTOR_SYNC_FORCE", "").lower() in ("1", "true", "yes")
        got_lock = True
        if not force:
            got_lock = await acquire_advisory_lock(db)
            if not got_lock:
                return {"skipped": True}
        try:
            watermark = await read_watermark(db)
            batch_size = int(settings.VECTOR_SYNC_BATCH_SIZE)

            changed = await _fetch_changed_properties(db, watermark, batch_size)
            if not changed:
                return {"scanned": 0, "embedded": 0, "updated": 0}

            stats["scanned"] = len(changed)
            await _process_batch(db, changed)
            await db.commit()

            # Count embeddings done in this batch
            for p in changed:
                pid = int(p["id"])
                existing = await get_existing_hash(db, pid)
                # We cannot easily deduce how many were embedded now; treat all as updated
                stats["updated"] += 1

            # Advance watermark to max updated_at in batch
            new_wm = max([p.get("updated_at") or p.get("created_at") for p in changed])
            if isinstance(new_wm, datetime):
                await write_watermark(db, new_wm)
                await db.commit()
            else:
                # Fallback: now()
                await write_watermark(db, datetime.now(timezone.utc))
                await db.commit()
        finally:
            if not force:
                await release_advisory_lock(db)
    return stats
