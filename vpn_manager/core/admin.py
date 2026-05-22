from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, VpnConfig, TargetApp, Subscription


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_active", "subscription")
    search_fields = ("email",)
    list_filter = ("is_active",)
    readonly_fields = ("subscription",)

    @admin.display(boolean=True, description="Подписка")
    def is_subscribed_display(self, obj):
        return obj.is_subscribed


@admin.register(VpnConfig)
class VpnConfigAdmin(admin.ModelAdmin):
    list_display = ("user", "priority")
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
    readonly_fields = (
        "gateway_customer_id",
        "gateway_subscription_id",
        "created_at",
        "updated_at",
    )
