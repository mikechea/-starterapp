import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models.deletion import ProtectedError

from tenant_app.models import Member, Region

pytestmark = pytest.mark.django_db(transaction=True)


def test_saving_region_name_rewrites_slug(test_tenant):
    connection.set_tenant(test_tenant)
    region = Region.objects.create(name="  West Coast  ")

    assert region.name == "West Coast"
    assert region.slug == "west-coast"

    region.name = "Pacific"
    region.save()
    region.refresh_from_db()

    assert region.slug == "pacific"
    connection.set_schema_to_public()


def test_region_name_without_slug_is_rejected(test_tenant):
    connection.set_tenant(test_tenant)
    with pytest.raises(ValidationError):
        Region.objects.create(name="!!!")

    assert Region.objects.count() == 0
    connection.set_schema_to_public()


def test_region_with_members_cannot_be_deleted(test_tenant):
    connection.set_tenant(test_tenant)
    region = Region.objects.create(name="West Coast")
    Member.objects.create(name="Ada Lovelace", region=region)

    with pytest.raises(ProtectedError):
        region.delete()

    assert Region.objects.filter(pk=region.pk).exists()
    assert Member.objects.filter(name="Ada Lovelace").exists()
    connection.set_schema_to_public()
