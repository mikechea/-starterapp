import pytest
import json
from tenant_app.models import Member, Region
from django.db import connection

# Mark all tests in this module to use the database
pytestmark = pytest.mark.django_db(transaction=True) # Use transactions for speed

# Constant used in tests
NONEXISTENT_ID = 9999

def member_collection_url(tenant_domain, region_slug):
    """List/create-under-region URL for a region slug."""
    return f'/client/{tenant_domain}/api/region/{region_slug}/member'


def detail_url(tenant_domain, member, region_slug="west-coast"):
    """Helper to get detail URL for a member, including tenant domain prefix"""
    return f'/client/{tenant_domain}/api/region/{region_slug}/member/{member.id}'

def test_list_members(tenant_client, test_tenant, member1, member2):
    """Test listing members in a region"""
    domain = test_tenant.test_domain # Get domain from the tenant fixture
    list_url = member_collection_url(domain, "west-coast")

    response = tenant_client.get(list_url)
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 2

    # Check member data is correct (order might vary, sort by id)
    members_data = sorted(data, key=lambda x: x['id'])
    assert members_data[0]['id'] == member1.id
    assert members_data[0]['name'] == member1.name
    assert members_data[0]['email'] == member1.email
    assert members_data[0]['phone'] == member1.phone
    assert members_data[1]['id'] == member2.id
    assert members_data[1]['name'] == member2.name

def test_create_member(tenant_client, test_tenant):
    """Test creating a new member"""
    domain = test_tenant.test_domain
    list_url = f'/client/{domain}/api/members'

    new_member_data = {
        "name": "New Test User",
        "email": "new@example.com",
        "phone": "555-555-5555",
        "region_name": "West Coast",
    }

    response = tenant_client.post(
        list_url, # Use dynamic URL
        data=json.dumps(new_member_data),
        content_type='application/json'
    )
    data = response.json()

    assert response.status_code == 200
    assert 'id' in data
    assert data['name'] == new_member_data['name']
    assert data['email'] == new_member_data['email']
    assert data['phone'] == new_member_data['phone']
    assert data['region']['name'] == "West Coast"
    assert data['region']['slug'] == "west-coast"

    # Verify in database (ensure connection is still set correctly)
    connection.set_tenant(test_tenant)
    created_member = Member.objects.get(id=data['id'])
    assert created_member.name == new_member_data['name']
    assert created_member.region.slug == "west-coast"
    connection.set_schema_to_public()

def test_create_member_invalid_data(tenant_client, test_tenant):
    """Test creating a member with invalid data (missing required fields)"""
    domain = test_tenant.test_domain
    list_url = f'/client/{domain}/api/members'

    invalid_data = {
        # Missing required 'name' field
        "email": "invalid@example.com",
        "phone": "555-555-5555"
    }

    response = tenant_client.post(
        list_url, # Use dynamic URL
        data=json.dumps(invalid_data),
        content_type='application/json'
    )

    # Assuming Ninja returns 422 for validation errors
    assert response.status_code == 422

def test_get_member(tenant_client, test_tenant, member1):
    """Test retrieving a specific member"""
    domain = test_tenant.test_domain
    url = detail_url(domain, member1) # Pass domain to helper

    response = tenant_client.get(url)
    data = response.json()

    assert response.status_code == 200
    assert data['id'] == member1.id
    assert data['name'] == member1.name
    assert data['email'] == member1.email
    assert data['phone'] == member1.phone

def test_get_nonexistent_member(tenant_client, test_tenant, west_coast_region):
    """Test retrieving a member that doesn't exist"""
    domain = test_tenant.test_domain
    nonexistent_url = f'/client/{domain}/api/region/west-coast/member/{NONEXISTENT_ID}'

    response = tenant_client.get(nonexistent_url)
    # Assuming Ninja returns 404 when Member.DoesNotExist is caught by its handler
    assert response.status_code == 404

def test_update_member(tenant_client, test_tenant, member1):
    """Test updating a member"""
    domain = test_tenant.test_domain
    url = detail_url(domain, member1) # Pass domain to helper

    update_data = {
        "name": "Updated Test User",
        "email": "updated@example.com",
        "phone": "999-999-9999"
    }

    response = tenant_client.put(
        url,
        data=json.dumps(update_data),
        content_type='application/json'
    )
    data = response.json()

    assert response.status_code == 200
    assert data['name'] == update_data['name']
    assert data['email'] == update_data['email']
    assert data['phone'] == update_data['phone']

    # Verify in database
    connection.set_tenant(test_tenant)
    updated_member = Member.objects.get(id=member1.id)
    assert updated_member.name == update_data['name']
    assert updated_member.email == update_data['email']
    assert updated_member.phone == update_data['phone']
    connection.set_schema_to_public()

def test_update_nonexistent_member(tenant_client, test_tenant, west_coast_region):
    """Test updating a member that doesn't exist"""
    domain = test_tenant.test_domain
    nonexistent_url = f'/client/{domain}/api/region/west-coast/member/{NONEXISTENT_ID}'

    update_data = {
        "name": "This Won't Work",
        "email": "wont@example.com",
        "phone": "000-000-0000"
    }

    response = tenant_client.put(
        nonexistent_url, # Use dynamic URL
        data=json.dumps(update_data),
        content_type='application/json'
    )
    assert response.status_code == 404

def test_update_member_invalid_data(tenant_client, test_tenant, member1):
    """Test updating a member with invalid data"""
    domain = test_tenant.test_domain
    url = detail_url(domain, member1) # Pass domain to helper

    invalid_data = {
        # Missing required 'name' field in MemberSchema
        "email": "stillneeded@example.com",
        "phone": "123-123-1234"
    }

    response = tenant_client.put(
        url,
        data=json.dumps(invalid_data),
        content_type='application/json'
    )
    assert response.status_code == 422 # Assuming Ninja validation error

def test_partial_update_member(tenant_client, test_tenant, member1):
    """
    Test partial update of a member.
    NOTE: Your current API PUT handler requires all fields in the payload schema.
    For partial updates (PATCH), you'd typically need a different schema or logic.
    This test assumes the PUT behaves like PATCH if fields are missing in the *payload*,
    which might not be the case depending on Ninja/Pydantic defaults.
    Let's test the behavior of the *current* PUT implementation where name is required.
    If you implement PATCH, you'd adjust this test.
    """
    domain = test_tenant.test_domain
    url = detail_url(domain, member1) # Pass domain to helper

    # Your MemberSchema requires 'name'. Let's provide it.
    # If email/phone are optional in the schema, they can be omitted for PUT.
    update_data = {
        "name": "Partially Updated User",
        # "email": None, # Explicitly setting to None might clear it
        # "phone": None, # Explicitly setting to None might clear it
        # Omitting optional fields if the schema allows
    }

    response = tenant_client.put(
        url,
        data=json.dumps(update_data),
        content_type='application/json'
    )
    data = response.json()

    assert response.status_code == 200

    # Verify in database
    connection.set_tenant(test_tenant)
    updated_member = Member.objects.get(id=member1.id)
    assert updated_member.name == update_data['name']
    # Check if email/phone remained unchanged (depends on API logic)
    assert updated_member.email == member1.email
    assert updated_member.phone == member1.phone
    connection.set_schema_to_public()

def test_delete_member(tenant_client, test_tenant, member1):
    """Test deleting a member"""
    domain = test_tenant.test_domain
    url = detail_url(domain, member1)

    response = tenant_client.delete(url)
    assert response.status_code == 200

    # Verify member was deleted from database
    connection.set_tenant(test_tenant)
    with pytest.raises(Member.DoesNotExist):
        Member.objects.get(id=member1.id)
    connection.set_schema_to_public()

def test_delete_nonexistent_member(tenant_client, test_tenant, west_coast_region):
    """Test deleting a member that doesn't exist"""
    domain = test_tenant.test_domain
    nonexistent_url = f'/client/{domain}/api/region/west-coast/member/{NONEXISTENT_ID}'

    response = tenant_client.delete(nonexistent_url)
    assert response.status_code == 404


def test_create_member_reuses_region_without_renaming(tenant_client, test_tenant):
    """A differently capitalized name matches the existing region and keeps its name."""
    domain = test_tenant.test_domain
    list_url = f'/client/{domain}/api/members'

    first = tenant_client.post(
        list_url,
        data=json.dumps({"name": "Ada Lovelace", "region_name": "West Coast"}),
        content_type='application/json',
    )
    second = tenant_client.post(
        list_url,
        data=json.dumps({"name": "Grace Hopper", "region_name": "west coast"}),
        content_type='application/json',
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['region']['id'] == second.json()['region']['id']
    assert second.json()['region']['name'] == "West Coast"
    assert second.json()['region']['slug'] == "west-coast"

    connection.set_tenant(test_tenant)
    assert Region.objects.count() == 1
    connection.set_schema_to_public()


def test_create_member_requires_region_name(tenant_client, test_tenant):
    domain = test_tenant.test_domain
    list_url = f'/client/{domain}/api/members'

    response = tenant_client.post(
        list_url,
        data=json.dumps({"name": "No Region"}),
        content_type='application/json',
    )

    assert response.status_code == 422
    connection.set_tenant(test_tenant)
    assert Member.objects.count() == 0
    assert Region.objects.count() == 0
    connection.set_schema_to_public()


def test_create_member_rejects_unslugifiable_region_name(tenant_client, test_tenant):
    domain = test_tenant.test_domain
    list_url = f'/client/{domain}/api/members'

    response = tenant_client.post(
        list_url,
        data=json.dumps({"name": "No Region", "region_name": "!!!"}),
        content_type='application/json',
    )

    assert response.status_code == 400
    connection.set_tenant(test_tenant)
    assert Member.objects.count() == 0
    assert Region.objects.count() == 0
    connection.set_schema_to_public()


def test_update_without_region_name_keeps_region(tenant_client, test_tenant):
    domain = test_tenant.test_domain
    list_url = f'/client/{domain}/api/members'
    created = tenant_client.post(
        list_url,
        data=json.dumps({"name": "Ada Lovelace", "region_name": "West Coast"}),
        content_type='application/json',
    )
    member_id = created.json()['id']
    url = f'/client/{domain}/api/region/west-coast/member/{member_id}'

    omitted = tenant_client.put(
        url,
        data=json.dumps({"name": "Ada Lovelace Updated"}),
        content_type='application/json',
    )
    explicit_null = tenant_client.put(
        url,
        data=json.dumps({"name": "Ada Lovelace Updated", "region_name": None}),
        content_type='application/json',
    )

    assert omitted.status_code == 200
    assert omitted.json()['region']['slug'] == "west-coast"
    assert explicit_null.status_code == 200
    assert explicit_null.json()['region']['slug'] == "west-coast"


def test_update_with_region_name_moves_member(tenant_client, test_tenant):
    domain = test_tenant.test_domain
    list_url = f'/client/{domain}/api/members'
    created = tenant_client.post(
        list_url,
        data=json.dumps({"name": "Ada Lovelace", "region_name": "West Coast"}),
        content_type='application/json',
    )
    member_id = created.json()['id']
    url = f'/client/{domain}/api/region/west-coast/member/{member_id}'

    response = tenant_client.put(
        url,
        data=json.dumps({"name": "Ada Lovelace", "region_name": "Pacific"}),
        content_type='application/json',
    )

    assert response.status_code == 200
    assert response.json()['region']['name'] == "Pacific"
    assert response.json()['region']['slug'] == "pacific"

    connection.set_tenant(test_tenant)
    assert Region.objects.filter(slug="west-coast").exists()
    member = Member.objects.get(id=member_id)
    assert member.region.slug == "pacific"
    connection.set_schema_to_public()


def test_update_rejects_unslugifiable_region_name(tenant_client, test_tenant):
    domain = test_tenant.test_domain
    list_url = f'/client/{domain}/api/members'
    created = tenant_client.post(
        list_url,
        data=json.dumps({"name": "Ada Lovelace", "region_name": "West Coast"}),
        content_type='application/json',
    )
    member_id = created.json()['id']
    url = f'/client/{domain}/api/region/west-coast/member/{member_id}'

    response = tenant_client.put(
        url,
        data=json.dumps({"name": "Renamed", "region_name": "!!!"}),
        content_type='application/json',
    )

    assert response.status_code == 400
    connection.set_tenant(test_tenant)
    member = Member.objects.get(id=member_id)
    assert member.name == "Ada Lovelace"
    assert member.region.slug == "west-coast"
    assert Region.objects.count() == 1
    connection.set_schema_to_public() 