"""RERA project, complaint, and builder endpoints."""


from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.data_hub import ReraComplaint, ReraProject
from app.schemas.data_hub import (
    BuilderListResponse,
    BuilderReputationResponse,
    ReraProjectListResponse,
    ReraProjectResponse,
)
from app.services.data_hub.utils import calculate_builder_score

from .helpers import _meta_from_table, _paginate

router = APIRouter()


@router.get("/rera-projects", response_model=ReraProjectListResponse)
async def list_rera_projects(
    status: str | None = Query(None),
    q: str | None = Query(None, description="Search project name or developer"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List RERA projects with optional status filter and text search."""
    filters = []
    if status:
        filters.append(ReraProject.status == status)
    if q:
        filters.append(
            ReraProject.project_name.ilike(f"%{q}%")
            | ReraProject.developer_name.ilike(f"%{q}%")
        )

    count_q = select(func.count()).select_from(ReraProject)
    data_q = select(ReraProject)
    if filters:
        count_q = count_q.where(and_(*filters))
        data_q = data_q.where(and_(*filters))

    total = (await db.execute(count_q)).scalar_one()
    offset = (page - 1) * limit
    rows = (await db.execute(data_q.offset(offset).limit(limit))).scalars().all()
    meta = await _meta_from_table(db, ReraProject)

    return {
        "items": rows,
        "meta": meta,
        **_paginate(total, page, limit),
    }


@router.get("/rera-projects/verify/{rera_number}")
async def verify_rera_project(rera_number: str, db: AsyncSession = Depends(get_db)):
    """Verify a RERA number — returns validity, status, and project name."""
    result = await db.execute(
        select(ReraProject).where(ReraProject.rera_number == rera_number)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return {"valid": False, "status": None, "project_name": None}
    return {"valid": True, "status": row.status, "project_name": row.project_name}


@router.get("/rera-projects/{rera_number}", response_model=ReraProjectResponse)
async def get_rera_project(rera_number: str, db: AsyncSession = Depends(get_db)):
    """Get a single RERA project by its RERA number."""
    result = await db.execute(
        select(ReraProject).where(ReraProject.rera_number == rera_number)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="RERA project not found")
    return row


# ---------------------------------------------------------------------------
# Builders (aggregated from RERA data)
# ---------------------------------------------------------------------------


@router.get("/builders", response_model=BuilderListResponse)
async def list_builders(
    q: str | None = Query(None, description="Search builder name"),
    order_by: str | None = Query(None, description="Set to 'score' to sort by builder score"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List builders aggregated from RERA projects, with complaint counts and scores."""
    # Build subquery: distinct developer slugs with name and project/complaint counts
    filters = []
    if q:
        filters.append(ReraProject.developer_name.ilike(f"%{q}%"))

    slug_q = (
        select(
            ReraProject.developer_slug.label("slug"),
            ReraProject.developer_name.label("builder_name"),
            func.count(ReraProject.id).label("total_projects"),
        )
        .where(ReraProject.developer_slug.isnot(None))
        .group_by(ReraProject.developer_slug, ReraProject.developer_name)
    )
    if filters:
        slug_q = slug_q.where(and_(*filters))

    # Fetch ALL builder rows (no pagination yet) so we can sort before slicing
    all_rows = (await db.execute(slug_q)).all()

    # Collect all builder slugs for bulk lookups
    all_slugs = [r.slug for r in all_rows if r.slug]

    # Bulk-fetch complaint counts
    complaint_counts: dict[str, int] = {}
    if all_slugs:
        complaint_count_rows = (
            await db.execute(
                select(ReraComplaint.builder_slug, func.count().label("cnt"))
                .where(ReraComplaint.builder_slug.in_(all_slugs))
                .group_by(ReraComplaint.builder_slug)
            )
        ).all()
        complaint_counts = {r.builder_slug: r.cnt for r in complaint_count_rows}

    # Build unsorted list with scores
    all_items: list[BuilderReputationResponse] = []
    for row in all_rows:
        builder_slug = row.slug
        builder_name = row.builder_name or builder_slug
        total_projects = row.total_projects
        total_complaints = complaint_counts.get(builder_slug, 0)
        score = calculate_builder_score(total_complaints, total_projects)
        all_items.append(
            BuilderReputationResponse(
                builder_name=builder_name,
                slug=builder_slug,
                total_projects=total_projects,
                total_complaints=total_complaints,
                builder_score=score,
                rera_projects=[],
                recent_complaints=[],
            )
        )

    # Sort before pagination
    if order_by == "score":
        all_items.sort(key=lambda x: x.builder_score, reverse=True)

    total = len(all_items)
    offset = (page - 1) * limit
    page_items = all_items[offset: offset + limit]

    # Bulk-fetch projects and recent complaints only for the current page slice
    page_slugs = [item.slug for item in page_items if item.slug]

    projects_by_slug: dict[str, list] = {s: [] for s in page_slugs}
    if page_slugs:
        proj_rows = (
            await db.execute(
                select(ReraProject).where(ReraProject.developer_slug.in_(page_slugs))
            )
        ).scalars().all()
        for p in proj_rows:
            if p.developer_slug in projects_by_slug:
                projects_by_slug[p.developer_slug].append(p)

    complaints_by_slug: dict[str, list] = {s: [] for s in page_slugs}
    if page_slugs:
        comp_rows = (
            await db.execute(
                select(ReraComplaint)
                .where(ReraComplaint.builder_slug.in_(page_slugs))
                .order_by(ReraComplaint.order_date.desc())
            )
        ).scalars().all()
        for c in comp_rows:
            if c.builder_slug in complaints_by_slug:
                complaints_by_slug[c.builder_slug].append(c)

    # Attach projects/complaints (cap at 5 each) to each page item
    items = []
    for item in page_items:
        item.rera_projects = projects_by_slug.get(item.slug, [])[:5]
        item.recent_complaints = complaints_by_slug.get(item.slug, [])[:5]
        items.append(item)

    meta = await _meta_from_table(db, ReraProject)
    return {
        "items": items,
        "meta": meta,
        **_paginate(total, page, limit),
    }


@router.get("/builders/{slug}", response_model=BuilderReputationResponse)
async def get_builder(slug: str, db: AsyncSession = Depends(get_db)):
    """Get builder reputation details by slug."""
    projects_result = await db.execute(
        select(ReraProject).where(ReraProject.developer_slug == slug)
    )
    projects = projects_result.scalars().all()
    if not projects:
        raise HTTPException(status_code=404, detail="Builder not found")

    total_projects = len(projects)
    builder_name = projects[0].developer_name or slug

    complaint_count_result = await db.execute(
        select(func.count()).select_from(ReraComplaint)
        .where(ReraComplaint.builder_slug == slug)
    )
    total_complaints = complaint_count_result.scalar_one()

    complaints_result = await db.execute(
        select(ReraComplaint)
        .where(ReraComplaint.builder_slug == slug)
        .order_by(ReraComplaint.order_date.desc())
        .limit(20)
    )
    complaints = complaints_result.scalars().all()

    score = calculate_builder_score(total_complaints, total_projects)

    return BuilderReputationResponse(
        builder_name=builder_name,
        slug=slug,
        total_projects=total_projects,
        total_complaints=total_complaints,
        builder_score=score,
        rera_projects=list(projects),
        recent_complaints=list(complaints),
    )
