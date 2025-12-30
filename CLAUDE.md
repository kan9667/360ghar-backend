# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

### Running the API
```bash
python run.py                                      # Simple start
fastapi dev app/main.py --host 0.0.0.0 --port 8000 # Hot reload (recommended)
```

### Testing
```bash
pytest tests/ -v                              # All tests
pytest tests/test_user_service.py -v         # Specific file
pytest tests/ -k "user" -v                   # By keyword
pytest tests/test_file.py::test_func -v      # Single test
pytest tests/ --cov=app --cov-report=html    # With coverage
```

### Data Population
```bash
PYTHONPATH=$(pwd) python populate_data/load_comprehensive_data.py          # Full dataset (~300 properties)
PYTHONPATH=$(pwd) python populate_data/load_comprehensive_data.py --quick  # Quick load (~51 properties)
PYTHONPATH=$(pwd) python populate_data/load_comprehensive_data.py --clear  # Clear first, then load
```

### Database
```bash
supabase db reset   # Reset local database
supabase db push    # Apply migrations
supabase db diff    # Check pending changes
```

## Architecture Overview

### Layered Structure
```
app/
├── api/api_v1/endpoints/   # REST endpoints (thin controllers)
├── services/               # Async business logic (main logic layer)
├── repositories/           # Complex database queries
├── models/                 # SQLAlchemy ORM models
├── schemas/                # Pydantic request/response validation
├── core/                   # Config, auth, database, exceptions, logging
└── middleware/             # Rate limiting, security headers
```

### Key Patterns

**Async-First**: All database operations and services use `async/await`. Services inject `AsyncSession` via FastAPI dependencies.

**Authentication Flow**: Supabase Auth (phone + password) → JWT token → `get_current_user` dependency → local user sync

**Geospatial Search**: PostGIS `ST_DWithin` for radius-based property search, `ST_Distance` for sorting by proximity.

**Full-Text Search**: PostgreSQL `ts_vector` column (`__ts_vector__`) on properties table.

**Semantic Search**: Hybrid vector + text scoring via `property_embeddings` table (pgvector).

### Service Layer Pattern
```python
class PropertyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_properties(self, filters: dict) -> List[Property]:
        # Business logic here
```

### Dependency Injection
```python
@router.get("/properties/")
async def get_properties(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    return await property_service.search(db, current_user)
```

## Key Files

| Purpose | Location |
|---------|----------|
| App factory | `app/factory.py` |
| Main entry | `app/main.py` |
| API router | `app/api/api_v1/api.py` |
| Database config | `app/core/database.py` |
| Auth logic | `app/core/auth.py` |
| Custom exceptions | `app/core/exceptions.py` |
| Settings | `app/core/config.py` |
| Migrations | `supabase/migrations/` |

## Coding Conventions

- **Python 3.10+**, FastAPI, SQLAlchemy 2.x async, Pydantic v2
- **snake_case** for modules/functions/variables; **PascalCase** for classes
- Full type hints everywhere
- Custom exceptions from `app/core/exceptions.py` (e.g., `UserNotFoundException`)
- Pydantic schemas with `Config.from_attributes = True` for ORM mode
- Use `Optional[]` for nullable fields, avoid `Union[]`
- Validation with `@field_validator` decorators

## Database Models

**Core entities**: User, Property, Agent, Booking, Visit, UserSwipe, Amenity

**Key relationships**:
- User → Properties (as owner), Swipes, Visits, Bookings
- Property → Images, Amenities (M2M via PropertyAmenity), Visits, Bookings
- Agent → User (1:1), Visits

**Enums** (in `app/models/enums.py`):
- PropertyType: house, apartment, builder_floor, room
- PropertyPurpose: buy, rent, short_stay
- BookingStatus: pending, confirmed, checked_in, checked_out, cancelled, completed
- VisitStatus: scheduled, confirmed, completed, cancelled, rescheduled

## Security

- Supabase JWT auth via `get_current_user` dependency
- Phone as primary identifier
- Role-based access: user, agent, admin
- Rate limiting: 100 req/min global, 5 req/min for auth endpoints
- Input validation via Pydantic schemas

## API Documentation

When running locally:
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc
- OpenAPI YAML: http://localhost:8000/api/v1/openapi.yaml
- Health: http://localhost:8000/health

## MCP Server

Exposes Model Context Protocol at `/mcp` with OAuth 2.1 authentication. Configure MCP clients:
```json
{
  "mcpServers": {
    "ghar360": {
      "transport": "http",
      "url": "https://api.360ghar.com/mcp"
    }
  }
}
```
