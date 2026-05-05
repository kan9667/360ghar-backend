"""
Owner tools for User MCP Server.

Tools for property owners to manage their properties:
- List owned properties
- Create property listing
- Get property details
- Update property
- Toggle availability
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.exceptions import (
    InsufficientPermissionsError,
    PropertyNotFoundException,
)
from app.core.logging import get_logger
from app.models.enums import PropertyType, PropertyPurpose
from app.mcp.apps_sdk import (
    AuthRequiredError,
    MCP_SECURITY_SCHEMES_MIXED,
    build_widget_tool_meta,
    raise_auth_required,
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
    serialize_property_basic,
    serialize_property_full,
    serialize_lease,
)
from app.schemas.property import PropertyCreate
from app.services.pm_properties import (
    create_managed_property,
    list_managed_properties,
    get_managed_property_detail,
    update_managed_property,
)
from app.services.pm_authz import assert_can_access_property

# Import the user MCP server instance to register tools
from app.mcp.user.server import user_mcp, _get_user, _require_auth

logger = get_logger(__name__)

# ChatGPT widget linkage metadata
OWNER_DASHBOARD_META = build_widget_tool_meta(
    widget_uri="ui://widget/ownerdashboardwidget.html",
    invoking="Loading your properties...",
    invoked="Properties loaded",
)


# ============================================================================
# Owner Property Tools
# ============================================================================


@user_mcp.tool(
    "owner_properties_list",
    annotations={
        "title": "List My Properties",
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
    meta=OWNER_DASHBOARD_META,
)
async def owner_properties_list(
    page: int = 1,
    limit: int = 20,
    occupancy: Optional[str] = None,
    q: Optional[str] = None,
) -> Dict[str, Any]:
    """List all properties owned by the current user.

    Args:
        page: Page number (default 1)
        limit: Items per page (default 20, max 100)
        occupancy: Filter by 'occupied' or 'vacant'
        q: Search query for title/address
    """
    try:
        limit = min(max(1, limit), 100)
        async for db in get_db():
            user = await _get_user(db)
            if not user:
                raise_auth_required(
                    message="Please log in to view your property dashboard.",
                    error_description="Authentication required",
                    scope="mcp:read",
                    structured_content={
                        "requires_auth": True,
                        "action": "owner_properties_list",
                    },
                )

            # Import here to get the User schema
            from app.schemas.user import User as UserSchema
            from sqlalchemy import select

            from app.models.enums import LeaseStatus
            from app.models.pm_leases import Lease
            from app.models.users import User as UserModel
            user_schema = UserSchema.model_validate(user)

            properties = await list_managed_properties(
                db,
                actor=user_schema,
                owner_id=user.id,
                occupancy=occupancy,
                q=q,
                limit=limit,
                offset=(page - 1) * limit,
            )

            property_ids = [p.id for p in properties]
            active_lease_tenants: dict[int, str | None] = {}
            if property_ids:
                lease_stmt = (
                    select(Lease.property_id, UserModel.full_name)
                    .join(UserModel, UserModel.id == Lease.tenant_user_id)
                    .where(Lease.property_id.in_(property_ids), Lease.status == LeaseStatus.active)
                )
                lease_result = await db.execute(lease_stmt)
                for prop_id, tenant_name in lease_result.all():
                    if prop_id not in active_lease_tenants:
                        active_lease_tenants[prop_id] = tenant_name

            items: list[dict[str, Any]] = []
            for prop in properties:
                item = serialize_property_basic(prop)
                tenant_name = active_lease_tenants.get(prop.id)
                item["has_active_lease"] = prop.id in active_lease_tenants
                if tenant_name:
                    item["tenant_name"] = tenant_name
                items.append(item)

            occupied = sum(1 for p in items if p.get("has_active_lease"))
            vacant = len(items) - occupied
            total_monthly_income = sum(
                float(p.get("monthly_rent") or 0) for p in items if p.get("has_active_lease")
            )

            return {
                "items": items,
                "total": len(items),
                "page": page,
                "limit": limit,
                "stats": {
                    "total_properties": len(items),
                    "occupied": occupied,
                    "vacant": vacant,
                    "total_monthly_income": total_monthly_income,
                },
            }
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in owner.properties.list: %s", e, exc_info=True)
        return {
            "error": True,
            "message": "Failed to list properties.",
        }


@user_mcp.tool(
    "owner_properties_create",
    annotations={
        "title": "Create Property Listing",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
)
async def owner_properties_create(
    title: str,
    property_type: str,
    purpose: str,
    full_address: str,
    city: str,
    locality: str,
    latitude: float,
    longitude: float,
    base_price: float,
    description: Optional[str] = None,
    sub_locality: Optional[str] = None,
    pincode: Optional[str] = None,
    state: Optional[str] = None,
    monthly_rent: Optional[float] = None,
    daily_rate: Optional[float] = None,
    security_deposit: Optional[float] = None,
    maintenance_charges: Optional[float] = None,
    area_sqft: Optional[float] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
    balconies: Optional[int] = None,
    parking_spaces: Optional[int] = None,
    floor_number: Optional[int] = None,
    total_floors: Optional[int] = None,
    max_occupancy: Optional[int] = None,
    minimum_stay_days: Optional[int] = None,
    main_image_url: Optional[str] = None,
    virtual_tour_url: Optional[str] = None,
    amenity_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Create a new property listing for the current user.

    Args:
        title: Property title (5-200 chars)
        property_type: house, apartment, builder_floor, room
        purpose: buy, rent, short_stay
        full_address: Complete address
        city: City name
        locality: Locality/area name
        latitude: GPS latitude (-90 to 90)
        longitude: GPS longitude (-180 to 180)
        base_price: Base price for sale or display
        ... (other optional fields)
    """
    try:
        # Validate property_type
        try:
            prop_type = PropertyType(property_type.lower())
        except ValueError:
            return invalid_input_response(f"Invalid property_type: {property_type}")

        # Validate purpose
        try:
            prop_purpose = PropertyPurpose(purpose.lower())
        except ValueError:
            return invalid_input_response(f"Invalid purpose: {purpose}")

        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="owner_properties_create",
                    message="Please log in to create a property listing.",
                    scope="mcp:write",
                )

            from app.schemas.user import User as UserSchema
            user_schema = UserSchema.model_validate(user)

            # Build property data
            property_data = PropertyCreate(
                title=title,
                description=description,
                property_type=prop_type,
                purpose=prop_purpose,
                full_address=full_address,
                city=city,
                locality=locality,
                sub_locality=sub_locality,
                pincode=pincode,
                state=state,
                latitude=latitude,
                longitude=longitude,
                base_price=base_price,
                monthly_rent=monthly_rent,
                daily_rate=daily_rate,
                security_deposit=security_deposit,
                maintenance_charges=maintenance_charges,
                area_sqft=area_sqft,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                balconies=balconies,
                parking_spaces=parking_spaces,
                floor_number=floor_number,
                total_floors=total_floors,
                max_occupancy=max_occupancy,
                minimum_stay_days=minimum_stay_days,
                main_image_url=main_image_url,
                virtual_tour_url=virtual_tour_url,
            )

            prop = await create_managed_property(
                db,
                actor=user_schema,
                owner_id=user.id,
                property_data=property_data,
            )

            # Handle amenities if provided
            if amenity_ids:
                from app.models.properties import PropertyAmenity
                for amenity_id in amenity_ids:
                    property_amenity = PropertyAmenity(
                        property_id=prop.id,
                        amenity_id=amenity_id
                    )
                    db.add(property_amenity)

            await db.commit()

            return MCPResponse.success({
                "message": "Property created successfully",
                "property": serialize_property_basic(prop),
            }).model_dump()
    except ValueError as e:
        return invalid_input_response(str(e))
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in owner.properties.create: %s", e, exc_info=True)
        return internal_error_response(f"Failed to create property: {str(e)}")


@user_mcp.tool(
    "owner_properties_get",
    annotations={
        "title": "Get Property Details (Owner)",
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
)
async def owner_properties_get(
    property_id: int,
) -> Dict[str, Any]:
    """Get detailed information about one of your properties.

    Args:
        property_id: ID of the property to retrieve
    """
    try:
        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="owner_properties_get",
                    message="Please log in to view this property.",
                    scope="mcp:read",
                )

            from app.schemas.user import User as UserSchema
            user_schema = UserSchema.model_validate(user)

            try:
                result = await get_managed_property_detail(
                    db,
                    actor=user_schema,
                    property_id=property_id,
                )
            except PropertyNotFoundException:
                return not_found_response("Property", property_id)
            except InsufficientPermissionsError:
                return MCPResponse.failure(
                    MCPErrorCode.INSUFFICIENT_PERMISSIONS,
                    "You do not have access to this property"
                ).model_dump()

            prop = result["property"]
            active_lease = result.get("active_lease")

            property_data = serialize_property_full(prop)

            lease_data = None
            if active_lease:
                lease_data = serialize_lease(active_lease)

            return MCPResponse.success({
                "property": property_data,
                "active_lease": lease_data,
            }).model_dump()
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in owner.properties.get: %s", e, exc_info=True)
        return internal_error_response(f"Failed to get property: {str(e)}")


@user_mcp.tool(
    "owner_properties_update",
    annotations={
        "title": "Update Property Listing",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
)
async def owner_properties_update(
    property_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    base_price: Optional[float] = None,
    monthly_rent: Optional[float] = None,
    daily_rate: Optional[float] = None,
    is_available: Optional[bool] = None,
    max_occupancy: Optional[int] = None,
    main_image_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Update one of your properties.

    Args:
        property_id: ID of the property to update
        ... (all other fields are optional for partial update)
    """
    try:
        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="owner_properties_update",
                    message="Please log in to update a property listing.",
                    scope="mcp:write",
                )

            from app.schemas.user import User as UserSchema
            user_schema = UserSchema.model_validate(user)

            try:
                prop = await assert_can_access_property(
                    db, actor=user_schema, property_id=property_id
                )
            except PropertyNotFoundException:
                return not_found_response("Property", property_id)
            except InsufficientPermissionsError:
                return MCPResponse.failure(
                    MCPErrorCode.INSUFFICIENT_PERMISSIONS,
                    "You do not have access to this property"
                ).model_dump()

            # Apply updates
            if title is not None:
                prop.title = title
            if description is not None:
                prop.description = description
            if base_price is not None:
                prop.base_price = base_price
            if monthly_rent is not None:
                prop.monthly_rent = monthly_rent
            if daily_rate is not None:
                prop.daily_rate = daily_rate
            if is_available is not None:
                prop.is_available = is_available
            if max_occupancy is not None:
                prop.max_occupancy = max_occupancy
            if main_image_url is not None:
                prop.main_image_url = main_image_url

            await db.flush()
            await db.refresh(prop)
            await db.commit()

            return MCPResponse.success({
                "message": "Property updated successfully",
                "property": serialize_property_basic(prop),
            }).model_dump()
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in owner.properties.update: %s", e, exc_info=True)
        return internal_error_response(f"Failed to update property: {str(e)}")


@user_mcp.tool(
    "owner_properties_toggle_availability",
    annotations={
        "title": "Toggle Property Availability",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
        "securitySchemes": MCP_SECURITY_SCHEMES_MIXED,
    },
)
async def owner_properties_toggle_availability(
    property_id: int,
    is_available: bool,
) -> Dict[str, Any]:
    """Toggle a property's availability status.

    Args:
        property_id: ID of the property
        is_available: True to mark as available, False otherwise
    """
    try:
        async for db in get_db():
            user = await _get_user(db)
            if not user:
                _require_auth(
                    action="owner_properties_toggle_availability",
                    message="Please log in to update property availability.",
                    scope="mcp:write",
                )

            from app.schemas.user import User as UserSchema
            user_schema = UserSchema.model_validate(user)

            try:
                prop = await assert_can_access_property(
                    db, actor=user_schema, property_id=property_id
                )
            except PropertyNotFoundException:
                return not_found_response("Property", property_id)
            except InsufficientPermissionsError:
                return MCPResponse.failure(
                    MCPErrorCode.INSUFFICIENT_PERMISSIONS,
                    "You do not have access to this property"
                ).model_dump()

            prop.is_available = is_available
            await db.flush()
            await db.commit()

            status = "available" if is_available else "unavailable"
            return MCPResponse.success({
                "message": f"Property marked as {status}",
                "property_id": property_id,
                "is_available": is_available,
            }).model_dump()
    except AuthRequiredError:
        raise
    except Exception as e:
        logger.error("Error in owner.properties.toggle_availability: %s", e, exc_info=True)
        return internal_error_response(f"Failed to toggle availability: {str(e)}")
