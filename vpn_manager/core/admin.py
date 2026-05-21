from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, VpnConfig, TargetApp, Subscription


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "is_subscribed", "email", "is_active", "subscription")
    search_fields = ("is_subscribed", "is_active", "email")
    readonly_fields = ("is_subscribed", "subscription")


@admin.register(VpnConfig)
class VpnConfigAdmin(admin.ModelAdmin):
    list_display = ("user", "priority", "is_active")
    search_fields = ("user__username", "priority")


@admin.register(TargetApp)
class TargetAppAdmin(admin.ModelAdmin):
    list_display = ("user", "package_name")
    search_fields = ("user__username", "package_name")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "current_period_end",
        "renewal_count",
        "status",
        "created_at",
    )
    search_fields = (
        "user__username",
        "current_period_end",
        "renewal_count",
        "status",
    )
