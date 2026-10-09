# Member regions implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Assign a region when a member is created, and allow update to move that member by region name.

**Architecture:** `Region.save()` derives `slug` from `name`. The member API resolves a region by that slug inside `transaction.atomic()`, creating the region only when the slug is new. Create requires `region_name`. Update changes the region only when `region_name` is sent.

**Tech Stack:** Django 4.2, django-tenants, Django Ninja, pytest.

## Global Constraints

- `Member.region` is nullable (`null=True`, `blank=True`) with `on_delete=PROTECT`.
- Do not backfill existing members and do not set `null=False`.
- `POST /members` requires `region_name`. Missing is 422.
- `PUT /members/{id}` treats omitted or JSON `null` `region_name` as "keep the current region".
- Lookup identity is `slugify(name)`. Reuse does not rename the region.
- Slug is not client input. It changes only when `Region.name` is saved.
- `Region.slug` max length is 100.
- Create and update return HTTP 200.
- Blank or unslugifiable region names return 400 and roll back.
- No region API.

---

### Task 1: Region slug and member foreign key

**Files:**
- Modify: `tenant_app/models.py`
- Modify: `tenant_app/admin.py`
- Create: `tenant_app/migrations/0003_member_region.py`
- Test: `tenant_app/tests/test_region.py`

- [x] Add `Region.save()` that strips `name`, sets `slug = slugify(name)`, and raises `ValidationError` when the slug is empty.
- [x] Widen `slug` to `max_length=100`.
- [x] Add nullable `Member.region` foreign key with `PROTECT`.
- [x] Register `Region` in admin with `slug` read-only, and show `region` on `MemberAdmin`.
- [x] Generate the tenant migration with `makemigrations`.
- [x] Test slug rewrite, rejected empty slug, and protected delete.

### Task 2: Member API

**Files:**
- Modify: `tenant_app/api.py`
- Modify: `tenant_app/tests/test_unit_members.py`
- Modify: `tenant_app/tests/test_integration_members.py`
- Modify: `tenant_app/tests/test_tenant_isolation.py`
- Modify: `README.md`

- [x] Split `MemberCreateSchema` (`region_name` required) from `MemberUpdateSchema` (`region_name` optional).
- [x] Add `region` to `MemberResponseSchema`.
- [x] `resolve_region()` slugifies, returns 400 when empty, and `get_or_create`s by slug inside the caller's transaction.
- [x] Create and update wrap region resolution and the member write in `transaction.atomic()`.
- [x] Update existing member tests so create sends `region_name`, and cover reuse, 422, 400, keep, and move.
- [x] Document `region_name` on the member endpoints in the README.

### Task 3: Verify

- [x] Run `pytest`.
