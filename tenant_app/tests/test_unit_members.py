import pytest
from tenant_app.api import (
    MemberCreateSchema,
    MemberUpdateSchema,
    list_members,
    create_member,
    get_member,
    update_member,
    delete_member,
)
from tenant_app.models import Member, Region

# Constant used in tests
NONEXISTENT_ID = 9999


@pytest.fixture(autouse=True)
def _tenant_context(mocker):
    """Unit tests call views directly; stub tenant context and skip real transactions."""
    mocker.patch("tenant_app.api.transaction.atomic")
    client = mocker.Mock(id=1)
    mocker.patch("tenant_app.api.get_current_tenant", return_value=client)
    mocker.patch("tenant_app.api._request_client", return_value=client)
    return client

# --- Unit Tests ---
def test_unit_list_members(mocker, member1_unit_data, member2_unit_data):
    """Test listing members in a region (unit)"""
    mocker.patch("tenant_app.api.Region.objects.get")
    mock_filter = mocker.patch("tenant_app.api.Member.objects.filter")
    mock_filter.return_value = [member1_unit_data, member2_unit_data]

    result = list_members(None, "west-coast")

    assert len(result) == 2
    assert isinstance(result, list)
    assert result[0].id == 1
    assert result[0].name == "Test User 1"
    assert result[1].id == 2
    assert result[1].name == "Test User 2"
    mock_filter.assert_called_once_with(region__slug="west-coast")

def test_unit_create_member(mocker, _tenant_context):
    """Test creating a new member (unit)"""
    region = Region(id=4, name="West Coast", slug="west-coast", client_id=1)
    mock_resolve = mocker.patch("tenant_app.api.resolve_region", return_value=region)
    mock_create = mocker.patch('tenant_app.api.Member.objects.create')
    created_instance = Member(
        id=3,
        name="New Test User",
        email="new@example.com",
        phone="555-555-5555",
        region=region,
        client_id=1,
    )
    mock_create.return_value = created_instance

    payload = MemberCreateSchema(
        name="New Test User",
        email="new@example.com",
        phone="555-555-5555",
        region_name="West Coast",
    )

    result = create_member(None, payload)

    assert result.id == 3
    assert result.name == "New Test User"
    assert result.email == "new@example.com"
    assert result.phone == "555-555-5555"
    mock_resolve.assert_called_once_with("West Coast")
    mock_create.assert_called_once_with(
        name="New Test User",
        email="new@example.com",
        phone="555-555-5555",
        region=region,
        client=_tenant_context,
    )

def test_unit_get_member(mocker, member1_unit_data):
    """Test retrieving a specific member (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_get.return_value = member1_unit_data

    result = get_member(None, "west-coast", 1)

    assert result.id == 1
    assert result.name == "Test User 1"
    assert result.email == "test1@example.com"
    mock_get.assert_called_once_with(id=1, region__slug="west-coast")

def test_unit_get_nonexistent_member(mocker):
    """Test retrieving a member that doesn't exist (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_get.side_effect = Member.DoesNotExist
    
    # We expect the exception to be raised and handled by the ninja framework
    with pytest.raises(Member.DoesNotExist):
        get_member(None, "west-coast", NONEXISTENT_ID)
    
    mock_get.assert_called_once_with(id=NONEXISTENT_ID, region__slug="west-coast")

def test_unit_update_member(mocker):
    """Test updating a member (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_member_instance = mocker.MagicMock(spec=Member)
    mock_member_instance.id = 1
    mock_member_instance.name = "Original Name"
    mock_member_instance.email = "original@example.com"
    mock_member_instance.phone = "111-111-1111"
    mock_get.return_value = mock_member_instance

    payload = MemberUpdateSchema(
        name="Updated Test User",
        email="updated@example.com",
        phone="999-999-9999"
    )

    result = update_member(None, "west-coast", 1, payload)

    mock_get.assert_called_once_with(id=1, region__slug="west-coast")
    assert mock_member_instance.name == "Updated Test User"
    assert mock_member_instance.email == "updated@example.com"
    assert mock_member_instance.phone == "999-999-9999"
    mock_member_instance.save.assert_called_once()
    assert result == mock_member_instance

def test_unit_update_nonexistent_member(mocker):
    """Test updating a member that doesn't exist (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_get.side_effect = Member.DoesNotExist
    
    payload = MemberUpdateSchema(
        name="This Won't Work",
        email="wont@example.com",
        phone="000-000-0000"
    )
    
    # We expect the exception to be raised and handled by the ninja framework
    with pytest.raises(Member.DoesNotExist):
        update_member(None, "west-coast", NONEXISTENT_ID, payload)
    
    mock_get.assert_called_once_with(id=NONEXISTENT_ID, region__slug="west-coast")

def test_unit_partial_update_member(mocker):
    """Test partially updating a member (unit) - based on current API logic"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_member_instance = mocker.MagicMock(spec=Member)
    mock_member_instance.id = 1
    mock_member_instance.name = "Original Name"
    mock_member_instance.email = "original@example.com"
    mock_member_instance.phone = "111-111-1111"
    mock_get.return_value = mock_member_instance

    # Payload requires 'name'. Email/Phone are optional in schema,
    # but API logic checks for None before updating.
    payload = MemberUpdateSchema(
        name="Partially Updated User",
        email=None, # Explicit None in payload
        phone=None  # Explicit None in payload
    )

    result = update_member(None, "west-coast", 1, payload)

    mock_get.assert_called_once_with(id=1, region__slug="west-coast")
    assert mock_member_instance.name == "Partially Updated User"
    # API logic checks `if payload.email is not None:`, so original value remains
    assert mock_member_instance.email == "original@example.com"
    # API logic checks `if payload.phone is not None:`, so original value remains
    assert mock_member_instance.phone == "111-111-1111"
    mock_member_instance.save.assert_called_once()
    assert result == mock_member_instance

def test_unit_delete_member(mocker):
    """Test deleting a member (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_member_instance = mocker.MagicMock(spec=Member)
    mock_member_instance.id = 1
    mock_get.return_value = mock_member_instance

    result = delete_member(None, "west-coast", 1)

    mock_get.assert_called_once_with(id=1, region__slug="west-coast")
    mock_member_instance.delete.assert_called_once()
    # API now returns the status code directly
    assert result == 200

def test_unit_delete_nonexistent_member(mocker):
    """Test deleting a member that doesn't exist (unit)"""
    mock_get = mocker.patch('tenant_app.api.Member.objects.get')
    mock_get.side_effect = Member.DoesNotExist
    
    # We expect the exception to be raised and handled by the ninja framework
    with pytest.raises(Member.DoesNotExist):
        delete_member(None, "west-coast", NONEXISTENT_ID)
    
    mock_get.assert_called_once_with(id=NONEXISTENT_ID, region__slug="west-coast") 