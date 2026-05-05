"""
Tenant tools for User MCP Server.

Tools for tenants to manage their rental experience:
- View current lease
- View rent payment history
- Create maintenance request
- List maintenance requests
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.mcp.apps_sdk import (
    AuthRequiredError,
    MCP_SECURITY_SCHEMES_MIXED,
    build_widget_tool_meta,
)
from app.mcp.errors import (
    MCPErrorCode,
    MCPResponse,
    internal_error_response,
    invalid_input_response,
    not_found_response,
)
from app.mcp.utils import (
    get_db,
    serialize_lease,
    serialize_maintenance_request,
)

# Import the user MCP server instance to register tools
from app.mcp.user.server import user_mcp, _get_user, _require_auth

logger = get_logger(__name__)

# ChatGPT widget linkage metadata
LEASE_DETAILS_META = build_widget_tool_meta(
    widget_uri="ui://widget/leasedetailswidget.html",
    invoking="Loading lease details...",
    invoked="Lease details loaded",
)

MAINTENANCE_WIDGET_META = build_widget_tool_meta(
    widget_uri="ui://widget/maintenancewidget.html",
    invoking="Loading maintenance requests...",
    invoked="Maintenance requests loaded",
)

TENANT_RENT_WIDGET_META = build_widget_tool_meta(
    widget_uri="ui://widget/tenantrentwidget.html",
    invoking="Loading your rent information...",
    invoked="Rent information loaded",
)


# ============================================================================
# Tenant Tools
# ============================================================================


@user_mcp.tool(
    "tenant_lease_current",
    annotations={
        "title": "View My Current Lease",
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
    meta=LEASE_DETAILS_META,
)
async def tenant_lease_current() -> Dict[str, Any]:
    """Get the current active lease for the tenant."""
    try:
        from sqlalchemy import select
        from app.models.pm_leases import Lease
        from app.models.enums import LeaseStatus

        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="tenant_lease_current",
                    message="Please log in to view your lease details.",
                    scope="mcp:read",
                )

            # Find active lease for this tenant
            stmt = select(Lease).where(
                Lease.tenant_user_id == user.id,
                Lease.status == LeaseStatus.active,
            ).order_by(Lease.created_at.desc()).limit(1)

            result = await db.execute(stmt)
            lease = result.scalar_one_or_none()

            if not lease:
                return {
                    "lease": None,
                    "message": "No active lease found.",
                }

            # Get property details
            from app.models.properties import Property
            prop_stmt = select(Property).where(Property.id == lease.property_id)
            prop_result = await db.execute(prop_stmt)
            prop = prop_result.scalar_one_or_none()

            property_data = None
            if prop:
                property_data = {
                    "id": prop.id,
                    "title": prop.title,
                    "locality": prop.locality,
                    "city": prop.city,
                    "full_address": getattr(prop, "full_address", None),
                    "main_image_url": getattr(prop, "main_image_url", None),
                }

            lease_data = serialize_lease(lease)
            lease_data["property"] = property_data

            return {
                "lease": lease_data,
            }
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in tenant.lease.current: %s", e, exc_info=True)
        return {
            "error": True,
            "message": "Failed to get current lease.",
        }


@user_mcp.tool(
    "tenant_rent_history",
    annotations={
        "title": "View My Rent Payment History",
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
    meta=TENANT_RENT_WIDGET_META,
)
async def tenant_rent_history(
    page: int = 1,
    limit: int = 20,
) -> Dict[str, Any]:
    """Get rent payment history for the tenant."""
    try:
        from sqlalchemy import select
        from app.models.pm_finance import RentPayment
        from app.models.pm_leases import Lease

        limit = min(max(1, limit), 100)

        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="tenant_rent_history",
                    message="Please log in to view your rent payment history.",
                    scope="mcp:read",
                )

            # Get all leases for this tenant
            lease_stmt = select(Lease.id).where(Lease.tenant_user_id == user.id)
            lease_result = await db.execute(lease_stmt)
            lease_ids = [r[0] for r in lease_result.all()]

            if not lease_ids:
                return {
                    "payments": [],
                    "total": 0,
                    "total_collected": 0,
                    "page": page,
                    "limit": limit,
                }

            # Get rent payments for these leases
            offset = (page - 1) * limit
            stmt = (
                select(RentPayment)
                .where(RentPayment.lease_id.in_(lease_ids))
                .order_by(RentPayment.paid_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await db.execute(stmt)
            payments = result.scalars().all()

            items = []
            for p in payments:
                items.append({
                    "id": p.id,
                    "rent_charge_id": p.charge_id,
                    "amount": float(p.amount_paid or 0),
                    "payment_date": p.paid_at.isoformat() if p.paid_at else None,
                    "payment_method": p.payment_method,
                    "transaction_id": p.reference,
                    "created_at": p.created_at.isoformat() if getattr(p, "created_at", None) else None,
                })

            total_collected = sum(p["amount"] for p in items)

            return {
                "payments": items,
                "total": len(items),
                "total_collected": total_collected,
                "page": page,
                "limit": limit,
            }
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in tenant.rent.history: %s", e, exc_info=True)
        return {
            "error": True,
            "message": "Failed to get rent history.",
        }


@user_mcp.tool(
    "tenant_maintenance_create",
    annotations={
        "title": "Create Maintenance Request",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
    meta=MAINTENANCE_WIDGET_META,
)
async def tenant_maintenance_create(
    property_id: int,
    title: str,
    description: str,
    category: str,
    priority: str = "medium",
) -> Dict[str, Any]:
    """Submit a maintenance request for a property you're renting.

    Args:
        property_id: ID of the property
        title: Short title for the issue
        description: Detailed description of the issue
        category: plumbing, electrical, hvac, appliance, structural, pest_control, cleaning, other
        priority: low, medium, high, urgent (default: medium)
    """
    try:
        from sqlalchemy import select
        from app.models.pm_leases import Lease
        from app.models.pm_maintenance import MaintenanceRequest
        from app.models.enums import (
            LeaseStatus,
            MaintenanceCategory,
            MaintenanceRequestStatus,
            MaintenanceUrgency,
        )

        # Validate category
        try:
            cat = MaintenanceCategory(category.lower())
        except ValueError:
            valid_categories = [c.value for c in MaintenanceCategory]
            return {
                "error": True,
                "message": f"Invalid category: {category}.",
                "valid_categories": valid_categories,
            }

        priority_norm = priority.lower().strip()
        urgency_map = {
            "low": MaintenanceUrgency.low,
            "medium": MaintenanceUrgency.medium,
            "high": MaintenanceUrgency.high,
            "urgent": MaintenanceUrgency.emergency,
            "emergency": MaintenanceUrgency.emergency,
        }
        urgency = urgency_map.get(priority_norm)
        if urgency is None:
            return {
                "error": True,
                "message": f"Invalid priority: {priority}.",
                "valid_priorities": ["low", "medium", "high", "urgent"],
            }

        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="tenant_maintenance_create",
                    message="Please log in to submit a maintenance request.",
                    scope="mcp:write",
                )

            # Verify tenant has active lease for this property
            lease_stmt = select(Lease).where(
                Lease.property_id == property_id,
                Lease.tenant_user_id == user.id,
                Lease.status == LeaseStatus.active,
            )
            lease_result = await db.execute(lease_stmt)
            lease = lease_result.scalar_one_or_none()

            if not lease:
                return {
                    "error": True,
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": "You do not have an active lease for this property.",
                }

            # Create maintenance request
            request = MaintenanceRequest(
                property_id=property_id,
                lease_id=lease.id,
                owner_id=lease.owner_id,
                tenant_user_id=user.id,
                title=title,
                description=description,
                category=cat,
                urgency=urgency,
                priority=priority_norm,
                request_status=MaintenanceRequestStatus.open,
            )
            db.add(request)
            await db.flush()
            await db.refresh(request)
            await db.commit()

            return {
                "request": serialize_maintenance_request(request),
            }
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in tenant.maintenance.create: %s", e, exc_info=True)
        return {
            "error": True,
            "message": "Failed to create maintenance request.",
        }


@user_mcp.tool(
    "tenant_maintenance_list",
    annotations={
        "title": "List My Maintenance Requests",
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
    meta=MAINTENANCE_WIDGET_META,
)
async def tenant_maintenance_list(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """List maintenance requests submitted by the tenant.

    Args:
        page: Page number (default 1)
        limit: Items per page (default 20)
        status: Filter by status (open, in_progress, scheduled, completed, cancelled)
    """
    try:
        from sqlalchemy import select
        from app.models.pm_maintenance import MaintenanceRequest
        from app.models.enums import MaintenanceRequestStatus, WorkOrderStatus

        limit = min(max(1, limit), 100)

        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="tenant_maintenance_list",
                    message="Please log in to view your maintenance requests.",
                    scope="mcp:read",
                )

            stmt = select(MaintenanceRequest).where(
                MaintenanceRequest.tenant_user_id == user.id
            )

            if status:
                status_norm = status.lower().strip()
                if status_norm == "open":
                    stmt = stmt.where(MaintenanceRequest.request_status == MaintenanceRequestStatus.open)
                elif status_norm == "in_progress":
                    stmt = stmt.where(MaintenanceRequest.work_order_status == WorkOrderStatus.in_progress)
                elif status_norm == "scheduled":
                    stmt = stmt.where(MaintenanceRequest.scheduled_for.is_not(None))
                elif status_norm == "completed":
                    stmt = stmt.where(MaintenanceRequest.completed_at.is_not(None))
                elif status_norm == "cancelled":
                    stmt = stmt.where(MaintenanceRequest.work_order_status == WorkOrderStatus.cancelled)
                else:
                    return {
                        "error": True,
                        "message": f"Invalid status: {status}.",
                        "valid_statuses": [
                            "open",
                            "in_progress",
                            "scheduled",
                            "completed",
                            "cancelled",
                        ],
                    }

            offset = (page - 1) * limit
            stmt = stmt.order_by(MaintenanceRequest.created_at.desc()).offset(offset).limit(limit)

            result = await db.execute(stmt)
            requests = result.scalars().all()

            items = [serialize_maintenance_request(r) for r in requests]

            total = len(items)
            return {
                "items": items,
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit if total else 0,
            }
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in tenant.maintenance.list: %s", e, exc_info=True)
        return {
            "error": True,
            "message": "Failed to list maintenance requests.",
        }
