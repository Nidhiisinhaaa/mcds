from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import PatientProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ["username", "email", "role", "is_staff", "is_active", "date_joined"]
    list_filter = ["role", "is_staff", "is_active"]
    search_fields = ["username", "email"]
    fieldsets = DjangoUserAdmin.fieldsets + (("Role", {"fields": ("role",)}),)


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "user",
        "age",
        "sex",
        "preferred_language",
        "consent_given_at",
    ]
    list_filter = ["sex", "preferred_language"]
    search_fields = ["full_name", "user__username", "user__email"]
