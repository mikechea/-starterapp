import json

import pytest
from django.db import connection
from django_multitenant.utils import set_current_tenant, unset_current_tenant

from tenant_app.models import Member, Region

pytestmark = pytest.mark.django_db(transaction=True)


def test_created_member_and_region_share_request_client(test_tenant):
    connection.set_tenant(test_tenant)
    set_current_tenant(test_tenant)
    try:
        region = Region.objects.create(name="West Coast", client=test_tenant)
        member = Member.objects.create(
            name="Ada Lovelace",
            region=region,
            client=test_tenant,
        )
        assert member.client_id == test_tenant.id
        assert region.client_id == test_tenant.id
        assert member.region_id == region.id
    finally:
        unset_current_tenant()
        connection.set_schema_to_public()


def test_region_queryset_filters_by_current_client(test_tenant, another_tenant):
    connection.set_tenant(test_tenant)
    set_current_tenant(test_tenant)
    try:
        Region.objects.create(name="West Coast", client=test_tenant)
        Region.objects.create(name="Other Client Region", client=test_tenant)
        Region.objects.filter(slug="other-client-region").update(
            client_id=another_tenant.id
        )
        visible = list(Region.objects.values_list("slug", flat=True))
        assert "west-coast" in visible
        assert "other-client-region" not in visible
    finally:
        unset_current_tenant()
        connection.set_schema_to_public()


def test_member_can_move_between_regions_of_same_client(test_tenant):
    connection.set_tenant(test_tenant)
    set_current_tenant(test_tenant)
    try:
        west = Region.objects.create(name="West Coast", client=test_tenant)
        pacific = Region.objects.create(name="Pacific", client=test_tenant)
        member = Member.objects.create(
            name="Ada Lovelace",
            region=west,
            client=test_tenant,
        )
        member.region = pacific
        member.save()
        member.refresh_from_db()
        assert member.region.slug == "pacific"
        assert member.client_id == test_tenant.id
    finally:
        unset_current_tenant()
        connection.set_schema_to_public()


def test_api_create_stamps_member_and_region_with_client(tenant_client, test_tenant):
    domain = test_tenant.test_domain
    response = tenant_client.post(
        f"/client/{domain}/api/members",
        data=json.dumps(
            {
                "name": "Ada Lovelace",
                "region_name": "West Coast",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["region"]["slug"] == "west-coast"

    connection.set_tenant(test_tenant)
    set_current_tenant(test_tenant)
    try:
        member = Member.objects.get(id=body["id"])
        assert member.client_id == test_tenant.id
        assert member.region.client_id == test_tenant.id
    finally:
        unset_current_tenant()
        connection.set_schema_to_public()
