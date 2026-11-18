from rest_framework import serializers


class BillingPlanSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=100)
    description = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    period = serializers.CharField(max_length=20)
    features = serializers.ListField(child=serializers.CharField())


class SubscriptionSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    payment_method_id = serializers.CharField(max_length=100, required=False)


class CancelSubscriptionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False)


class AdminPlanChangeSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=["FREE", "PRO"])
    days = serializers.IntegerField(min_value=1, max_value=3650, default=30)
