import pytest

from app.models.enums import PropertyPurpose, PropertyType
from app.models.properties import Property
from app.models.users import User
from app.services.property import list_user_properties


@pytest.mark.asyncio
async def test_list_user_properties_returns_only_owned(test_db) -> None:
    user_1 = User(
        supabase_user_id="test-user-1",
        email="user1@example.com",
        phone="+910000000001",
        full_name="User One",
        is_active=True,
        is_verified=True,
        role="user",
    )
    user_2 = User(
        supabase_user_id="test-user-2",
        email="user2@example.com",
        phone="+910000000002",
        full_name="User Two",
        is_active=True,
        is_verified=True,
        role="user",
    )
    test_db.add_all([user_1, user_2])
    await test_db.flush()

    prop_1 = Property(
        title="Property 1",
        property_type=PropertyType.apartment,
        purpose=PropertyPurpose.rent,
        base_price=25000,
        owner_id=user_1.id,
    )
    prop_2 = Property(
        title="Property 2",
        property_type=PropertyType.house,
        purpose=PropertyPurpose.buy,
        base_price=12500000,
        owner_id=user_1.id,
    )
    prop_3 = Property(
        title="Property 3",
        property_type=PropertyType.room,
        purpose=PropertyPurpose.rent,
        base_price=9000,
        owner_id=user_2.id,
    )
    test_db.add_all([prop_1, prop_2, prop_3])
    await test_db.commit()

    results = await list_user_properties(test_db, owner_id=user_1.id)
    assert len(results) == 2
    assert {p.owner_id for p in results} == {user_1.id}

