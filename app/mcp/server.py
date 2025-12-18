from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from mcp.server.auth.middleware.auth_context import get_access_token as get_auth_access_token

from app.core.database import AsyncSessionLocal
from app.core.auth import verify_supabase_token
from app.core.exceptions import PropertyNotFoundException
from app.core.logging import get_logger
from app.mcp.errors import (
    MCPErrorCode,
    MCPResponse,
    internal_error_response,
    invalid_input_response,
    not_found_response,
    unauthorized_response,
)
from app.mcp.validation import DiscoveryFeedInput, PropertyGetInput, SwipeInput
from app.schemas.property import (
    UnifiedPropertyFilter,
    PropertySwipe,
)
from app.schemas.visit import VisitCreate
from app.services import property as property_svc
from app.services import swipe as swipe_svc
from app.services import visit as visit_svc
from app.services.user import (
    get_or_create_user_from_supabase,
    get_user_by_id,
    update_user_preferences,
)
from app.services.agent import get_user_agent
from app.services.blog import list_blog_posts, get_blog_post
from app.services.oauth_token_store import oauth_token_store

logger = get_logger(__name__)

# Create a single FastMCP server instance for the backend.
# HTTP transport and authentication are configured in app.main when mounting /mcp.
mcp = FastMCP("ghar360")

# Note: We keep a simple in-process session token for backwards compatibility with
# tools that explicitly pass or set a JWT. For HTTP-based MCP with proper bearer
# auth, tools should prefer the `jwt` argument, which will typically be populated
# by the client from the Authorization header.
_SESSION_JWT: Optional[str] = None


async def _get_db():
    async with AsyncSessionLocal() as db:
        yield db


async def _get_user_from_jwt(db, jwt: Optional[str]) -> Optional[Any]:
    """
    Resolve the current authenticated user for MCP tools.

    Priority:
    1. Use the access token from the MCP auth context (OAuth or Supabase JWT)
    2. Fallback to an explicit JWT argument or legacy session JWT
    """
    # 1) Authenticated bearer token from MCP HTTP auth (preferred path)
    access_token = get_auth_access_token()
    if access_token is not None:
        claims = getattr(access_token, "claims", {}) or {}
        auth_method = claims.get("auth_method")

        if auth_method == "oauth":
            user_id_raw = claims.get("sub") or claims.get("user_id")
            if not user_id_raw:
                logger.warning("OAuth access token missing user id claim")
                return None
            try:
                user_id = int(user_id_raw)
            except (TypeError, ValueError):
                logger.warning("OAuth access token has invalid user id: %r", user_id_raw)
                return None

            user = await get_user_by_id(db, user_id)
            if not user:
                logger.warning("OAuth access token refers to unknown user id %s", user_id)
            return user

        if auth_method == "supabase_jwt":
            supa_id = claims.get("sub")
            if not supa_id:
                logger.warning("Supabase JWT access token missing sub claim")
                return None
            supa_data = {
                "id": supa_id,
                "email": claims.get("email"),
                "phone": claims.get("phone"),
                "email_verified": claims.get("email_verified", False),
                "user_metadata": claims.get("user_metadata") or {},
            }
            return await get_or_create_user_from_supabase(db, supa_data)

    # 2) Fallback: explicit JWT argument or legacy in-process session JWT
    token = jwt or _SESSION_JWT
    if not token:
        return None

    supa = await verify_supabase_token(token)
    if not supa:
        return None
    return await get_or_create_user_from_supabase(db, supa)


@mcp.tool("auth.set_jwt")
async def auth_set_jwt(jwt: str) -> Dict[str, Any]:
    """Store a bearer JWT for subsequent tool calls in this MCP session."""
    global _SESSION_JWT
    # Basic shape check
    if not isinstance(jwt, str) or len(jwt.split(".")) < 3:
        return invalid_input_response("Invalid JWT format")
    _SESSION_JWT = jwt
    return MCPResponse.success({"message": "JWT stored successfully"}).dict()


@mcp.tool("auth.logout")
async def auth_logout(jwt: Optional[str] = None) -> Dict[str, Any]:
    """Revoke the current session token and clear session state."""
    global _SESSION_JWT
    try:
        # Get the token to revoke
        access_token = get_auth_access_token()
        token_to_revoke = None
        
        if access_token is not None:
            claims = getattr(access_token, "claims", {}) or {}
            if claims.get("auth_method") == "oauth":
                token_to_revoke = getattr(access_token, "token", None)
        
        # Revoke OAuth token if present
        if token_to_revoke:
            await oauth_token_store.revoke_token(token_to_revoke)
        
        # Clear session JWT
        _SESSION_JWT = None
        
        return MCPResponse.success({"message": "Logged out successfully"}).dict()
    except Exception as e:
        logger.error(f"Error in auth.logout: {e}", exc_info=True)
        return internal_error_response(f"Failed to logout: {str(e)}")


@mcp.tool("auth.refresh")
async def auth_refresh(refresh_token: str) -> Dict[str, Any]:
    """Refresh access token using a refresh token."""
    try:
        refresh_data = await oauth_token_store.get_refresh_token(refresh_token)
        if not refresh_data:
            return MCPResponse.failure(
                MCPErrorCode.INVALID_TOKEN,
                "Invalid or expired refresh token"
            ).dict()
        
        # Generate new access token
        import secrets
        new_access_token = secrets.token_urlsafe(32)
        
        await oauth_token_store.store_oauth_tokens(
            access_token=new_access_token,
            refresh_token=refresh_token,
            user_id=refresh_data["user_id"],
            scope=refresh_data["scope"],
            access_token_expires_in=3600,
            refresh_token_expires_in=86400 * 30,
        )
        
        return MCPResponse.success({
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": refresh_data["scope"],
        }).dict()
    except Exception as e:
        logger.error(f"Error in auth.refresh: {e}", exc_info=True)
        return internal_error_response(f"Failed to refresh token: {str(e)}")


@mcp.tool("auth.whoami")
async def auth_whoami(jwt: Optional[str] = None) -> Dict[str, Any]:
    """Return the current authenticated user with full profile details."""
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return MCPResponse.failure(
                    MCPErrorCode.UNAUTHORIZED,
                    "Not authenticated"
                ).dict()
            
            # Get assigned agent if any
            agent_info = None
            if getattr(user, "agent_id", None):
                agent = await get_user_agent(db, user.id, auto_assign=False)
                if agent:
                    agent_info = {
                        "id": agent.id,
                        "name": agent.name,
                        "phone": agent.phone,
                        "email": agent.email,
                        "agent_type": agent.agent_type,
                    }
            
            return MCPResponse.success({
                "authenticated": True,
                "user": {
                    "id": user.id,
                    "email": getattr(user, "email", None),
                    "phone": getattr(user, "phone", None),
                    "full_name": getattr(user, "full_name", None),
                    "role": getattr(user, "role", "user"),
                    "is_verified": getattr(user, "is_verified", False),
                    "profile_image_url": getattr(user, "profile_image_url", None),
                    "preferences": getattr(user, "preferences", None),
                    "notification_settings": getattr(user, "notification_settings", None),
                    "current_latitude": getattr(user, "current_latitude", None),
                    "current_longitude": getattr(user, "current_longitude", None),
                    "created_at": getattr(user, "created_at", None).isoformat() if getattr(user, "created_at", None) else None,
                },
                "agent": agent_info,
            }).dict()
    except Exception as e:
        logger.error(f"Error in auth.whoami: {e}", exc_info=True)
        return internal_error_response(f"Failed to get user info: {str(e)}")


@mcp.tool("properties.search")
async def properties_search(
    jwt: Optional[str] = None,
    search_query: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: int = 5,
    page: int = 1,
    limit: int = 20,
    include_unavailable: bool = False,
) -> Dict[str, Any]:
    """Search properties with optional text and location filters."""
    try:
        limit = min(max(1, limit), 50)
        if latitude is not None and not (-90 <= latitude <= 90):
            return invalid_input_response("Invalid latitude (must be -90 to 90)")
        if longitude is not None and not (-180 <= longitude <= 180):
            return invalid_input_response("Invalid longitude (must be -180 to 180)")
        if radius_km < 0 or radius_km > 50:
            return invalid_input_response("radius_km must be between 0 and 50")

        filters = UnifiedPropertyFilter(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            search_query=search_query,
            include_unavailable=include_unavailable,
        )

        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            uid = user.id if user else None
            data = await property_svc.get_unified_properties_optimized(
                db=db, filters=filters, user_id=uid, page=page, limit=limit
            )
            # Serialize enriched fields for MCP clients
            items = []
            for p in data["items"]:
                items.append(
                    {
                        "id": p.id,
                        "title": p.title,
                        "property_type": getattr(p, "property_type", None).value if getattr(p, "property_type", None) else None,
                        "purpose": getattr(p, "purpose", None).value if getattr(p, "purpose", None) else None,
                        "city": p.city,
                        "locality": p.locality,
                        "price": p.base_price,
                        "monthly_rent": getattr(p, "monthly_rent", None),
                        "daily_rate": getattr(p, "daily_rate", None),
                        "bedrooms": getattr(p, "bedrooms", None),
                        "bathrooms": getattr(p, "bathrooms", None),
                        "area_sqft": getattr(p, "area_sqft", None),
                        "is_available": getattr(p, "is_available", True),
                        "latitude": p.latitude,
                        "longitude": p.longitude,
                        "main_image_url": p.main_image_url,
                        "distance_km": getattr(p, "distance_km", None),
                    }
                )
            return MCPResponse.success({
                "total": data["total"],
                "page": page,
                "limit": limit,
                "total_pages": data.get("total_pages", 1),
                "items": items,
            }).dict()
    except Exception as e:
        logger.error(f"Error in properties.search: {e}", exc_info=True)
        return internal_error_response(f"Failed to search properties: {str(e)}")


@mcp.tool("properties.get")
async def properties_get(property_id: int, jwt: Optional[str] = None) -> Dict[str, Any]:
    """Get a single property with full details and user context."""
    try:
        # Validate input
        input_data = PropertyGetInput(property_id=property_id)
    except ValueError as e:
        return invalid_input_response(str(e))
    
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            try:
                prop = await property_svc.get_property(db, input_data.property_id)
            except PropertyNotFoundException:
                return not_found_response("Property", input_data.property_id)
            
            # Build enriched property data
            property_data = {
                # Core info
                "id": prop.id,
                "title": prop.title,
                "description": prop.description,
                "property_type": getattr(prop, "property_type", None).value if getattr(prop, "property_type", None) else None,
                "purpose": getattr(prop, "purpose", None).value if getattr(prop, "purpose", None) else None,
                "status": getattr(prop, "status", None).value if getattr(prop, "status", None) else None,
                # Location
                "full_address": getattr(prop, "full_address", None),
                "city": prop.city,
                "locality": prop.locality,
                "sub_locality": getattr(prop, "sub_locality", None),
                "landmark": getattr(prop, "landmark", None),
                "pincode": getattr(prop, "pincode", None),
                "state": getattr(prop, "state", None),
                "country": getattr(prop, "country", None),
                "latitude": prop.latitude,
                "longitude": prop.longitude,
                # Pricing
                "base_price": prop.base_price,
                "monthly_rent": getattr(prop, "monthly_rent", None),
                "daily_rate": getattr(prop, "daily_rate", None),
                "price_per_sqft": getattr(prop, "price_per_sqft", None),
                "security_deposit": getattr(prop, "security_deposit", None),
                "maintenance_charges": getattr(prop, "maintenance_charges", None),
                # Specs
                "area_sqft": getattr(prop, "area_sqft", None),
                "bedrooms": getattr(prop, "bedrooms", None),
                "bathrooms": getattr(prop, "bathrooms", None),
                "balconies": getattr(prop, "balconies", None),
                "parking_spaces": getattr(prop, "parking_spaces", None),
                "floor_number": getattr(prop, "floor_number", None),
                "total_floors": getattr(prop, "total_floors", None),
                "max_occupancy": getattr(prop, "max_occupancy", None),
                "age_of_property": getattr(prop, "age_of_property", None),
                # Media
                "main_image_url": prop.main_image_url,
                "images": [
                    {"url": i.image_url, "caption": getattr(i, "caption", None)}
                    for i in (prop.images or [])
                ],
                "virtual_tour_url": getattr(prop, "virtual_tour_url", None),
                "video_tour_url": getattr(prop, "video_tour_url", None),
                # Features & Amenities
                "amenities": [
                    {
                        "id": getattr(a, "amenity", a).id if hasattr(a, "amenity") else getattr(a, "id", None),
                        "title": getattr(a, "amenity", a).title if hasattr(a, "amenity") else getattr(a, "title", None),
                        "icon": getattr(getattr(a, "amenity", a), "icon", None) if hasattr(a, "amenity") else getattr(a, "icon", None),
                        "category": getattr(getattr(a, "amenity", a), "category", None) if hasattr(a, "amenity") else getattr(a, "category", None),
                    }
                    for a in (prop.amenities or [])
                ],
                "features": getattr(prop, "features", None),
                "tags": getattr(prop, "tags", None),
                # Availability
                "is_available": getattr(prop, "is_available", True),
                "available_from": getattr(prop, "available_from", None).isoformat() if getattr(prop, "available_from", None) else None,
                "minimum_stay_days": getattr(prop, "minimum_stay_days", None),
                # Owner info
                "owner_name": getattr(prop, "owner_name", None),
                "builder_name": getattr(prop, "builder_name", None),
                # Stats
                "view_count": getattr(prop, "view_count", 0),
                "like_count": getattr(prop, "like_count", 0),
                "created_at": getattr(prop, "created_at", None).isoformat() if getattr(prop, "created_at", None) else None,
            }
            
            # User context if authenticated
            user_context = None
            if user:
                is_liked = await swipe_svc.get_user_like_for_property(db, user.id, prop.id)
                
                # Check if user has scheduled visits for this property
                user_visits_data = await visit_svc.get_user_visits(db, user.id)
                property_visits = [
                    v for v in user_visits_data.get("visits", [])
                    if v.property_id == prop.id
                ]
                
                user_context = {
                    "is_liked": is_liked,
                    "has_visited": any(v.status == "completed" for v in property_visits),
                    "scheduled_visits": [
                        {
                            "id": v.id,
                            "scheduled_date": v.scheduled_date.isoformat() if v.scheduled_date else None,
                            "status": v.status,
                        }
                        for v in property_visits
                        if v.status in ["scheduled", "confirmed", "rescheduled"]
                    ],
                }

            return MCPResponse.success({
                "property": property_data,
                "user_context": user_context,
            }).dict()
    except Exception as e:
        logger.error(f"Error in properties.get: {e}", exc_info=True)
        return internal_error_response(f"Failed to get property: {str(e)}")


@mcp.tool("discovery.feed")
async def discovery_feed(jwt: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """Get a recommended property feed for the current user."""
    try:
        # Validate input
        input_data = DiscoveryFeedInput(limit=limit)
    except ValueError as e:
        return invalid_input_response(str(e))
    
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            uid = user.id if user else None
            props = await property_svc.get_property_recommendations(db, user_id=uid, limit=input_data.limit)
            items = [
                {
                    "id": p.id,
                    "title": p.title,
                    "property_type": getattr(p, "property_type", None).value if getattr(p, "property_type", None) else None,
                    "purpose": getattr(p, "purpose", None).value if getattr(p, "purpose", None) else None,
                    "city": p.city,
                    "locality": p.locality,
                    "price": p.base_price,
                    "monthly_rent": getattr(p, "monthly_rent", None),
                    "daily_rate": getattr(p, "daily_rate", None),
                    "bedrooms": getattr(p, "bedrooms", None),
                    "bathrooms": getattr(p, "bathrooms", None),
                    "area_sqft": getattr(p, "area_sqft", None),
                    "is_available": getattr(p, "is_available", True),
                    "main_image_url": p.main_image_url,
                }
                for p in props
            ]
            return MCPResponse.success({
                "items": items,
                "count": len(items),
            }).dict()
    except Exception as e:
        logger.error(f"Error in discovery.feed: {e}", exc_info=True)
        return internal_error_response(f"Failed to get discovery feed: {str(e)}")


@mcp.tool("swipes.like")
async def swipes_like(property_id: int, jwt: Optional[str] = None) -> Dict[str, Any]:
    """Like a property."""
    try:
        # Validate input
        input_data = SwipeInput(property_id=property_id)
    except ValueError as e:
        return invalid_input_response(str(e))
    
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return unauthorized_response("Authentication required to like properties")
            
            ok = await swipe_svc.record_swipe(
                db, user.id, PropertySwipe(property_id=input_data.property_id, is_liked=True)
            )
            await db.commit()
            return MCPResponse.success({
                "liked": bool(ok),
                "property_id": input_data.property_id,
            }).dict()
    except Exception as e:
        logger.error(f"Error in swipes.like: {e}", exc_info=True)
        return internal_error_response(f"Failed to like property: {str(e)}")


@mcp.tool("swipes.dislike")
async def swipes_dislike(property_id: int, jwt: Optional[str] = None) -> Dict[str, Any]:
    """Dislike a property."""
    try:
        # Validate input
        input_data = SwipeInput(property_id=property_id)
    except ValueError as e:
        return invalid_input_response(str(e))
    
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return unauthorized_response("Authentication required to dislike properties")
            
            ok = await swipe_svc.record_swipe(
                db, user.id, PropertySwipe(property_id=input_data.property_id, is_liked=False)
            )
            await db.commit()
            return MCPResponse.success({
                "disliked": bool(ok),
                "property_id": input_data.property_id,
            }).dict()
    except Exception as e:
        logger.error(f"Error in swipes.dislike: {e}", exc_info=True)
        return internal_error_response(f"Failed to dislike property: {str(e)}")


@mcp.tool("swipes.undo")
async def swipes_undo(jwt: Optional[str] = None) -> Dict[str, Any]:
    """Undo last swipe for the current user."""
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return unauthorized_response("Authentication required to undo swipes")
            
            last = await swipe_svc.undo_last_swipe(db, user.id)
            await db.commit()
            
            if last is None:
                return MCPResponse.failure(
                    MCPErrorCode.NOT_FOUND,
                    "No swipe found to undo"
                ).dict()
            
            return MCPResponse.success({"undone": True}).dict()
    except Exception as e:
        logger.error(f"Error in swipes.undo: {e}", exc_info=True)
        return internal_error_response(f"Failed to undo swipe: {str(e)}")


@mcp.tool("shortlist.list")
async def shortlist_list(
    jwt: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> Dict[str, Any]:
    """List liked properties for the current user with enriched property details."""
    try:
        limit = min(max(1, limit), 50)
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return unauthorized_response("Authentication required to view shortlist")
            filters = UnifiedPropertyFilter()
            data = await swipe_svc.get_swipe_history(db, user.id, filters, page, limit, is_liked=True)
            items: List[Dict[str, Any]] = []
            for swipe in data["items"]:
                p = swipe.property
                if not p:
                    continue
                items.append(
                    {
                        "id": p.id,
                        "title": p.title,
                        "property_type": getattr(p, "property_type", None).value if getattr(p, "property_type", None) else None,
                        "purpose": getattr(p, "purpose", None).value if getattr(p, "purpose", None) else None,
                        "city": p.city,
                        "locality": p.locality,
                        "price": p.base_price,
                        "monthly_rent": getattr(p, "monthly_rent", None),
                        "daily_rate": getattr(p, "daily_rate", None),
                        "bedrooms": getattr(p, "bedrooms", None),
                        "bathrooms": getattr(p, "bathrooms", None),
                        "area_sqft": getattr(p, "area_sqft", None),
                        "is_available": getattr(p, "is_available", True),
                        "main_image_url": p.main_image_url,
                        "liked_at": swipe.created_at.isoformat() if getattr(swipe, "created_at", None) else None,
                    }
                )
            return MCPResponse.success({
                "total": data["total"],
                "page": data["page"],
                "limit": data["limit"],
                "total_pages": data["total_pages"],
                "items": items,
            }).dict()
    except Exception as e:
        logger.error(f"Error in shortlist.list: {e}", exc_info=True)
        return internal_error_response(f"Failed to list shortlist: {str(e)}")


@mcp.tool("visits.schedule")
async def visits_schedule(
    property_id: int,
    scheduled_date_iso: str,
    special_requirements: Optional[str] = None,
    jwt: Optional[str] = None,
) -> Dict[str, Any]:
    """Schedule a property visit for the current user."""
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(scheduled_date_iso)
    except Exception:
        return invalid_input_response("scheduled_date_iso must be ISO-8601 format")

    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return unauthorized_response("Authentication required to schedule visits")
            visit = await visit_svc.create_visit(
                db,
                user_id=user.id,
                visit=VisitCreate(property_id=property_id, scheduled_date=dt, special_requirements=special_requirements),
            )
            await db.commit()
            return MCPResponse.success({
                "visit_id": visit.id,
                "property_id": property_id,
                "scheduled_date": dt.isoformat(),
                "status": visit.status,
            }).dict()
    except ValueError as e:
        return invalid_input_response(str(e))
    except Exception as e:
        logger.error(f"Error in visits.schedule: {e}", exc_info=True)
        return internal_error_response(f"Failed to schedule visit: {str(e)}")


@mcp.tool("visits.list")
async def visits_list(jwt: Optional[str] = None) -> Dict[str, Any]:
    """List visits for the current user with full property and agent details."""
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return unauthorized_response("Authentication required to view visits")
            data = await visit_svc.get_user_visits(db, user.id)
            out = []
            for v in data["visits"]:
                p = v.property
                property_info = None
                if p:
                    property_info = {
                        "id": p.id,
                        "title": p.title,
                        "property_type": getattr(p, "property_type", None).value if getattr(p, "property_type", None) else None,
                        "purpose": getattr(p, "purpose", None).value if getattr(p, "purpose", None) else None,
                        "city": getattr(p, "city", None),
                        "locality": getattr(p, "locality", None),
                        "full_address": getattr(p, "full_address", None),
                        "latitude": getattr(p, "latitude", None),
                        "longitude": getattr(p, "longitude", None),
                        "price": getattr(p, "base_price", None),
                        "bedrooms": getattr(p, "bedrooms", None),
                        "bathrooms": getattr(p, "bathrooms", None),
                        "main_image_url": p.main_image_url,
                    }
                
                # Get agent info if assigned
                agent_info = None
                if getattr(v, "agent_id", None):
                    from app.services.agent import get_agent_by_id
                    agent = await get_agent_by_id(db, v.agent_id)
                    if agent:
                        agent_info = {
                            "id": agent.id,
                            "name": agent.name,
                            "phone": agent.phone,
                            "email": agent.email,
                        }
                
                out.append({
                    "id": v.id,
                    "property_id": v.property_id,
                    "scheduled_date": v.scheduled_date.isoformat() if v.scheduled_date else None,
                    "status": v.status,
                    "special_requirements": getattr(v, "special_requirements", None),
                    "notes": getattr(v, "notes", None),
                    "property": property_info,
                    "agent": agent_info,
                    "created_at": v.created_at.isoformat() if getattr(v, "created_at", None) else None,
                })
            
            return MCPResponse.success({
                "total": data.get("total", len(out)),
                "upcoming": data.get("upcoming", 0),
                "completed": data.get("completed", 0),
                "cancelled": data.get("cancelled", 0),
                "visits": out,
            }).dict()
    except Exception as e:
        logger.error(f"Error in visits.list: {e}", exc_info=True)
        return internal_error_response(f"Failed to list visits: {str(e)}")


@mcp.tool("visits.cancel")
async def visits_cancel(visit_id: int, reason: str, jwt: Optional[str] = None) -> Dict[str, Any]:
    """Cancel a visit for the current user."""
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return unauthorized_response("Authentication required to cancel visits")
            # Basic ownership check: ensure the visit belongs to the user
            v = await visit_svc.get_visit(db, visit_id)
            if not v:
                return not_found_response("Visit", visit_id)
            if v.user_id != user.id:
                return MCPResponse.failure(
                    MCPErrorCode.INSUFFICIENT_PERMISSIONS,
                    "You can only cancel your own visits"
                ).dict()
            updated = await visit_svc.cancel_visit(db, visit_id, reason)
            await db.commit()
            return MCPResponse.success({
                "cancelled": bool(updated),
                "visit_id": visit_id,
            }).dict()
    except Exception as e:
        logger.error(f"Error in visits.cancel: {e}", exc_info=True)
        return internal_error_response(f"Failed to cancel visit: {str(e)}")


# ============================================================================
# User Profile Tools
# ============================================================================


@mcp.tool("user.profile")
async def user_profile(jwt: Optional[str] = None) -> Dict[str, Any]:
    """Get the full user profile with preferences and settings."""
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return unauthorized_response("Authentication required")
            
            # Get swipe stats
            swipe_stats = await swipe_svc.get_swipe_stats(db, user.id)
            
            # Get assigned agent
            agent_info = None
            if getattr(user, "agent_id", None):
                agent = await get_user_agent(db, user.id, auto_assign=False)
                if agent:
                    agent_info = {
                        "id": agent.id,
                        "name": agent.name,
                        "phone": agent.phone,
                        "email": agent.email,
                        "agent_type": agent.agent_type,
                        "specialization": getattr(agent, "specialization", None),
                    }
            
            return MCPResponse.success({
                "user": {
                    "id": user.id,
                    "email": getattr(user, "email", None),
                    "phone": getattr(user, "phone", None),
                    "full_name": getattr(user, "full_name", None),
                    "role": getattr(user, "role", "user"),
                    "is_verified": getattr(user, "is_verified", False),
                    "is_active": getattr(user, "is_active", True),
                    "profile_image_url": getattr(user, "profile_image_url", None),
                    "current_latitude": getattr(user, "current_latitude", None),
                    "current_longitude": getattr(user, "current_longitude", None),
                    "created_at": getattr(user, "created_at", None).isoformat() if getattr(user, "created_at", None) else None,
                },
                "preferences": getattr(user, "preferences", None) or {},
                "notification_settings": getattr(user, "notification_settings", None) or {},
                "privacy_settings": getattr(user, "privacy_settings", None) or {},
                "stats": {
                    "total_swipes": swipe_stats.get("total_swipes", 0),
                    "liked_count": swipe_stats.get("liked_count", 0),
                    "disliked_count": swipe_stats.get("disliked_count", 0),
                    "like_percentage": swipe_stats.get("like_percentage", 0),
                },
                "agent": agent_info,
            }).dict()
    except Exception as e:
        logger.error(f"Error in user.profile: {e}", exc_info=True)
        return internal_error_response(f"Failed to get user profile: {str(e)}")


@mcp.tool("user.update_preferences")
async def user_update_preferences(
    preferences: Dict[str, Any],
    jwt: Optional[str] = None,
) -> Dict[str, Any]:
    """Update user search and notification preferences."""
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return unauthorized_response("Authentication required")
            
            updated_user = await update_user_preferences(db, user.id, preferences)
            await db.commit()
            
            if not updated_user:
                return internal_error_response("Failed to update preferences")
            
            return MCPResponse.success({
                "message": "Preferences updated successfully",
                "preferences": updated_user.preferences,
            }).dict()
    except Exception as e:
        logger.error(f"Error in user.update_preferences: {e}", exc_info=True)
        return internal_error_response(f"Failed to update preferences: {str(e)}")


# ============================================================================
# Agent Tools
# ============================================================================


@mcp.tool("agents.get_assigned")
async def agents_get_assigned(jwt: Optional[str] = None) -> Dict[str, Any]:
    """Get the user's assigned Relationship Manager agent with contact details."""
    try:
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if not user:
                return unauthorized_response("Authentication required")
            
            agent = await get_user_agent(db, user.id, auto_assign=False)
            if not agent:
                return MCPResponse.success({
                    "has_agent": False,
                    "agent": None,
                    "message": "No agent assigned. Use the mobile app to get an agent assigned.",
                }).dict()
            
            return MCPResponse.success({
                "has_agent": True,
                "agent": {
                    "id": agent.id,
                    "name": agent.name,
                    "phone": agent.phone,
                    "email": agent.email,
                    "agent_type": agent.agent_type,
                    "specialization": getattr(agent, "specialization", None),
                    "experience_level": getattr(agent, "experience_level", None),
                    "rating": getattr(agent, "rating", None),
                    "total_clients": getattr(agent, "total_clients", 0),
                    "is_available": getattr(agent, "is_available", True),
                    "profile_image_url": getattr(agent, "profile_image_url", None),
                    "bio": getattr(agent, "bio", None),
                },
            }).dict()
    except Exception as e:
        logger.error(f"Error in agents.get_assigned: {e}", exc_info=True)
        return internal_error_response(f"Failed to get assigned agent: {str(e)}")


# ============================================================================
# Advanced Search Tools
# ============================================================================


@mcp.tool("properties.search_advanced")
async def properties_search_advanced(
    jwt: Optional[str] = None,
    search_query: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: int = 5,
    property_type: Optional[str] = None,
    purpose: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    amenities: Optional[List[int]] = None,
    page: int = 1,
    limit: int = 20,
    include_unavailable: bool = False,
) -> Dict[str, Any]:
    """Advanced property search with full filter support."""
    try:
        limit = min(max(1, limit), 50)
        if latitude is not None and not (-90 <= latitude <= 90):
            return invalid_input_response("Invalid latitude (must be -90 to 90)")
        if longitude is not None and not (-180 <= longitude <= 180):
            return invalid_input_response("Invalid longitude (must be -180 to 180)")
        if radius_km < 0 or radius_km > 50:
            return invalid_input_response("radius_km must be between 0 and 50")
        if min_price is not None and max_price is not None and min_price > max_price:
            return invalid_input_response("min_price cannot be greater than max_price")

        # Build filters
        filters = UnifiedPropertyFilter(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            search_query=search_query,
            include_unavailable=include_unavailable,
            price_min=min_price,
            price_max=max_price,
            bedrooms_min=bedrooms,
            bathrooms_min=bathrooms,
            area_min=min_area,
            area_max=max_area,
            amenity_ids=amenities,
        )
        
        # Handle property_type filter
        if property_type:
            from app.models.enums import PropertyType
            try:
                filters.property_type = [PropertyType(property_type)]
            except ValueError:
                return invalid_input_response(f"Invalid property_type: {property_type}")
        
        # Handle purpose filter
        if purpose:
            from app.models.enums import PropertyPurpose
            try:
                filters.purpose = PropertyPurpose(purpose)
            except ValueError:
                return invalid_input_response(f"Invalid purpose: {purpose}")

        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            uid = user.id if user else None
            data = await property_svc.get_unified_properties_optimized(
                db=db, filters=filters, user_id=uid, page=page, limit=limit
            )
            
            items = []
            for p in data["items"]:
                items.append({
                    "id": p.id,
                    "title": p.title,
                    "property_type": getattr(p, "property_type", None).value if getattr(p, "property_type", None) else None,
                    "purpose": getattr(p, "purpose", None).value if getattr(p, "purpose", None) else None,
                    "city": p.city,
                    "locality": p.locality,
                    "sub_locality": getattr(p, "sub_locality", None),
                    "price": p.base_price,
                    "monthly_rent": getattr(p, "monthly_rent", None),
                    "daily_rate": getattr(p, "daily_rate", None),
                    "bedrooms": getattr(p, "bedrooms", None),
                    "bathrooms": getattr(p, "bathrooms", None),
                    "area_sqft": getattr(p, "area_sqft", None),
                    "is_available": getattr(p, "is_available", True),
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "main_image_url": p.main_image_url,
                    "distance_km": getattr(p, "distance_km", None),
                })
            
            return MCPResponse.success({
                "total": data["total"],
                "page": page,
                "limit": limit,
                "total_pages": data.get("total_pages", 1),
                "filters_applied": {
                    "search_query": search_query,
                    "property_type": property_type,
                    "purpose": purpose,
                    "price_range": [min_price, max_price] if min_price or max_price else None,
                    "bedrooms": bedrooms,
                    "bathrooms": bathrooms,
                    "area_range": [min_area, max_area] if min_area or max_area else None,
                    "location": {"lat": latitude, "lng": longitude, "radius_km": radius_km} if latitude else None,
                },
                "items": items,
            }).dict()
    except Exception as e:
        logger.error(f"Error in properties.search_advanced: {e}", exc_info=True)
        return internal_error_response(f"Failed to search properties: {str(e)}")


# ============================================================================
# Blog Tools
# ============================================================================


@mcp.tool("blog.search")
async def blog_search(
    query: Optional[str] = None,
    categories: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    page: int = 1,
    limit: int = 20,
) -> Dict[str, Any]:
    """Search blog posts by query, categories, or tags."""
    try:
        limit = min(max(1, limit), 50)
        
        async for db in _get_db():
            posts, total = await list_blog_posts(
                db,
                q=query,
                categories=categories,
                tags=tags,
                page=page,
                limit=limit,
                include_inactive=False,
            )
            
            items = []
            for post in posts:
                items.append({
                    "id": post.id,
                    "title": post.title,
                    "slug": post.slug,
                    "excerpt": post.content[:200] + "..." if post.content and len(post.content) > 200 else post.content,
                    "featured_image_url": getattr(post, "featured_image_url", None),
                    "categories": [c.name for c in (post.categories or [])],
                    "tags": [t.name for t in (post.tags or [])],
                    "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
                })
            
            total_pages = (total + limit - 1) // limit
            return MCPResponse.success({
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "items": items,
            }).dict()
    except Exception as e:
        logger.error(f"Error in blog.search: {e}", exc_info=True)
        return internal_error_response(f"Failed to search blog posts: {str(e)}")


@mcp.tool("blog.get")
async def blog_get(identifier: str) -> Dict[str, Any]:
    """Get a blog post by ID or slug with full content."""
    try:
        async for db in _get_db():
            post = await get_blog_post(db, identifier, include_inactive=False)
            
            if not post:
                return not_found_response("Blog post", identifier)
            
            return MCPResponse.success({
                "post": {
                    "id": post.id,
                    "title": post.title,
                    "slug": post.slug,
                    "content": post.content,
                    "featured_image_url": getattr(post, "featured_image_url", None),
                    "meta_title": getattr(post, "meta_title", None),
                    "meta_description": getattr(post, "meta_description", None),
                    "categories": [{"id": c.id, "name": c.name, "slug": c.slug} for c in (post.categories or [])],
                    "tags": [{"id": t.id, "name": t.name, "slug": t.slug} for t in (post.tags or [])],
                    "author_id": getattr(post, "author_id", None),
                    "created_at": post.created_at.isoformat() if getattr(post, "created_at", None) else None,
                    "updated_at": post.updated_at.isoformat() if getattr(post, "updated_at", None) else None,
                },
            }).dict()
    except Exception as e:
        logger.error(f"Error in blog.get: {e}", exc_info=True)
        return internal_error_response(f"Failed to get blog post: {str(e)}")


# ============================================================================
# System Tools
# ============================================================================


@mcp.tool("system.status")
async def system_status(jwt: Optional[str] = None) -> Dict[str, Any]:
    """Get system status and available features."""
    try:
        # Check auth status
        auth_status = "unauthenticated"
        user_info = None
        
        async for db in _get_db():
            user = await _get_user_from_jwt(db, jwt)
            if user:
                auth_status = "authenticated"
                user_info = {
                    "id": user.id,
                    "role": getattr(user, "role", "user"),
                }
        
        return MCPResponse.success({
            "status": "operational",
            "version": "2.0.0",
            "auth": {
                "status": auth_status,
                "user": user_info,
                "methods": ["supabase_jwt", "oauth"],
            },
            "features": {
                "properties": {
                    "search": True,
                    "search_advanced": True,
                    "get": True,
                    "discovery_feed": True,
                },
                "swipes": {
                    "like": True,
                    "dislike": True,
                    "undo": True,
                    "shortlist": True,
                },
                "visits": {
                    "schedule": True,
                    "list": True,
                    "cancel": True,
                },
                "user": {
                    "profile": True,
                    "update_preferences": True,
                },
                "agents": {
                    "get_assigned": True,
                },
                "blog": {
                    "search": True,
                    "get": True,
                },
            },
            "endpoints": {
                "oauth_authorize": "/mcp/oauth/authorize",
                "oauth_token": "/mcp/oauth/token",
                "api_docs": "/api/v1/docs",
            },
        }).dict()
    except Exception as e:
        logger.error(f"Error in system.status: {e}", exc_info=True)
        return internal_error_response(f"Failed to get system status: {str(e)}")


def run():
    mcp.run()


if __name__ == "__main__":
    run()
