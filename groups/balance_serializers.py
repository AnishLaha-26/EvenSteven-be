from rest_framework import serializers
from decimal import Decimal


class MemberBalanceSerializer(serializers.Serializer):
    """Serializer for individual member balance information."""
    user_id = serializers.IntegerField()
    user_email = serializers.EmailField()
    user_name = serializers.CharField()
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.ChoiceField(choices=['owed', 'owes', 'settled'])


class GroupBalanceSummarySerializer(serializers.Serializer):
    """Serializer for group balance summary."""
    group_id = serializers.IntegerField()
    group_name = serializers.CharField()
    currency = serializers.CharField()
    members = MemberBalanceSerializer(many=True)
    total_owed = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_owing = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_balance = serializers.DecimalField(max_digits=12, decimal_places=2)


class BalanceBreakdownSerializer(serializers.Serializer):
    """Serializer for detailed balance breakdown."""
    expenses_paid = serializers.DecimalField(max_digits=12, decimal_places=2)
    expense_shares_owed = serializers.DecimalField(max_digits=12, decimal_places=2)
    payments_made = serializers.DecimalField(max_digits=12, decimal_places=2)
    payments_received = serializers.DecimalField(max_digits=12, decimal_places=2)
    settlements_made = serializers.DecimalField(max_digits=12, decimal_places=2)
    settlements_received = serializers.DecimalField(max_digits=12, decimal_places=2)


class MemberBalanceDetailSerializer(serializers.Serializer):
    """Serializer for detailed member balance information."""
    user_id = serializers.IntegerField()
    user_email = serializers.EmailField()
    group_id = serializers.IntegerField()
    group_name = serializers.CharField()
    currency = serializers.CharField()
    current_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    breakdown = BalanceBreakdownSerializer()
    status = serializers.ChoiceField(choices=['owed', 'owes', 'settled'])


class MemberBalanceFromUserPerspectiveSerializer(serializers.Serializer):
    """Serializer for member balance from current user's perspective."""
    user_id = serializers.IntegerField()
    user_email = serializers.EmailField()
    user_name = serializers.CharField()
    balance_with_you = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.ChoiceField(choices=['you', 'owes_you', 'you_owe', 'settled'])
    is_current_user = serializers.BooleanField()


class GroupBalanceSummaryFromUserPerspectiveSerializer(serializers.Serializer):
    """Serializer for group balance summary from current user's perspective."""
    group_id = serializers.IntegerField()
    group_name = serializers.CharField()
    currency = serializers.CharField()
    current_user_id = serializers.IntegerField()
    members = MemberBalanceFromUserPerspectiveSerializer(many=True)
    total_owed_to_you = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_you_owe = serializers.DecimalField(max_digits=12, decimal_places=2)
    your_net_balance = serializers.DecimalField(max_digits=12, decimal_places=2)


class BalanceUpdateSerializer(serializers.Serializer):
    """Serializer for balance update operations."""
    success = serializers.BooleanField()
    message = serializers.CharField()
    updated_members = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of user IDs whose balances were updated"
    )
