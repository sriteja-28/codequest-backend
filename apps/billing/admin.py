from django.contrib import admin
from .models import BillingPlan, UserSubscription, Payment


@admin.register(BillingPlan)
class BillingPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "period", "ai_hints_per_day", "is_active"]
    list_filter = ["is_active", "period"]
    search_fields = ["name", "description"]


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "started_at", "expires_at", "is_active"]
    list_filter = ["is_active", "plan", "started_at"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["user", "amount", "status", "payment_method", "created_at"]
    list_filter = ["status", "created_at", "payment_method"]
    search_fields = ["user__username", "transaction_id"]
    readonly_fields = ["created_at", "transaction_id"]
