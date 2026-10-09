import pytest
from django.test import Client
from django.db import connection
from django_tenants.test.client import TenantClient
from django_tenants.utils import get_public_schema_name

# Assuming your tenant model is Client from shared_app
# Adjust imports based on your actual project structure
from shared_app.models import Client as Tenant, Domain
from ..models import Member, Region

@pytest.fixture(scope='function') # Use 'function' scope for isolation between tests
def test_tenant(db, django_db_blocker):
    """
    Creates a tenant for testing within a transaction.
    Relies on the 'db' fixture from pytest-django.
    """
    # Ensure we're in the public schema before creating tenants
    connection.set_schema_to_public()
    tenant_domain = 'test' # Define domain here to reuse
    with django_db_blocker.unblock():
        # Create the tenant
        tenant = Tenant.objects.create(
            schema_name='test',
            name='Test Tenant'
            # Add any other required fields for your Tenant model
        )
        # Add a domain for the tenant
        Domain.objects.create(
            tenant=tenant,
            domain=tenant_domain, # Use the variable
            is_primary=True
        )
    # Store the domain on the tenant object for the client fixture to use
    tenant.test_domain = tenant_domain
    connection.set_tenant(tenant)
    Member.objects.all().delete()
    Region.objects.all().delete()
    connection.set_schema_to_public()
    yield tenant
    # Ensure schema is reset if any direct connection manipulation happened post-yield
    connection.set_schema_to_public()

@pytest.fixture(scope='function')
def another_tenant(db, django_db_blocker):
    """
    Creates a second tenant for isolation testing.
    Relies on the 'db' fixture from pytest-django.
    """
    # Ensure we're in the public schema before creating tenants
    connection.set_schema_to_public()
    tenant_domain = 'another' # Different domain from test_tenant
    with django_db_blocker.unblock():
        # Create the tenant with a different schema_name
        tenant = Tenant.objects.create(
            schema_name='another',
            name='Another Test Tenant'
        )
        # Add a domain for the second tenant
        Domain.objects.create(
            tenant=tenant,
            domain=tenant_domain,
            is_primary=True
        )
    # Store the domain on the tenant object for the client fixture to use
    tenant.test_domain = tenant_domain
    connection.set_tenant(tenant)
    Member.objects.all().delete()
    Region.objects.all().delete()
    connection.set_schema_to_public()
    yield tenant
    # Teardown handled by transaction rollback and schema reset
    connection.set_schema_to_public()

@pytest.fixture
def tenant_client(test_tenant):
    """
    Provides a Django test client configured for the specific test tenant.
    Uses TenantClient to ensure tenant routing works correctly.
    """
    # Use TenantClient instead of the standard Client
    client = TenantClient(test_tenant)
    
    # Set SERVER_NAME so the middleware can identify the tenant by domain
    client.defaults['SERVER_NAME'] = test_tenant.test_domain
    yield client
    # Reset connection after test finishes using the client
    connection.set_schema_to_public()

@pytest.fixture
def another_tenant_client(another_tenant):
    """
    Provides a Django test client configured for the second test tenant.
    Similar to tenant_client but for testing cross-tenant scenarios.
    """
    client = TenantClient(another_tenant)
    client.defaults['SERVER_NAME'] = another_tenant.test_domain
    yield client
    connection.set_schema_to_public()

@pytest.fixture
def west_coast_region(test_tenant):
    """Shared region used by member fixtures that need path-scoped URLs."""
    connection.set_tenant(test_tenant)
    region, _created = Region.objects.get_or_create(
        slug="west-coast",
        defaults={"name": "West Coast", "client": test_tenant},
    )
    connection.set_schema_to_public()
    return region

@pytest.fixture
def member1(test_tenant, west_coast_region):
    """Creates the first Member instance within the test tenant's schema."""
    connection.set_tenant(test_tenant)
    member = Member.objects.create(
        name="Test User 1",
        email="test1@example.com",
        phone="123-456-7890",
        region=west_coast_region,
        client=test_tenant,
    )
    connection.set_schema_to_public()
    return member

@pytest.fixture
def member2(test_tenant, west_coast_region):
    """Creates the second Member instance within the test tenant's schema."""
    connection.set_tenant(test_tenant)
    member = Member.objects.create(
        name="Test User 2",
        email="test2@example.com",
        phone="098-765-4321",
        region=west_coast_region,
        client=test_tenant,
    )
    connection.set_schema_to_public()
    return member

# --- Fixtures for Unit Tests ---

@pytest.fixture
def member1_unit_data():
    """Provides data for the first member for unit tests (no DB interaction)."""
    region = Region(id=4, name="West Coast", slug="west-coast", client_id=1)
    return Member(
        id=1,
        name="Test User 1",
        email="test1@example.com",
        phone="123-456-7890",
        region=region,
        client_id=1,
    )

@pytest.fixture
def member2_unit_data():
    """Provides data for the second member for unit tests (no DB interaction)."""
    region = Region(id=4, name="West Coast", slug="west-coast", client_id=1)
    return Member(
        id=2,
        name="Test User 2",
        email="test2@example.com",
        phone="098-765-4321",
        region=region,
        client_id=1,
    ) 