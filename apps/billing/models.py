from django.db import models
from django.utils import timezone


class BillingPlan(models.Model):
    """Subscription plans."""
    FREE = "FREE"
    PRO = "PRO"
    PLAN_CHOICES = [
        (FREE, "Free"),
        (PRO, "Pro"),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    period = models.CharField(max_length=20, default="month")  # month, year
    
    features = models.JSONField(default=list, help_text="List of features")
    ai_hints_per_day = models.PositiveIntegerField(default=20)
    ai_chat_per_day = models.PositiveIntegerField(default=20)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "billing_plans"
        ordering = ["price"]

    def __str__(self):
        return self.name


class UserSubscription(models.Model):
    """Track user subscriptions."""
    user = models.OneToOneField(
        "users.User", on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(BillingPlan, on_delete=models.SET_NULL, null=True)
    
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_subscriptions"

    def __str__(self):
        return f"{self.user.username} - {self.plan.name if self.plan else 'No Plan'}"


class Payment(models.Model):
    """Payment records."""
    STATUS_PENDING = "PENDING"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]
    
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="payments"
    )
    subscription = models.ForeignKey(
        UserSubscription, on_delete=models.SET_NULL, null=True, blank=True
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, unique=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.status})"
