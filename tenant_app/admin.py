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
