from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django_multitenant.fields import TenantForeignKey
from django_multitenant.models import TenantModel


class Region(TenantModel):
    # db_constraint=False: Client lives in the public schema; a real FK
    # blocks django-tenants test flush (TRUNCATE public client tables).
    client = models.ForeignKey(
        "shared_app.Client",
        on_delete=models.CASCADE,
        related_name="regions",
        db_constraint=False,
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class TenantMeta:
        tenant_field_name = "client_id"

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.slug = slugify(self.name)
        if not self.slug:
            raise ValidationError(
                {"name": "Region name must contain a letter or number."}
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Member(TenantModel):
    client = models.ForeignKey(
        "shared_app.Client",
        on_delete=models.CASCADE,
        related_name="members",
        db_constraint=False,
    )
    name = models.CharField(max_length=100)
    email = models.TextField(blank=True)
    phone = models.TextField(blank=True)
    region = TenantForeignKey(
        "Region",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="members",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class TenantMeta:
        tenant_field_name = "client_id"

    def __str__(self):
        return self.name
