from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fields = ("program", "photo", "bio")


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "email", "first_name", "last_name", "program", "is_active", "date_joined")
    list_filter = ("is_active", "is_staff", "profile__program")
    actions = ["suspend_users", "reactivate_users"]

    @admin.display(description="Program", ordering="profile__program")
    def program(self, obj):
        return obj.profile.get_program_display() if hasattr(obj, "profile") else "—"

    @admin.action(description="Suspend selected users (block login)")
    def suspend_users(self, request, queryset):
        n = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f"Suspended {n} user(s).")

    @admin.action(description="Reactivate selected users")
    def reactivate_users(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f"Reactivated {n} user(s).")


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
