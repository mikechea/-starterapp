# django_multitenant Member/Region Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Stamp `Member` and `Region` with a shared `client` tenant column and make `Member.region` a `TenantForeignKey`, while keeping schema isolation from django-tenants and allowing moves between regions of the same client.

**Architecture:** Both models subclass `TenantModel` with `TenantMeta.tenant_field_name = "client_id"`. Middleware after `TenantSubfolderMiddleware` calls `set_current_tenant(connection.tenant)`. `Client` stays a django-tenants model and exposes `tenant_value` as `self.id`. API create/update continue to resolve regions by slug; they also ensure `client` matches the request tenant.

**Tech Stack:** Django 4.2, django-tenants, django_multitenant 4.x, Django Ninja, pytest.

## Global Constraints

- The django_multitenant tenant is `shared_app.Client`, not `Region`.
- `Member` and `Region` both have non-null `client` foreign keys to `Client`.
- `Member.region` stays nullable (`null=True`, `blank=True`) with `on_delete=PROTECT`, implemented as `TenantForeignKey`.
- `Client` is not turned into a `TenantModel`; it only gains `tenant_value`.
- The API does not accept or return a client id.
- Moving a member between regions of the same client remains allowed.
- Citus / composite primary keys are out of scope.
- django-tenants schema isolation remains in place.
- Spec: `docs/superpowers/specs/2026-10-09-django-multitenant-member-region-design.md`.

## File map

| File | Responsibility |
|------|----------------|
| `requirements.txt` | Pin `django_multitenant` |
| `shared_app/models.py` | `Client.tenant_value` property |
| `tenant_app/models.py` | `TenantModel`, `client` FK, `TenantForeignKey` |
| `tenant_app/middleware.py` | Bridge django-tenants → `set_current_tenant` |
| `starterapp/settings.py` | Install app + middleware |
| `tenant_app/api.py` | Stamp `client` on create/resolve |
| `tenant_app/admin.py` | Show `client` on list displays |
| `tenant_app/migrations/0004_*.py` | Add/backfill/require `client`, state for `TenantForeignKey` |
| `tenant_app/tests/conftest.py` | Fixtures pass `client=test_tenant` |
| `tenant_app/tests/test_region.py` | Existing region tests + client stamp |
| `tenant_app/tests/test_multitenant_client.py` | New django_multitenant association tests |
| `tenant_app/tests/test_unit_members.py` | Unit fixtures include `client_id` |
| `README.md` | Note dependency / dual isolation briefly |

---

### Task 1: Dependency, Client.tenant_value, and middleware

**Files:**
- Modify: `requirements.txt`
- Modify: `shared_app/models.py`
- Create: `tenant_app/middleware.py`
- Modify: `starterapp/settings.py`

**Interfaces:**
- Consumes: `connection.tenant` from django-tenants; `set_current_tenant` / `unset_current_tenant` from `django_multitenant.utils`
- Produces: `Client.tenant_value -> int`; middleware class `DjangoMultitenantMiddleware`

- [ ] **Step 1: Add the dependency**

Append to `requirements.txt`:

```
django_multitenant>=4.1.0,<5.0.0
```

Install into the project venv if needed:

```bash
./venv/bin/pip install 'django_multitenant>=4.1.0,<5.0.0'
```

- [ ] **Step 2: Add `tenant_value` on `Client`**

In `shared_app/models.py`, add this property on `Client` (keep `TenantMixin` as the base):

```python
@property
def tenant_value(self):
    return self.id
```

- [ ] **Step 3: Create the middleware**

Create `tenant_app/middleware.py`:

```python
from django.db import connection
from django_multitenant.utils import set_current_tenant, unset_current_tenant
from django_tenants.utils import get_public_schema_name


class DjangoMultitenantMiddleware:
    """Bridge django-tenants schema selection into django_multitenant."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if (
                getattr(connection, "tenant", None) is not None
                and connection.schema_name != get_public_schema_name()
            ):
                set_current_tenant(connection.tenant)
            response = self.get_response(request)
            return response
        finally:
            unset_current_tenant()
```

- [ ] **Step 4: Wire settings**

In `starterapp/settings.py`:

1. Add `'django_multitenant'` to `SHARED_APPS` (after `'django_tenants'`).
2. Insert `'tenant_app.middleware.DjangoMultitenantMiddleware'` immediately after `'django_tenants.middleware.TenantSubfolderMiddleware'` in `MIDDLEWARE`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt shared_app/models.py tenant_app/middleware.py starterapp/settings.py
git commit -m "$(cat <<'EOF'
Add django_multitenant bridge for Client tenant context.

Client exposes tenant_value, and middleware maps the django-tenants schema tenant into set_current_tenant.
EOF
)"
```

---

### Task 2: Models and migration

**Files:**
- Modify: `tenant_app/models.py`
- Modify: `tenant_app/admin.py`
- Create: `tenant_app/migrations/0004_member_region_client.py` (name from makemigrations is fine)
- Modify: `tenant_app/tests/conftest.py`
- Modify: `tenant_app/tests/test_region.py`
- Create: `tenant_app/tests/test_multitenant_client.py` (failing tests first for model behavior)

**Interfaces:**
- Consumes: `TenantModel`, `TenantForeignKey`, `Client`
- Produces: `Member.client`, `Region.client`, `Member.region` as `TenantForeignKey`

- [ ] **Step 1: Write failing model association tests**

Create `tenant_app/tests/test_multitenant_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
./venv/bin/pytest tenant_app/tests/test_multitenant_client.py -v
```

Expected: FAIL (no `client` field / import or create errors).

- [ ] **Step 3: Update models**

Replace `tenant_app/models.py` with:

```python
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django_multitenant.fields import TenantForeignKey
from django_multitenant.models import TenantModel


class Region(TenantModel):
    client = models.ForeignKey(
        "shared_app.Client",
        on_delete=models.CASCADE,
        related_name="regions",
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
```

- [ ] **Step 4: Update admin**

```python
from django.contrib import admin
from .models import Member, Region


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "region", "client", "created_at")
    search_fields = ("name", "email", "phone")
    readonly_fields = ("client",)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "client", "created_at")
    readonly_fields = ("slug", "client")
```

- [ ] **Step 5: Generate and complete the migration**

```bash
./venv/bin/python manage.py makemigrations tenant_app --name member_region_client
```

Edit the generated migration so it:

1. Adds nullable `client` on `Member` and `Region`.
2. Runs a data migration that sets `client_id` from the `Client` whose `schema_name` matches the schema being migrated (skip the public schema).
3. Alters both `client` fields to `null=False`.
4. Alters `Member.region` to use `django_multitenant.fields.TenantForeignKey` (same `db_column` / FK target; state update).

Data migration function:

```python
from django.db import connection
from django_tenants.utils import get_public_schema_name, schema_context


def populate_client(apps, schema_editor):
    schema_name = connection.schema_name
    if schema_name == get_public_schema_name():
        return

    Client = apps.get_model("shared_app", "Client")
    Region = apps.get_model("tenant_app", "Region")
    Member = apps.get_model("tenant_app", "Member")

    with schema_context(get_public_schema_name()):
        client = Client.objects.get(schema_name=schema_name)

    Region.objects.filter(client_id__isnull=True).update(client_id=client.id)
    Member.objects.filter(client_id__isnull=True).update(client_id=client.id)
```

Apply:

```bash
./venv/bin/python manage.py migrate_schemas --tenant
```

- [ ] **Step 6: Update fixtures and region tests**

In `tenant_app/tests/conftest.py`, pass `client=test_tenant` into every `Region.objects.create` / `get_or_create` / `Member.objects.create`, and into unit `Region(...)` / `Member(...)` constructors (`client_id=1` is fine for unit data).

In `tenant_app/tests/test_region.py`, pass `client=test_tenant` on creates:

```python
region = Region.objects.create(name="  West Coast  ", client=test_tenant)
# ...
Region.objects.create(name="!!!", client=test_tenant)  # still raises
# ...
region = Region.objects.create(name="West Coast", client=test_tenant)
Member.objects.create(name="Ada Lovelace", region=region, client=test_tenant)
```

Wrap DB tests that use managers with `set_current_tenant(test_tenant)` / `unset_current_tenant()` when filters would otherwise hide rows (create paths that rely on auto-stamp). Explicit `client=` on create is required either way.

- [ ] **Step 7: Run model tests**

```bash
./venv/bin/pytest tenant_app/tests/test_multitenant_client.py tenant_app/tests/test_region.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tenant_app/models.py tenant_app/admin.py tenant_app/migrations/ tenant_app/tests/conftest.py tenant_app/tests/test_region.py tenant_app/tests/test_multitenant_client.py
git commit -m "$(cat <<'EOF'
Associate Member and Region with Client via django_multitenant.

Both models store client_id; Member.region is a TenantForeignKey so joins match the same client.
EOF
)"
```

---

### Task 3: API stamping and existing test updates

**Files:**
- Modify: `tenant_app/api.py`
- Modify: `tenant_app/tests/test_unit_members.py`
- Modify: `tenant_app/tests/test_integration_members.py` (only if assertions need client checks)
- Modify: `tenant_app/tests/test_multitenant_client.py` (add API-level test)
- Modify: `README.md`

**Interfaces:**
- Consumes: `connection.tenant` or `get_current_tenant()`; existing `resolve_region`
- Produces: create/update paths that set `client` on new regions and members

- [ ] **Step 1: Add failing API association test**

Append to `tenant_app/tests/test_multitenant_client.py`:

```python
import json


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
```

- [ ] **Step 2: Run it to verify failure or incomplete stamp**

```bash
./venv/bin/pytest tenant_app/tests/test_multitenant_client.py::test_api_create_stamps_member_and_region_with_client -v
```

Expected: FAIL until API + middleware stamp `client` (or FAIL on NOT NULL if create omits client).

- [ ] **Step 3: Update `resolve_region` and create/update**

In `tenant_app/api.py`:

```python
from django.db import connection, transaction
from django_multitenant.utils import get_current_tenant


def _request_client():
    tenant = get_current_tenant() or getattr(connection, "tenant", None)
    if tenant is None:
        raise HttpError(500, "Tenant context is required.")
    return tenant


def resolve_region(region_name: str) -> Region:
    """Find a region by the slug of its name, creating it when missing.

    Callers must run this inside transaction.atomic() so a failed member
    write rolls back a region created for that request.
    """
    cleaned = region_name.strip()
    slug = slugify(cleaned)
    if not slug:
        raise HttpError(400, "Region name must contain a letter or number.")
    client = _request_client()
    region, _created = Region.objects.get_or_create(
        slug=slug,
        defaults={"name": cleaned, "client": client},
    )
    return region


@api.post("/members", response=MemberResponseSchema)
def create_member(request, payload: MemberCreateSchema):
    with transaction.atomic():
        region = resolve_region(payload.region_name)
        member = Member.objects.create(
            name=payload.name,
            phone=payload.phone or "",
            email=payload.email or "",
            region=region,
            client=_request_client(),
        )
    return member
```

Leave update/move logic as-is (region change only). Do not change `client` on update.

- [ ] **Step 4: Fix unit tests**

In `tenant_app/tests/test_unit_members.py`:

- Give unit `Region` / `Member` instances a `client_id` (for example `1`).
- Keep mocking `transaction.atomic`.
- When testing create, assert `Member.objects.create` is called with `client=` equal to the patched current tenant, or patch `_request_client` / `get_current_tenant` to return an object with `id=1` and assert that id is passed.

Example autouse addition alongside the existing atomic mock:

```python
@pytest.fixture(autouse=True)
def _tenant_context(mocker):
    mocker.patch("tenant_app.api.transaction.atomic")
    client = mocker.Mock(id=1)
    mocker.patch("tenant_app.api.get_current_tenant", return_value=client)
    mocker.patch("tenant_app.api._request_client", return_value=client)
```

Adjust create assertion:

```python
mock_create.assert_called_once_with(
    name="New Test User",
    email="new@example.com",
    phone="555-555-5555",
    region=region,
    client=mocker.ANY,  # or the same client mock
)
```

Prefer asserting the exact client mock returned by `_request_client`.

- [ ] **Step 5: Run the focused and full suites**

```bash
./venv/bin/pytest tenant_app/tests/test_multitenant_client.py tenant_app/tests/test_unit_members.py tenant_app/tests/test_integration_members.py tenant_app/tests/test_tenant_isolation.py tenant_app/tests/test_region.py -v
./venv/bin/pytest
```

Expected: PASS.

- [ ] **Step 6: README note**

In `README.md`, under Structure or Additional Notes, add one short note:

```markdown
- Tenant rows are isolated by django-tenants schemas. Inside a schema, `Member` and `Region` also store a `client` foreign key used by django_multitenant so `Member.region` joins match the same client.
```

Add `django_multitenant` to the opening sentence that lists django-tenants / Django Ninja if that sentence exists.

- [ ] **Step 7: Commit**

```bash
git add tenant_app/api.py tenant_app/tests/test_multitenant_client.py tenant_app/tests/test_unit_members.py tenant_app/tests/conftest.py README.md
git commit -m "$(cat <<'EOF'
Stamp member and region creates with the request client.

API resolve/create paths set client from the current tenant so TenantForeignKey joins stay consistent.
EOF
)"
```

---

### Task 4: Verify end-to-end

**Files:** none beyond fixes discovered while verifying

- [ ] **Step 1: Run the full test suite**

```bash
./venv/bin/pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Smoke the create path with the running server (optional)**

With `runserver` and tenant `tenant1`:

```bash
curl -s -X POST http://localhost:8000/client/tenant1/api/members \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ada Lovelace","region_name":"West Coast"}'
```

Expected: HTTP 200 JSON including `"region":{"name":"West Coast","slug":"west-coast",...}`.

- [ ] **Step 3: Commit any leftover fixes** (only if Step 1 or 2 forced small repairs)

```bash
git add -A
git commit -m "$(cat <<'EOF'
Fix leftover django_multitenant integration issues from verification.
EOF
)"
```

Skip this commit if the working tree is clean.

---

## Spec coverage check

| Spec requirement | Task |
|------------------|------|
| `TenantModel` + `client` on Member/Region | Task 2 |
| `TenantForeignKey` for `Member.region` | Task 2 |
| `Client.tenant_value` | Task 1 |
| Middleware `set_current_tenant` | Task 1 |
| API stamps client; no client in body/response | Task 3 |
| Move between regions same client | Task 2 + existing update tests |
| Migration backfill by schema_name | Task 2 |
| Admin shows client | Task 2 |
| Tests for stamp, filter, move, fixtures | Tasks 2–3 |
| Out of scope: Citus, Client as TenantModel, region-as-tenant | Not planned |
