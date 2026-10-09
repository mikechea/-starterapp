import pytest
import json
from django.db import connection
from tenant_app.models import Member, Region

# Mark all tests to use database
pytestmark = pytest.mark.django_db(transaction=True)

def test_api_endpoint_isolation(tenant_client, another_tenant_client, test_tenant, another_tenant):
    """Test that API endpoints respect tenant isolation by using API calls"""
    # ----- First Tenant Direct DB Operations -----
    # Set connection to first tenant
    connection.set_tenant(test_tenant)
    
    # Delete any existing members to start clean
    Member.objects.all().delete()
    
    # Create a member directly in first tenant's database
    member_a_db = Member.objects.create(
        name="Direct DB Tenant A Member",
        email="direct_a@example.com",
        phone="111-111-1111"
    )
    
    # Verify there's only one member
    assert Member.objects.count() == 1
    
    # ----- Second Tenant Direct DB Operations -----
    # Set connection to second tenant
    connection.set_tenant(another_tenant)
    
    # Delete any existing members to start clean
    Member.objects.all().delete()
    
    # Create a member directly in second tenant's database
    member_b_db = Member.objects.create(
        name="Direct DB Tenant B Member",
        email="direct_b@example.com",
        phone="222-222-2222"
    )
    
    # Verify there's only one member
    assert Member.objects.count() == 1
    
    # ----- Now test API isolation -----
    # Create a member through the API in the first tenant
    domain_a = test_tenant.test_domain
    list_url_a = f'/client/{domain_a}/api/members'
    
    new_member_data_a = {
        "name": "Tenant A API Member",
        "email": "api_member_a@example.com",
        "phone": "333-333-3333",
        "region_name": "Tenant A",
    }
    
    response_create_a = tenant_client.post(
        list_url_a,
        data=json.dumps(new_member_data_a),
        content_type='application/json'
    )
    assert response_create_a.status_code == 200
    member_a_data = response_create_a.json()
    member_a_id = member_a_data['id']
    
    # Create a member through the API in the second tenant
    domain_b = another_tenant.test_domain
    list_url_b = f'/client/{domain_b}/api/members'
    
    new_member_data_b = {
        "name": "Tenant B API Member", # Distinct name for validation
        "email": "api_member_b@example.com", # Distinct email for validation
        "phone": "444-444-4444", # Distinct phone for validation
        "region_name": "Tenant B",
    }
    
    response_create_b = another_tenant_client.post(
        list_url_b,
        data=json.dumps(new_member_data_b),
        content_type='application/json'
    )
    assert response_create_b.status_code == 200
    member_b_data = response_create_b.json()
    member_b_id = member_b_data['id']
    
    # Verify first tenant's database now has 2 members (1 direct + 1 API)
    connection.set_tenant(test_tenant)
    assert Member.objects.count() == 2
    member_names_a_db = list(Member.objects.values_list('name', flat=True))
    assert "Direct DB Tenant A Member" in member_names_a_db
    assert "Tenant A API Member" in member_names_a_db

    # Verify second tenant's database now has 2 members (1 direct + 1 API)
    connection.set_tenant(another_tenant)
    assert Member.objects.count() == 2
    member_names_b_db = list(Member.objects.values_list('name', flat=True))
    assert "Direct DB Tenant B Member" in member_names_b_db
    assert "Tenant B API Member" in member_names_b_db
    assert Region.objects.filter(slug="tenant-a").count() == 0
    assert Region.objects.filter(slug="tenant-b").count() == 1

    # Test first tenant API access to its own data
    url_a = f'/client/{domain_a}/api/region/tenant-a/member/{member_a_id}'
    response_a = tenant_client.get(url_a)
    assert response_a.status_code == 200
    response_a_data = response_a.json()
    assert response_a_data['name'] == "Tenant A API Member"

    # Test first tenant CANNOT access second tenant's data (expect 404)
    url_b_from_a = f'/client/{domain_a}/api/region/tenant-b/member/{member_b_id}'
    response_a_to_b = tenant_client.get(url_b_from_a)
    assert response_a_to_b.status_code == 404 # Primary assertion

    # Test second tenant can access its own data
    url_b = f'/client/{domain_b}/api/region/tenant-b/member/{member_b_id}'
    response_b = another_tenant_client.get(url_b)
    assert response_b.status_code == 200
    response_b_data = response_b.json()
    assert response_b_data['name'] == "Tenant B API Member"

    # Test second tenant CANNOT access first tenant's data (expect 404)
    url_a_from_b = f'/client/{domain_b}/api/region/tenant-a/member/{member_a_id}'
    response_b_to_a = another_tenant_client.get(url_a_from_b)
    assert response_b_to_a.status_code == 404 # Primary assertion

    # Reset connection to public schema
    connection.set_schema_to_public()
    
    print("\nTenant isolation test completed successfully!")
    # The test passes if tenant isolation is confirmed via content verification, not necessarily status codes

def test_list_endpoint_isolation(tenant_client, another_tenant_client, test_tenant, another_tenant):
    """Test that list endpoints only show data for the current tenant"""
    # First, clean up existing data
    connection.set_tenant(test_tenant)
    Member.objects.all().delete()
    
    connection.set_tenant(another_tenant)
    Member.objects.all().delete()
    
    # Create members through the API in the first tenant
    domain_a = test_tenant.test_domain
    create_url_a = f'/client/{domain_a}/api/members'
    list_url_a = f'/client/{domain_a}/api/region/tenant-a/member'
    
    # Create two members in first tenant with distinctive names
    tenant_a_members = [
        {
            "name": "Tenant A List Member 1",
            "email": "list_a1@example.com",
            "phone": "555-555-5551",
            "region_name": "Tenant A",
        },
        {
            "name": "Tenant A List Member 2",
            "email": "list_a2@example.com",
            "phone": "555-555-5552",
            "region_name": "Tenant A",
        }
    ]
    
    for member_data in tenant_a_members:
        response = tenant_client.post(
            create_url_a,
            data=json.dumps(member_data),
            content_type='application/json'
        )
        assert response.status_code == 200
    
    # Create members through the API in the second tenant with distinctive names
    domain_b = another_tenant.test_domain
    create_url_b = f'/client/{domain_b}/api/members'
    list_url_b = f'/client/{domain_b}/api/region/tenant-b/member'
    
    # Create three members in second tenant
    tenant_b_members = [
        {
            "name": "Tenant B List Member 1",
            "email": "list_b1@example.com",
            "phone": "666-666-6661",
            "region_name": "Tenant B",
        },
        {
            "name": "Tenant B List Member 2",
            "email": "list_b2@example.com",
            "phone": "666-666-6662",
            "region_name": "Tenant B",
        },
        {
            "name": "Tenant B List Member 3",
            "email": "list_b3@example.com",
            "phone": "666-666-6663",
            "region_name": "Tenant B",
        }
    ]
    
    for member_data in tenant_b_members:
        response = another_tenant_client.post(
            create_url_b,
            data=json.dumps(member_data),
            content_type='application/json'
        )
        assert response.status_code == 200
    
    # Verify direct database counts
    connection.set_tenant(test_tenant)
    tenant_a_count = Member.objects.count()
    assert tenant_a_count == 2, f"Expected 2 members in tenant A, but got {tenant_a_count}"
    
    connection.set_tenant(another_tenant)
    tenant_b_count = Member.objects.count()
    assert tenant_b_count == 3, f"Expected 3 members in tenant B, but got {tenant_b_count}"
    
    # Test first tenant list endpoint - should only see tenant A's members
    response_a = tenant_client.get(list_url_a)
    assert response_a.status_code == 200
    data_a = response_a.json()
    member_names_a = [member['name'] for member in data_a]
    # Verify tenant A only sees its own members
    assert len(data_a) == 2 # Check count if reliable
    assert all(name.startswith("Tenant A") for name in member_names_a), "Should only see Tenant A members"
    assert not any(name.startswith("Tenant B") for name in member_names_a), "Should not see any Tenant B members"
    
    # Test second tenant list endpoint - should only see tenant B's members
    response_b = another_tenant_client.get(list_url_b)
    assert response_b.status_code == 200
    data_b = response_b.json()
    member_names_b = [member['name'] for member in data_b]
    # Verify tenant B only sees its own members
    assert len(data_b) == 3 # Check count if reliable
    assert all(name.startswith("Tenant B") for name in member_names_b), "Should only see Tenant B members"
    assert not any(name.startswith("Tenant A") for name in member_names_b), "Should not see any Tenant A members"
    
    # Reset connection to public schema
    connection.set_schema_to_public() 