# django_multitenant for Member and Region

## Goal

Associate `Member` and `Region` with `django_multitenant` so both rows carry the same client tenant column, and `Member.region` is a `TenantForeignKey`. Schema isolation from `django-tenants` stays in place. A member can still move between regions that belong to the same client.

## Decisions

- The django_multitenant tenant is the existing `shared_app.Client`, not `Region`.
- `Member` and `Region` both subclass `TenantModel` and store a non-null `client` foreign key to `Client` with `db_constraint=False` (Client is in the public schema; a real FK breaks django-tenants test flush).
- Both models set `TenantMeta.tenant_field_name = "client_id"`.
- `Member.region` becomes a `TenantForeignKey` (still nullable, `blank=True`, `on_delete=PROTECT`).
- `Client` stays a `django_tenants` `TenantMixin` model. It is not turned into a `TenantModel`. It gains a `tenant_value` property that returns `self.id`, which `django_multitenant` needs when the current tenant is a `Client` instance.
- The API does not accept a client id. Create and update stamp `client` from the schema already selected by django-tenants.
- Middleware after `TenantSubfolderMiddleware` calls `set_current_tenant(connection.tenant)` on tenant requests and clears it afterward. Public-schema routes leave the django_multitenant tenant unset.
- Moving a member between regions of the same client remains allowed. Changing `client_id` on an existing row is still rejected by `django_multitenant` (`NotSupportedError`).
- Citus distribution and composite primary keys are out of scope.

## Why not Region-as-tenant

If `region_id` were the tenant column, `TenantModel.save()` would refuse region changes after create. That would break the existing move-by-`region_name` update. A shared `client_id` keeps moves within one client and still enforces that a member only joins a region with the same client.

## Models

```python
# Member and Region (shape, not final file)
class Region(TenantModel):
    client = models.ForeignKey("shared_app.Client", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class TenantMeta:
        tenant_field_name = "client_id"

class Member(TenantModel):
    client = models.ForeignKey("shared_app.Client", on_delete=models.CASCADE)
    region = TenantForeignKey(
        "Region",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="members",
    )
    # name, email, phone, created_at unchanged

    class TenantMeta:
        tenant_field_name = "client_id"
```

`Region.save()` still strips `name`, sets `slug = slugify(name)`, and rejects empty slugs. Reusing a region by slug does not rename it. `slug` uniqueness stays schema-local.

`Client` adds:

```python
@property
def tenant_value(self):
    return self.id
```

## Request lifecycle

1. `TenantSubfolderMiddleware` selects the Postgres schema and sets `connection.tenant` to a `Client`.
2. New middleware sets `set_current_tenant(connection.tenant)` when the connection is on a tenant schema, and calls `unset_current_tenant()` on the way out.
3. `Member.objects` / `Region.objects` filter by `client_id` when a current tenant is set.
4. `TenantForeignKey` joins and descriptor loads also match `client_id` on both sides.

Public routes (`/api/clients`, `/api/domains`, public admin) do not set the django_multitenant tenant.

## API behavior (unchanged surface)

- `POST /members` still requires `region_name`. Resolve or create the region, then create the member, both stamped with the request client, inside `transaction.atomic()`.
- List, get, update, and delete stay under `/region/{region}/member...` and still filter by region slug.
- Update still moves a member when `region_name` is sent, and leaves the region alone when it is omitted or JSON `null`.
- Responses still include `region` as `{ id, name, slug }` or `null`. They do not expose `client`.

## Migration

Add `django_multitenant` to `requirements.txt` and install it in the project.

Add a tenant migration after `0003_member_region`:

1. Add nullable `client` on `Member` and `Region`.
2. Data migration: for each tenant schema, set `client_id` to the `Client` whose `schema_name` matches the schema being migrated.
3. Alter `client` to non-null on both models.
4. Alter `Member.region` to `TenantForeignKey` (same database column; migration state update).

Existing region-less members keep `region=null` and receive the schema's client. Tenants with no members or regions are unchanged aside from the new column definition for future rows.

## Admin

- Show `client` on Member and Region admin list displays (read-only is fine; values come from the request schema in normal use).
- Slug on Region stays read-only.

## Tests

- A created member and its region share the request client's id.
- Create that reuses a region by slug still works; both rows share the same client.
- Update that moves a member between two regions of the same client still works.
- While the current tenant is set, `Region.objects` does not return a region row stamped with a different `client_id`.
- Existing member API, region, and tenant-isolation tests keep passing once fixtures stamp `client` from the test tenant.
- Unit tests that call views without middleware set `set_current_tenant` (or mock as needed) so `TenantForeignKey` / manager filters do not warn or filter incorrectly.

## Out of scope

- Making `Client` a `TenantModel`.
- Region-as-tenant (option 1).
- Citus / distributed tables / composite primary keys.
- A client id in request or response bodies.
- Changing region slug uniqueness to include `client_id` (schemas already isolate rows).
- Removing django-tenants schema isolation.
