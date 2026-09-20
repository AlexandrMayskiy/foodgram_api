from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import Follow

User = get_user_model()


@admin.register(User)
class UserAdmin(UserAdmin):
    """Настройка отображения кастомных пользователей в админке."""

    list_display = (
        "id",
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
    )
    search_fields = ("username", "email", "first_name", "last_name")
    list_filter = ("username", "email", "is_staff", "is_active")
    ordering = ("id",)


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    """Настройка отображения подписок в админке."""

    list_display = ("id", "user", "author")
    search_fields = (
        "user__username",
        "author__username",
        "user__email",
        "author__email",
    )
