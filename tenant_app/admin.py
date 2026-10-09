from django.contrib import admin
from .models import Member, Region

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'region', 'created_at')
    search_fields = ('name', 'email', 'phone')

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    readonly_fields = ('slug',)
