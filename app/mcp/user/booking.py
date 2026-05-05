"""
Booking tools for User MCP Server.

Tools for short-stay property bookings:
- Create booking
- List bookings
- Get booking details
- Cancel booking
- Check availability
- Get pricing
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.mcp.apps_sdk import (
    AuthRequiredError,
    MCP_SECURITY_SCHEMES_MIXED,
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
    serialize_booking,
    serialize_property_basic,
)
from app.schemas.booking import BookingCreate
from app.services import booking as booking_svc

# Import the user MCP server instance to register tools
from app.mcp.user.server import user_mcp, _get_user, _require_auth

logger = get_logger(__name__)


# ============================================================================
# Booking Tools (for short-stay properties)
# ============================================================================


@user_mcp.tool(
    "bookings_create",
    annotations={
        "title": "Create Booking",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
)
async def bookings_create(
    property_id: int,
    check_in_date: str,
    check_out_date: str,
    guests: int = 1,
    special_requests: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new booking for a short-stay property.

    Args:
        property_id: ID of the property to book
        check_in_date: Check-in date (ISO-8601 format)
        check_out_date: Check-out date (ISO-8601 format)
        guests: Number of guests (default 1)
        special_requests: Any special requests
    """
    try:
        # Parse dates
        try:
            check_in = datetime.fromisoformat(check_in_date)
            check_out = datetime.fromisoformat(check_out_date)
        except ValueError:
            return invalid_input_response("Dates must be in ISO-8601 format")

        if check_out <= check_in:
            return invalid_input_response("Check-out date must be after check-in date")

        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="bookings_create",
                    message="Please log in to create a booking.",
                    scope="mcp:write",
                )

            # Check availability
            availability = await booking_svc.check_availability(
                db, property_id, check_in_date, check_out_date, guests
            )

            if not availability.get("available"):
                return MCPResponse.failure(
                    MCPErrorCode.BOOKING_CONFLICT,
                    availability.get("reason", "Property not available for these dates")
                ).model_dump()

            # Create booking
            booking_data = BookingCreate(
                property_id=property_id,
                check_in_date=check_in,
                check_out_date=check_out,
                guests=guests,
                special_requests=special_requests,
            )

            booking = await booking_svc.create_booking(db, user.id, booking_data)
            await db.commit()

            return MCPResponse.success({
                "message": "Booking created successfully",
                "booking": serialize_booking(booking),
            }).model_dump()
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in bookings.create: %s", e, exc_info=True)
        return internal_error_response(f"Failed to create booking: {str(e)}")


@user_mcp.tool(
    "bookings_list",
    annotations={
        "title": "List My Bookings",
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
)
async def bookings_list(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """List the current user's bookings.

    Args:
        page: Page number
        limit: Items per page
        status: Filter by status (pending, confirmed, checked_in, checked_out, cancelled, completed)
    """
    try:
        limit = min(max(1, limit), 100)

        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="bookings_list",
                    message="Please log in to view your bookings.",
                    scope="mcp:read",
                )

            data = await booking_svc.get_user_bookings(db, user.id)
            bookings = data.get("bookings", [])

            # Filter by status if provided
            if status:
                bookings = [b for b in bookings if b.booking_status == status]

            # Paginate
            start = (page - 1) * limit
            end = start + limit
            paginated = bookings[start:end]

            items = [serialize_booking(b) for b in paginated]

            return MCPResponse.success({
                "total": data.get("total", 0),
                "upcoming": data.get("upcoming", 0),
                "completed": data.get("completed", 0),
                "cancelled": data.get("cancelled", 0),
                "page": page,
                "limit": limit,
                "bookings": items,
            }).model_dump()
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in bookings.list: %s", e, exc_info=True)
        return internal_error_response(f"Failed to list bookings: {str(e)}")


@user_mcp.tool(
    "bookings_get",
    annotations={
        "title": "Get Booking Details",
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
)
async def bookings_get(
    booking_id: int,
) -> Dict[str, Any]:
    """Get details of a specific booking.

    Args:
        booking_id: ID of the booking
    """
    try:
        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="bookings_get",
                    message="Please log in to view this booking.",
                    scope="mcp:read",
                )

            booking = await booking_svc.get_booking(db, booking_id)

            if not booking:
                return not_found_response("Booking", booking_id)

            # Verify ownership
            if booking.user_id != user.id:
                return MCPResponse.failure(
                    MCPErrorCode.INSUFFICIENT_PERMISSIONS,
                    "You can only view your own bookings"
                ).model_dump()

            # Get property details
            from sqlalchemy import select
            from app.models.properties import Property
            prop_stmt = select(Property).where(Property.id == booking.property_id)
            prop_result = await db.execute(prop_stmt)
            prop = prop_result.scalar_one_or_none()

            property_data = serialize_property_basic(prop) if prop else None

            return MCPResponse.success({
                "booking": serialize_booking(booking),
                "property": property_data,
            }).model_dump()
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in bookings.get: %s", e, exc_info=True)
        return internal_error_response(f"Failed to get booking: {str(e)}")


@user_mcp.tool(
    "bookings_cancel",
    annotations={
        "title": "Cancel Booking",
        "readOnlyHint": False,
        "destructiveHint": True,
        "openWorldHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
)
async def bookings_cancel(
    booking_id: int,
    reason: str,
) -> Dict[str, Any]:
    """Cancel a booking.

    Args:
        booking_id: ID of the booking to cancel
        reason: Reason for cancellation
    """
    try:
        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="bookings_cancel",
                    message="Please log in to cancel a booking.",
                    scope="mcp:write",
                )

            booking = await booking_svc.get_booking(db, booking_id)

            if not booking:
                return not_found_response("Booking", booking_id)

            # Verify ownership
            if booking.user_id != user.id:
                return MCPResponse.failure(
                    MCPErrorCode.INSUFFICIENT_PERMISSIONS,
                    "You can only cancel your own bookings"
                ).model_dump()

            # Check if can be cancelled
            if booking.booking_status in ["cancelled", "completed", "checked_out"]:
                return MCPResponse.failure(
                    MCPErrorCode.OPERATION_FAILED,
                    f"Booking cannot be cancelled (status: {booking.booking_status})"
                ).model_dump()

            success = await booking_svc.cancel_booking(db, booking_id, reason)
            await db.commit()

            if success:
                return MCPResponse.success({
                    "message": "Booking cancelled successfully",
                    "booking_id": booking_id,
                }).model_dump()
            else:
                return internal_error_response("Failed to cancel booking")
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in bookings.cancel: %s", e, exc_info=True)
        return internal_error_response(f"Failed to cancel booking: {str(e)}")


@user_mcp.tool(
    "bookings_check_availability",
    annotations={
        "title": "Check Booking Availability",
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
)
async def bookings_check_availability(
    property_id: int,
    check_in_date: str,
    check_out_date: str,
    guests: int = 1,
) -> Dict[str, Any]:
    """Check if a property is available for booking.

    Args:
        property_id: ID of the property
        check_in_date: Check-in date (ISO-8601)
        check_out_date: Check-out date (ISO-8601)
        guests: Number of guests
    """
    try:
        async for db in get_db():
            result = await booking_svc.check_availability(
                db, property_id, check_in_date, check_out_date, guests
            )

            return MCPResponse.success({
                "available": result.get("available", False),
                "reason": result.get("reason"),
                "max_occupancy": result.get("max_occupancy"),
            }).model_dump()
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in bookings.check_availability: %s", e, exc_info=True)
        return internal_error_response(f"Failed to check availability: {str(e)}")


@user_mcp.tool(
    "bookings_get_pricing",
    annotations={
        "title": "Get Booking Pricing",
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
)
async def bookings_get_pricing(
    property_id: int,
    check_in_date: str,
    check_out_date: str,
    guests: int = 1,
) -> Dict[str, Any]:
    """Get pricing details for a potential booking.

    Args:
        property_id: ID of the property
        check_in_date: Check-in date (ISO-8601)
        check_out_date: Check-out date (ISO-8601)
        guests: Number of guests
    """
    try:
        try:
            check_in = datetime.fromisoformat(check_in_date)
            check_out = datetime.fromisoformat(check_out_date)
        except ValueError:
            return invalid_input_response("Dates must be in ISO-8601 format")

        async for db in get_db():
            pricing = await booking_svc.calculate_pricing(
                db, property_id, check_in, check_out, guests
            )

            if isinstance(pricing, dict) and pricing.get("error"):
                return MCPResponse.failure(
                    MCPErrorCode.INVALID_INPUT,
                    pricing["error"]
                ).model_dump()

            return MCPResponse.success({
                "pricing": pricing,
            }).model_dump()
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in bookings.get_pricing: %s", e, exc_info=True)
        return internal_error_response(f"Failed to get pricing: {str(e)}")
