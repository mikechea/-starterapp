from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from typing import List, Optional
from .models import Member, Region
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils.text import slugify

api = NinjaAPI(title="Tenant API", urls_namespace="tenant_api")


class RegionResponseSchema(Schema):
    id: int
    name: str
    slug: str


class MemberCreateSchema(Schema):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    region_name: str


class MemberUpdateSchema(Schema):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    region_name: Optional[str] = None


class MemberResponseSchema(Schema):
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    created_at: datetime
    region: Optional[RegionResponseSchema] = None


class ErrorSchema(Schema):
    detail: str


def resolve_region(region_name: str) -> Region:
    """Find a region by the slug of its name, creating it when missing.

    Callers must run this inside transaction.atomic() so a failed member
    write rolls back a region created for that request.
    """
    cleaned = region_name.strip()
    slug = slugify(cleaned)
    if not slug:
        raise HttpError(400, "Region name must contain a letter or number.")
    region, _created = Region.objects.get_or_create(
        slug=slug,
        defaults={"name": cleaned},
    )
    return region


@api.exception_handler(ObjectDoesNotExist)
def object_does_not_exist_handler(request, exc):
    return api.create_response(
        request,
        {"detail": "Object not found."},
        status=404
    )

@api.get("/region/{region}/member", response=List[MemberResponseSchema])
def list_members(request, region: str):
    # The current tenant schema is already set by django-tenants middleware
    Region.objects.get(slug=region)
    return Member.objects.filter(region__slug=region)

@api.post("/members", response=MemberResponseSchema)
def create_member(request, payload: MemberCreateSchema):
    # The current tenant schema is already set by django-tenants middleware
    with transaction.atomic():
        region = resolve_region(payload.region_name)
        member = Member.objects.create(
            name=payload.name,
            phone=payload.phone or "",
            email=payload.email or "",
            region=region,
        )
    return member

@api.get("/region/{region}/member/{member_id}", response=MemberResponseSchema)
def get_member(request, region: str, member_id: int):
    member = Member.objects.get(id=member_id, region__slug=region)
    return member

@api.put("/region/{region}/member/{member_id}", response=MemberResponseSchema)
def update_member(request, region: str, member_id: int, payload: MemberUpdateSchema):
    member = Member.objects.get(id=member_id, region__slug=region)
    with transaction.atomic():
        member.name = payload.name
        if payload.phone is not None:
            member.phone = payload.phone
        if payload.email is not None:
            member.email = payload.email
        if payload.region_name is not None:
            member.region = resolve_region(payload.region_name)
        member.save()
    return member

@api.delete("/region/{region}/member/{member_id}", response={200: None})
def delete_member(request, region: str, member_id: int):
    member = Member.objects.get(id=member_id, region__slug=region)
    member.delete()
    return 200
