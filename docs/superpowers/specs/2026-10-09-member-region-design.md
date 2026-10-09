# Member regions

## Goal

When a member is created, the tenant API accepts a region name, finds or creates that region, and assigns it to the member. The lookup, create, and assignment run in one database transaction. A member update can move the member to another region by name, or leave the current region unchanged.

Regions stay tenant-scoped in `tenant_app`. There is no region API. Renaming a region stays in Django admin.

## Decisions

- A member has at most one region in this change. `Member.region` is a foreign key with `null=True` and `blank=True`. `on_delete` is `PROTECT`.
- The column stays nullable. This change does not backfill existing members and does not set `null=False`. A later migration can backfill and then make the foreign key required.
- The create API is stricter than the column. `POST /members` requires `region_name`.
- `PUT /members/{id}` treats `region_name` as optional. Omitting it keeps the member's current region, including null. Sending it moves the member.
- Region identity at creation time is the slug derived from the name. `West Coast` and `west coast` are the same region.
- Reusing a region does not change its stored name.
- The slug is not client input. `Region.save()` sets it from `name` immediately before writing the row. It changes only when `Region.name` is saved.
- Moving a member does not delete the region they left.

## Data model

`Region` keeps `name` (`CharField`, max length 100), `slug` (`SlugField`, unique), and `created_at`. `slug` max length becomes 100 so a slugified name can fit.

`Region.save()` strips `name`, sets `slug = slugify(name)`, then saves. If the slug is empty, `save()` raises `ValidationError` and does not write the row.

`Member.region` references `Region`. Deleting a region that still has members fails. Deleting a member does not delete its region.

Django admin:

- Register `Region` with name, slug, and created time. Slug is read-only.
- Show `region` on the member admin.

## Member API

Create and update use separate request schemas. The current shared schema would make `region_name` required on update.

`POST /members` body:

- `name` (required)
- `email` (optional)
- `phone` (optional)
- `region_name` (required)

`PUT /members/{id}` body:

- `name` (required, unchanged from today)
- `email` (optional)
- `phone` (optional)
- `region_name` (optional)

Neither request accepts a slug.

List, get, update, and delete are scoped by region slug:

- `GET /region/{region}/member`
- `GET /region/{region}/member/{member_id}`
- `PUT /region/{region}/member/{member_id}`
- `DELETE /region/{region}/member/{member_id}`

`{region}` is the region slug. List returns only members in that region and 404s if the region does not exist. Get, put, and delete 404 if the member is not in that region. Create stays on `/members`.

List and detail responses add `region`. It is `null` or:

```json
{ "id": 3, "name": "West Coast", "slug": "west-coast" }
```

Create and update continue to return HTTP 200, matching the existing member API. A missing `region_name` on create is a 422 validation error. There is no `POST` or `PATCH` for regions.

## Transaction

When `region_name` is present, this runs inside `transaction.atomic()`:

1. Strip the name. `slug = slugify(name)`.
2. If `slug` is empty, raise a 400 and roll back. Nothing is written.
3. Look up `Region` by `slug`.
4. If none exists, create it with the stripped name. `save()` writes the slug.
5. On create, create the member with that region. On update, set `member.region` and save the member's other fields in the same transaction.

If two requests create the same new slug at once, one insert wins and the other reuses that row.

If `region_name` is omitted or JSON `null` on update, the handler does not touch `member.region`.

Regions live in the tenant schema, same as members. A region created for one tenant is not visible to another.

A reused region's name stays as first saved. The next member created with `West Coast` after an admin rename to `Pacific` creates a new region, because the slug is now `pacific`. Existing members stay on the renamed row because the foreign key stores the region id.

## Errors

- Create without `region_name`: 422.
- Create or update with a blank name, or a name that slugifies to nothing: 400, transaction rolled back.
- Unknown member id: existing 404 behavior.
- Admin rename whose new slug is already taken: the unique constraint rejects the save. No API behavior for this.

## Migration

Add a tenant migration after `0002_region`:

- Change `Region.slug` max length from 50 to 100.
- Add nullable `Member.region`.

Existing members remain region-less. Tenants with no members are unchanged.

## Tests

- Create with a new region name creates the region, assigns it, and returns the region object.
- Create with a different capitalization reuses the region and does not change its name.
- Create without `region_name` returns 422 and writes nothing.
- Create or update with an unslugifiable region name returns 400 and writes nothing.
- Update without `region_name`, or with JSON `null`, keeps the current region.
- Update with `region_name` moves the member, creating the region when needed.
- Saving a new `Region.name` rewrites `slug`.
- A region that still has members cannot be deleted.

## Out of scope

- A region list, create, or rename API.
- Backfill of existing members.
- Making `Member.region` non-null.
- Deleting a region when its last member leaves.
